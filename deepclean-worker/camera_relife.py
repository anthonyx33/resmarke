"""Camera Re-Life -- non-generative camera acquisition re-simulation (V7 layer).

The V7 pipeline keeps the full-frame Qwen wash (the SynthID carrier breaker)
unchanged. The wash leaves a fresh full-frame generative fingerprint. This
module is the second layer: it re-acquires the washed frame through a
simulated camera pipeline so the DELIVERED pixel statistics are camera
statistics, not generator statistics.

Order is physical, and the order is the mechanism:

    washed RGB
      -> micro-rotation + center crop + resample   (phase/grid break)
      -> lens MTF blur (chroma-heavier than luma)  (optics)
      -> sRGB -> linear                            (sensor domain)
      -> Bayer RGGB mosaicing                      (half the samples discarded)
      -> shot + read noise BEFORE demosaic         (sensor noise, physically
                                                    placed -- the noise becomes
                                                    part of the image structure)
      -> bilinear demosaic                         (CFA interpolation structure)
      -> white-balance / channel-gain drift        (color pipeline)
      -> linear -> sRGB + subtle S-curve           (rendering)
      -> chromatic aberration + micro vignette     (lens character)
      -> luma-only unsharp (light)                 (default camera sharpening)

All stages are classical. No neural model runs here, so nothing new is
stamped -- that is the entire point of the layer.
"""

import hashlib
import time

import numpy as np
from PIL import Image, ImageFilter

from photo_naturalization import (
    apply_lens_character,
    apply_micro_vignette,
    demosaic_channel,
    edge_pad,
    linear_to_srgb,
    split_channel_blur,
    srgb_to_linear,
)


PRESETS = {
    "light": {
        "rotation_deg": 0.10,
        "blur_luma": 0.12,
        "blur_chroma_mult": 1.15,
        "shot_noise": 0.00045,
        "read_noise": 0.0009,
        "wb_drift": 0.012,
        "tone": 0.03,
        "ca_amount": 0.10,
        "vignette": 0.04,
        "sharpen_percent": 10,
        "bayer_mix": 1.0,
    },
    "balanced": {
        "rotation_deg": 0.18,
        "blur_luma": 0.18,
        "blur_chroma_mult": 1.25,
        "shot_noise": 0.0007,
        "read_noise": 0.0013,
        "wb_drift": 0.02,
        "tone": 0.05,
        "ca_amount": 0.16,
        "vignette": 0.07,
        "sharpen_percent": 14,
        "bayer_mix": 1.0,
    },
    "strong": {
        "rotation_deg": 0.30,
        "blur_luma": 0.28,
        "blur_chroma_mult": 1.40,
        "shot_noise": 0.0011,
        "read_noise": 0.0019,
        "wb_drift": 0.035,
        "tone": 0.08,
        "ca_amount": 0.22,
        "vignette": 0.10,
        "sharpen_percent": 16,
        "bayer_mix": 1.0,
    },
}

DEFAULT_SETTINGS = {
    "enabled": True,
    "preset": "balanced",
}


def is_camera_relife(settings):
    return isinstance(settings, dict) and settings.get("mode") == "camera-relife"


def normalize_camera_relife_settings(settings):
    raw = settings if isinstance(settings, dict) else {}
    sub = raw.get("camera_relife") if isinstance(raw.get("camera_relife"), dict) else {}
    preset = str(sub.get("preset", DEFAULT_SETTINGS["preset"]))
    if preset not in PRESETS:
        preset = DEFAULT_SETTINGS["preset"]
    cfg = dict(PRESETS[preset])
    cfg["enabled"] = raw.get("mode") == "camera-relife" if raw else True
    if "enabled" in sub:
        cfg["enabled"] = bool(sub["enabled"])
    for key in PRESETS[preset]:
        if key in sub:
            cfg[key] = _clamp(sub[key], 0.0, 2.0)
    cfg["preset"] = preset
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
    material = f"camera-relife-v1:{creator_id}:{seed_extra}:{size[0]}x{size[1]}:{salt}"
    return int(hashlib.sha256(material.encode("utf-8")).hexdigest()[:16], 16) & 0xFFFFFFFF


def apply_camera_relife(image, settings=None, creator_id="camera-relife", seed_extra=""):
    """Run the full camera re-life stack in-place-free style: returns
    (relifed_image, report). Caller owns the final single JPEG encode."""
    cfg = normalize_camera_relife_settings(settings)
    report = {
        "enabled": bool(cfg["enabled"]),
        "pipeline": "camera_relife_v1",
        "applied": False,
        "preset": cfg["preset"],
        "settings": {k: cfg[k] for k in PRESETS[cfg["preset"]]},
        "layers": {},
    }
    if not cfg["enabled"]:
        return image, report

    started = time.time()
    rng = np.random.default_rng(_seed(creator_id, seed_extra, image.size, 1))

    work = image.convert("RGB")

    # --- 1. grid/phase break --------------------------------------------------
    work = _rotate_crop(work, rng, cfg["rotation_deg"])
    report["layers"]["grid_break"] = {
        "method": "micro_rotation + center_crop + resample",
        "rotation_deg": cfg["rotation_deg"],
    }

    # --- 2. optics: lens MTF (chroma heavier than luma) -----------------------
    work = split_channel_blur(work, cfg["blur_luma"], cfg["blur_chroma_mult"])
    report["layers"]["lens_mtf"] = {
        "method": "split_channel_gaussian",
        "luma_radius": cfg["blur_luma"],
        "chroma_multiplier": cfg["blur_chroma_mult"],
    }

    # --- 3. sensor domain: Bayer + pre-demosaic noise + demosaic --------------
    linear = srgb_to_linear(np.asarray(work).astype(np.float32) / 255.0)
    linear = _bayer_roundtrip(linear, rng, cfg["shot_noise"], cfg["read_noise"], cfg["bayer_mix"])
    report["layers"]["bayer_cfa"] = {
        "method": "bayer_rggb_mosaic + pre_demosaic_shot_read_noise + bilinear_demosaic",
        "pattern": "RGGB",
        "shot_noise": cfg["shot_noise"],
        "read_noise": cfg["read_noise"],
        "mix": cfg["bayer_mix"],
        "noise_before_demosaic": True,
    }

    # --- 4. color pipeline: WB drift ------------------------------------------
    gains = 1.0 + rng.uniform(-cfg["wb_drift"], cfg["wb_drift"], size=3).astype(np.float32)
    linear = np.clip(linear * gains[None, None, :], 0.0, 1.0)
    report["layers"]["white_balance_drift"] = {
        "method": "per_channel_gain_drift",
        "gains": [float(g) for g in gains],
    }

    # --- 5. rendering: back to sRGB + tone curve ------------------------------
    work = Image.fromarray(np.clip(linear_to_srgb(linear) * 255.0 + 0.5, 0, 255).astype(np.uint8))
    if cfg["tone"] > 0:
        work = _tone_curve(work, cfg["tone"])
    report["layers"]["tone_curve"] = {"method": "subtle_s_curve", "amount": cfg["tone"]}

    # --- 6. lens character at delivery resolution -----------------------------
    if cfg["ca_amount"] > 0:
        work = apply_lens_character(work, cfg["ca_amount"])
    if cfg["vignette"] > 0:
        work = apply_micro_vignette(work, cfg["vignette"])
    report["layers"]["lens_character"] = {
        "chromatic_aberration": cfg["ca_amount"],
        "micro_vignette": cfg["vignette"],
    }

    # --- 7. default camera sharpening (luma only, no chroma halos) ------------
    if cfg["sharpen_percent"] > 0:
        work = _luma_unsharp(work, cfg["sharpen_percent"])
    report["layers"]["sharpen"] = {
        "method": "luma_unsharp",
        "percent": cfg["sharpen_percent"],
    }

    report["applied"] = True
    report["runtime_ms"] = int((time.time() - started) * 1000)
    return work.convert("RGB"), report


# ---------------------------------------------------------------------------
# Stages
# ---------------------------------------------------------------------------

def _rotate_crop(image, rng, max_degrees):
    """Small random rotation with edge padding + center crop back to the
    original size. Breaks the pixel grid/phase alignment of the washed frame."""
    if max_degrees <= 0:
        return image
    angle = float(rng.uniform(-max_degrees, max_degrees))
    width, height = image.size
    pad = max(8, int(np.ceil(np.hypot(width, height) * abs(angle) * np.pi / 180.0)) + 4)
    padded = edge_pad(image, pad)
    rotated = padded.rotate(angle, resample=Image.Resampling.BILINEAR, expand=False)
    pw, ph = rotated.size
    left, top = (pw - width) // 2, (ph - height) // 2
    return rotated.crop((left, top, left + width, top + height))


def _bayer_roundtrip(linear, rng, shot, read, mix):
    """Full-strength RGGB CFA round-trip in linear light.

    Mosaic -> per-sample shot/read noise -> bilinear demosaic. The noise is
    added at the SAMPLED positions only, then spread by the interpolation --
    physically, this is where sensor noise enters a real camera, and it makes
    the noise part of the image structure instead of a coat on top of it.
    """
    height, width, _ = linear.shape
    yy, xx = np.indices((height, width))
    red_mask = ((yy % 2) == 0) & ((xx % 2) == 0)
    blue_mask = ((yy % 2) == 1) & ((xx % 2) == 1)
    green_mask = ~(red_mask | blue_mask)
    masks = (red_mask, green_mask, blue_mask)

    luma = (
        linear[..., 0] * 0.2126
        + linear[..., 1] * 0.7152
        + linear[..., 2] * 0.0722
    )
    variance = luma * shot + read ** 2
    noise = rng.normal(0.0, np.sqrt(variance).astype(np.float32)).astype(np.float32)

    demosaiced = []
    for channel, mask in enumerate(masks):
        # Sensor sample: value at the CFA position plus the photon/read noise
        # drawn at that position.
        sampled = (linear[..., channel] + noise) * mask.astype(np.float32)
        demosaiced.append(demosaic_channel(sampled, mask.astype(np.float32)))
    demosaiced_rgb = np.stack(demosaiced, axis=2)

    mix = min(1.0, max(0.0, float(mix)))
    return linear * (1.0 - mix) + demosaiced_rgb * mix


def _tone_curve(image, amount):
    """Subtle S-curve (contrast) in sRGB -- the rendering-stage fingerprint
    of a real JPEG pipeline, in the opposite direction of a flat diffusion
    decode."""
    if amount <= 0:
        return image
    x = np.asarray(image).astype(np.float32) / 255.0
    # y = x + a * x * (1 - x) * (2x - 1)  -> gentle S, endpoints fixed.
    curved = x + amount * x * (1.0 - x) * (2.0 * x - 1.0)
    curved = np.clip(curved * 255.0 + 0.5, 0, 255).astype(np.uint8)
    return Image.fromarray(curved)


def _luma_unsharp(image, percent):
    """Sharpening on luminance only -- default camera sharpening, no chroma
    halos (chroma halos are an upscaler/GAN tell)."""
    if percent <= 0:
        return image
    y, cb, cr = image.convert("YCbCr").split()
    y = y.filter(ImageFilter.UnsharpMask(radius=1.2, percent=percent, threshold=2))
    return Image.merge("YCbCr", (y, cb, cr)).convert("RGB")
