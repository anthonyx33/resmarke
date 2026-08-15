"""Coherent Camera Model (V8.8) — inverse ISP -> virtual camera -> forward ISP.

Adopted from the external pipeline review (G8): do not stack camera clues on
top of the generator's residual. Instead, walk the image INTO an approximate
camera domain through inverse rendering (display gamma -> tone -> CCM -> WB),
apply one coherent optical + sensor acquisition model, then walk it back OUT
through the matching forward rendering. The paired transforms largely cancel
for content, while the intermediate noise, clipping, cross-channel
correlations and demosaic structure acquire genuinely camera-like statistics.

Order (all non-generative, CPU):

    1.  sRGB -> linear (inverse display gamma)
    2.  weak synthesis-residual cleanup (edge-aware, flat regions only)
    3.  inverse tone curve (LUT)
    4.  inverse camera CCM  -> linear camera RGB
    5.  inverse WB gains
    6.  optics in camera RGB: per-channel PSF -> restrained CA -> tiny vignette
    7.  WB gains (forward)
    8.  Bayer RGGB mosaic -> shot/read noise BEFORE demosaic -> MHC demosaic
    9.  weak ISP denoise (edge-aware)
    10. forward camera CCM -> working linear RGB
    11. forward tone curve (LUT)
    12. linear -> sRGB
    13. restrained luma sharpening

Deliberately absent (per review): random WB drift > 1%, visible FPN banding,
hot pixels, synthetic PRNU, palette quantization, engineered JPEG grids.
"""

import hashlib
import time

import numpy as np
from PIL import Image, ImageFilter

from camera_relife import _bayer_roundtrip, _luma_unsharp
from photo_naturalization import (
    apply_lens_character,
    apply_micro_vignette,
    linear_to_srgb,
    srgb_to_linear,
)


# Plausible daylight camera->working-RGB colour correction matrix (row sums
# ~1, white preserved). One fixed profile beats random matrices: paired
# inverse/forward transforms cancel for content and colour the noise path
# consistently.
CCM = np.array(
    [
        [1.8595, -0.6277, -0.2318],
        [-0.1585, 1.3840, -0.2255],
        [-0.0556, -0.3798, 1.4354],
    ],
    dtype=np.float64,
)

PRESETS = {
    # strength axis (P1..P3 of the review's ladder; P0 = resize only)
    "light": {
        "psf_g": 0.25, "psf_rb": 0.30, "ca_amount": 0.10, "vignette": 0.005,
        "shot_noise": 0.0005, "read_noise": 0.0009, "cleanup": 0.10,
        "denoise": 0.04, "tone": 0.02, "wb_drift": 0.005, "sharpen_percent": 8,
    },
    "balanced": {
        "psf_g": 0.32, "psf_rb": 0.40, "ca_amount": 0.20, "vignette": 0.010,
        "shot_noise": 0.0007, "read_noise": 0.0012, "cleanup": 0.20,
        "denoise": 0.06, "tone": 0.03, "wb_drift": 0.0075, "sharpen_percent": 10,
    },
    "deep": {
        "psf_g": 0.40, "psf_rb": 0.50, "ca_amount": 0.30, "vignette": 0.015,
        "shot_noise": 0.0010, "read_noise": 0.0016, "cleanup": 0.30,
        "denoise": 0.09, "tone": 0.04, "wb_drift": 0.01, "sharpen_percent": 12,
    },
}

DEFAULT_SETTINGS = {"enabled": True, "strength": "balanced"}


def is_coherent_camera(settings):
    return isinstance(settings, dict) and settings.get("mode") == "coherent-camera"


def normalize_coherent_camera_settings(settings):
    raw = settings if isinstance(settings, dict) else {}
    sub = raw.get("coherent_camera") if isinstance(raw.get("coherent_camera"), dict) else {}
    strength = str(sub.get("strength", DEFAULT_SETTINGS["strength"]))
    if strength not in PRESETS:
        strength = DEFAULT_SETTINGS["strength"]
    cfg = dict(PRESETS[strength])
    cfg["enabled"] = raw.get("mode") == "coherent-camera" if raw else True
    if "enabled" in sub:
        cfg["enabled"] = bool(sub["enabled"])
    for key in PRESETS[strength]:
        if key in sub:
            cfg[key] = _clamp(sub[key], 0.0, 2.0)
    cfg["strength"] = strength
    return cfg


def _clamp(value, low, high):
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return low
    if not np.isfinite(parsed):
        return low
    return max(low, min(high, parsed))


def _seed(creator_id, seed_extra, size, salt):
    material = f"coherent-camera-v1:{creator_id}:{seed_extra}:{size[0]}x{size[1]}:{salt}"
    return int(hashlib.sha256(material.encode("utf-8")).hexdigest()[:16], 16) & 0xFFFFFFFF


def apply_coherent_camera(image, settings=None, creator_id="coherent-camera", seed_extra=""):
    """Run the full coherent camera model in-place-free style: returns
    (naturalized_image, report). Caller owns the single final JPEG encode."""
    cfg = normalize_coherent_camera_settings(settings)
    report = {
        "enabled": bool(cfg["enabled"]),
        "pipeline": "coherent_camera_v1",
        "applied": False,
        "strength": cfg["strength"],
        "settings": {k: cfg[k] for k in PRESETS[cfg["strength"]]},
        "layers": {},
    }
    if not cfg["enabled"]:
        return image, report

    started = time.time()
    rng = np.random.default_rng(_seed(creator_id, seed_extra, image.size, 1))
    work = image.convert("RGB")

    # --- 1. display gamma -> linear -------------------------------------------
    linear = srgb_to_linear(np.asarray(work).astype(np.float32) / 255.0)
    report["layers"]["inverse_gamma"] = {"applied": True}

    # --- 2. weak synthesis-residual cleanup (flat regions, edge-aware) --------
    linear = _residual_cleanup(linear, cfg["cleanup"])
    report["layers"]["residual_cleanup"] = {"amount": cfg["cleanup"], "edge_aware": True}

    # --- 3-5. inverse tone / CCM / WB -----------------------------------------
    tone_fwd, tone_inv = _make_tone_luts(cfg["tone"])
    linear = _apply_lut(linear, tone_inv)
    cam = _apply_ccm(linear, np.linalg.inv(CCM))
    gains = _wb_gains(rng, cfg["wb_drift"])
    cam = cam / gains[None, None, :]
    report["layers"]["inverse_isp"] = {
        "tone_amount": cfg["tone"], "ccm": "fixed_daylight_inverse", "wb_drift": cfg["wb_drift"],
    }

    # --- 6. optics in camera RGB ----------------------------------------------
    cam = _per_channel_psf(cam, cfg["psf_g"], cfg["psf_rb"])
    cam_image = Image.fromarray(np.clip(cam * 255.0, 0, 255).astype(np.uint8))
    cam_image = apply_lens_character(cam_image, cfg["ca_amount"])
    cam_image = apply_micro_vignette(cam_image, cfg["vignette"])
    cam = np.asarray(cam_image).astype(np.float32) / 255.0
    report["layers"]["optics"] = {
        "psf_g": cfg["psf_g"], "psf_rb": cfg["psf_rb"], "ca_amount": cfg["ca_amount"],
        "vignette": cfg["vignette"], "domain": "linear_camera_rgb_before_cfa",
    }

    # --- 7. WB forward ---------------------------------------------------------
    cam = cam * gains[None, None, :]

    # --- 8. CFA + pre-demosaic noise + MHC demosaic ---------------------------
    cam = _bayer_roundtrip(
        cam, rng, cfg["shot_noise"], cfg["read_noise"], 1.0,
        malvar=True, fpn_col=0.0, fpn_row=0.0, hot_frac=0.0, match_read=0.0,
    )
    report["layers"]["sensor"] = {
        "pattern": "RGGB", "shot_noise": cfg["shot_noise"], "read_noise": cfg["read_noise"],
        "demosaic": "malvar_he_cutler", "noise_before_demosaic": True,
    }

    # --- 9. weak ISP denoise ---------------------------------------------------
    cam = _isp_denoise(cam, cfg["denoise"])
    report["layers"]["isp_denoise"] = {"amount": cfg["denoise"], "edge_aware": True}

    # --- 10-12. forward CCM / tone / sRGB -------------------------------------
    linear_out = _apply_ccm(cam, CCM)
    linear_out = _apply_lut(linear_out, tone_fwd)
    out = np.clip(linear_to_srgb(np.clip(linear_out, 0.0, 1.0)) * 255.0 + 0.5, 0, 255).astype(np.uint8)
    work = Image.fromarray(out)
    report["layers"]["forward_isp"] = {"ccm": "fixed_daylight_forward", "tone_amount": cfg["tone"]}

    # --- 13. restrained luma sharpening ----------------------------------------
    work = _luma_unsharp(work, cfg["sharpen_percent"])
    report["layers"]["sharpen"] = {"method": "luma_unsharp", "percent": cfg["sharpen_percent"]}

    report["applied"] = True
    report["runtime_ms"] = int((time.time() - started) * 1000)
    return work.convert("RGB"), report


# ---------------------------------------------------------------------------
# Stages
# ---------------------------------------------------------------------------

def _residual_cleanup(linear, amount):
    """Remove the strongest generator residual in FLAT regions only.

    original = structure + generator_residual; attenuate 0..amount of the
    high-pass residual where the local gradient is low, keep edges intact."""
    if amount <= 0:
        return linear
    rgb = Image.fromarray(np.clip(linear * 255.0, 0, 255).astype(np.uint8))
    blurred = np.asarray(rgb.filter(ImageFilter.GaussianBlur(radius=1.0))).astype(np.float32) / 255.0
    gray = linear[..., 0] * 0.2126 + linear[..., 1] * 0.7152 + linear[..., 2] * 0.0722
    edge = np.abs(gray - np.asarray(
        rgb.convert("L").filter(ImageFilter.GaussianBlur(radius=1.0))
    ).astype(np.float32) / 255.0)
    flat = np.clip(1.0 - (edge - 0.008) / 0.03, 0.0, 1.0)[..., None]
    attenuation = 1.0 - amount * flat
    return blurred * (1.0 - attenuation) + linear * attenuation


def _make_tone_luts(amount):
    """Subtle monotonic S-curve (cubic) + exact inverse via LUT inversion."""
    x = np.linspace(0.0, 1.0, 4096, dtype=np.float64)
    forward = x + amount * x * (1.0 - x) * (2.0 * x - 1.0)
    forward = np.clip(forward, 0.0, 1.0)
    inverse = np.interp(x, forward, x)
    return forward.astype(np.float32), inverse.astype(np.float32)


def _apply_lut(rgb, lut):
    idx = np.clip((rgb * (len(lut) - 1)).astype(np.int32), 0, len(lut) - 1)
    return lut[idx].astype(np.float32)


def _apply_ccm(rgb, matrix):
    flat = rgb.reshape(-1, 3)
    return (flat @ matrix.T.astype(np.float32)).reshape(rgb.shape).astype(np.float32)


def _wb_gains(rng, drift):
    # g fixed at 1; r/b drift is sub-1% per the review (visible colour change
    # buys little photographicity).
    return np.array([1.0 + float(rng.uniform(-drift, drift)), 1.0,
                     1.0 + float(rng.uniform(-drift, drift))], dtype=np.float32)


def _per_channel_psf(cam, psf_g, psf_rb):
    """Wavelength-dependent optical PSF in linear camera RGB (optics precede
    the sensor). Radii are pixel-equivalent sigmas at current resolution."""
    image = Image.fromarray(np.clip(cam * 255.0, 0, 255).astype(np.uint8))
    r, g, b = image.split()
    if psf_rb > 0:
        r = r.filter(ImageFilter.GaussianBlur(radius=psf_rb))
        b = b.filter(ImageFilter.GaussianBlur(radius=psf_rb))
    if psf_g > 0:
        g = g.filter(ImageFilter.GaussianBlur(radius=psf_g))
    return np.asarray(Image.merge("RGB", (r, g, b))).astype(np.float32) / 255.0


def _isp_denoise(cam, amount):
    """Very weak edge-aware ISP denoise after demosaic: pull flat areas
    slightly toward a local blur, leave edges alone (no visible smoothing)."""
    if amount <= 0:
        return cam
    rgb = Image.fromarray(np.clip(cam * 255.0, 0, 255).astype(np.uint8))
    blurred = np.asarray(rgb.filter(ImageFilter.GaussianBlur(radius=0.6))).astype(np.float32) / 255.0
    gray = cam[..., 0] * 0.2126 + cam[..., 1] * 0.7152 + cam[..., 2] * 0.0722
    edge = np.abs(gray - np.asarray(
        rgb.convert("L").filter(ImageFilter.GaussianBlur(radius=0.6))
    ).astype(np.float32) / 255.0)
    flat = np.clip(1.0 - (edge - 0.006) / 0.025, 0.0, 1.0)[..., None]
    mask = amount * flat
    return cam * (1.0 - mask) + blurred * mask
