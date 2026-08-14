"""DS ReMint V6 -- quality-constrained reconstruction remint.

Builds on CX Remint v5 (deep-hist-up) with the verified fixes for the two
live problems:

  1. "Still flagged as Flux / regenerated with a different AI":
     - Spectral amplitude reshape (1/f^alpha + noise floor) now also runs at
       the FINAL resolution, where the detector reads the delivered file's
       statistics -- the upscale was re-steepening the spectrum back toward
       the diffusion look.
     - Dehalo before sharpening removes the overshoot halos that classifiers
       read as GAN/SR ringing.
     - A single luma-only unsharp pass (no chroma halos) and content-masked
       sensor grain give a camera high-frequency band without the
       "over-sharpened AI" look.

  2. "Pixelated / grainy / low quality":
     - ONE consolidated shift+downscale resample replaces the stacked
       subpixel-translate -> Lanczos -> bounce chain (v5's blur stack).
     - Grain/texture is applied ONCE, at the delivered resolution, masked so
       flat areas (skies) stay clean and textured areas get the sensor
       signature -- v5 added optical + RGB noise at process resolution and
       then magnified it by upscaling.
     - Reconstruction is anti-ringing Lanczos + dehalo + luma sharpen
       (classical, non-generative: nothing new is stamped).
     - Exactly ONE JPEG encode (the worker finalize pass-throughs the bytes).

Pipeline order (matches production reality):

    decode -> [pre-regeneration (SynthID killer) -> colour restore]
           -> per-rung: single consolidated resample (adaptive escalates
              against the real detector and stops at minimum destruction)
           -> reconstruction to delivery size (never above the original)
           -> final-resolution spectral reshape
           -> final tone lock (histogram match to original)
           -> realism lens character + micro vignette
           -> masked sensor texture (once)
           -> one JPEG encode with coherent iPhone EXIF
           -> final-byte QC (SSIM, PSNR, sharpness ratio, blockiness, halo)
"""

import hashlib
import time
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

from max_cx_remint import (
    ACQUISITION_PRESETS,
    HARD_MIN_LONG_EDGE,
    QUALITY_FLOOR_PRESETS,
    _fft_radial_amplitude_match,
    _histogram_match,
)
from neural_texture import compare_images
from photo_naturalization import (
    apply_acquisition_noise_rgb,
    apply_lens_character,
    apply_micro_vignette,
    edge_pad,
)
import iphone_exif


DEFAULT_SETTINGS = {
    "enabled": True,
    "engine_mode": "adaptive",       # "adaptive" (detector-gated) | "template"
    "quality_floor": "balanced",     # key into QUALITY_FLOOR_PRESETS
    "target_long_edge": None,        # explicit sanitize floor override
    "acquisition": "balanced",       # key into ACQUISITION_PRESETS
    "iphone_exif": True,
    "device": "auto",
    "resolution_mode": "off",        # "off" | "standard" (72 DPI) | "custom"
    "x_resolution": 72.0,
    "y_resolution": 72.0,
    # --- sanitization ---------------------------------------------------------
    # Pre-regeneration is the only operation that removed SynthID in live tests.
    "pre_regen": True,
    "regen_level": 8,
    "regen_process_cap": 1536,
    "regen_timeout": 300,
    # Final-resolution spectral reshape kills the diffusion/flux amplitude
    # signature the regen + upscale leave behind.
    "spectral_reshape": True,
    "spectral_strength": 0.3,
    "spectral_alpha": 2.0,
    "spectral_noise_floor": 0.012,
    # Pull the regenerated palette back to the original's (histogram match).
    "color_restore": True,
    "color_restore_strength": 0.8,
    "color_restore_method": "histogram",   # "histogram" | "mean_std"
    # Single consolidated resample kernel: "ewi-lanczos" (anti-ringing
    # pre-blur + Lanczos), "lanczos", or "bicubic".
    "resample_kernel": "ewi-lanczos",
    "bounce": False,                 # v5's kernel-diverse bounce; off by default
    "realism_boost": 0.3,            # lens character + micro vignette
    # --- reconstruction (the quality stage) -----------------------------------
    # Delivery long edge; None = min(source_long_edge, 1440). Never upscales
    # past the source unless output_target explicitly says otherwise.
    "output_target": None,
    "dehalo_strength": 0.6,
    "sharpen_percent": 24,           # final luma-only unsharp
    "texture_amount": 0.9,           # masked sensor-grain strength (0..1)
    # --- output ---------------------------------------------------------------
    "jpeg_quality": 94,
    "jpeg_subsampling": "4:2:2",
    "ai_threshold": 0.50,            # adaptive: ship if P(AI) <= this
    "max_rungs": 5,
}


def is_ds_remint_v6(settings):
    return isinstance(settings, dict) and settings.get("mode") == "ds-remint-v6"


def normalize_ds_remint_v6_settings(settings):
    raw = settings if isinstance(settings, dict) else {}
    sub = raw.get("ds_remint_v6") if isinstance(raw.get("ds_remint_v6"), dict) else {}
    cfg = dict(DEFAULT_SETTINGS)
    cfg["enabled"] = raw.get("mode") == "ds-remint-v6"

    engine_mode = str(sub.get("engine_mode", cfg["engine_mode"]))
    cfg["engine_mode"] = engine_mode if engine_mode in ("template", "adaptive") else "adaptive"

    qf = str(sub.get("quality_floor", cfg["quality_floor"]))
    cfg["quality_floor"] = qf if qf in QUALITY_FLOOR_PRESETS else "balanced"

    acq = str(sub.get("acquisition", cfg["acquisition"]))
    cfg["acquisition"] = acq if acq in ACQUISITION_PRESETS else "balanced"

    if sub.get("target_long_edge") is not None:
        cfg["target_long_edge"] = max(
            HARD_MIN_LONG_EDGE, int(_clamp(sub["target_long_edge"], 64, 8192))
        )
    else:
        cfg["target_long_edge"] = None

    cfg["iphone_exif"] = bool(sub.get("iphone_exif", cfg["iphone_exif"]))
    cfg["device"] = str(sub.get("device", cfg["device"]))
    resolution_mode = str(sub.get("resolution_mode", cfg["resolution_mode"]))
    cfg["resolution_mode"] = (
        resolution_mode if resolution_mode in ("off", "standard", "custom") else "off"
    )
    cfg["x_resolution"] = float(_clamp(sub.get("x_resolution", cfg["x_resolution"]), 1, 12000))
    cfg["y_resolution"] = float(_clamp(sub.get("y_resolution", cfg["y_resolution"]), 1, 12000))

    cfg["pre_regen"] = bool(sub.get("pre_regen", cfg["pre_regen"]))
    cfg["regen_level"] = int(_clamp(sub.get("regen_level", cfg["regen_level"]), 3, 10))
    cfg["regen_process_cap"] = int(
        _clamp(sub.get("regen_process_cap", cfg["regen_process_cap"]), 512, 4096)
    )
    cfg["regen_timeout"] = int(_clamp(sub.get("regen_timeout", cfg["regen_timeout"]), 30, 900))
    cfg["spectral_reshape"] = bool(sub.get("spectral_reshape", cfg["spectral_reshape"]))
    cfg["spectral_strength"] = float(
        _clamp(sub.get("spectral_strength", cfg["spectral_strength"]), 0.0, 1.0)
    )
    cfg["spectral_alpha"] = float(_clamp(sub.get("spectral_alpha", cfg["spectral_alpha"]), 0.5, 4.0))
    cfg["spectral_noise_floor"] = float(
        _clamp(sub.get("spectral_noise_floor", cfg["spectral_noise_floor"]), 0.0, 0.2)
    )
    cfg["color_restore"] = bool(sub.get("color_restore", cfg["color_restore"]))
    cfg["color_restore_strength"] = float(
        _clamp(sub.get("color_restore_strength", cfg["color_restore_strength"]), 0.0, 1.0)
    )
    method = str(sub.get("color_restore_method", cfg["color_restore_method"]))
    cfg["color_restore_method"] = method if method in ("mean_std", "histogram") else "histogram"

    kernel = str(sub.get("resample_kernel", cfg["resample_kernel"]))
    cfg["resample_kernel"] = (
        kernel if kernel in ("ewi-lanczos", "lanczos", "bicubic") else "ewi-lanczos"
    )
    cfg["bounce"] = bool(sub.get("bounce", cfg["bounce"]))
    cfg["realism_boost"] = float(_clamp(sub.get("realism_boost", cfg["realism_boost"]), 0.0, 1.0))

    if sub.get("output_target") is not None:
        cfg["output_target"] = int(_clamp(sub["output_target"], 256, 8192))
    else:
        cfg["output_target"] = None
    cfg["dehalo_strength"] = float(_clamp(sub.get("dehalo_strength", cfg["dehalo_strength"]), 0.0, 1.0))
    cfg["sharpen_percent"] = int(_clamp(sub.get("sharpen_percent", cfg["sharpen_percent"]), 0, 200))
    cfg["texture_amount"] = float(_clamp(sub.get("texture_amount", cfg["texture_amount"]), 0.0, 1.5))

    cfg["jpeg_quality"] = int(_clamp(sub.get("jpeg_quality", cfg["jpeg_quality"]), 60, 100))
    sub_sampling = sub.get("jpeg_subsampling", cfg["jpeg_subsampling"])
    cfg["jpeg_subsampling"] = (
        sub_sampling if sub_sampling in ("4:2:0", "4:2:2", "4:4:4") else "4:2:2"
    )
    cfg["ai_threshold"] = float(_clamp(sub.get("ai_threshold", cfg["ai_threshold"]), 0.0, 1.0))
    cfg["max_rungs"] = int(_clamp(sub.get("max_rungs", cfg["max_rungs"]), 1, 8))
    return cfg


def apply_ds_remint_v6(input_path, output_path, creator_id, settings=None, seed_extra="", detector=None):
    """Full DS ReMint V6 pipeline. Writes the FINAL camera-like JPEG (with
    coherent iPhone EXIF when enabled) to output_path and returns a report.

    detector: optional callable(path)->dict for adaptive mode; expected keys
    ai_probability (0-1 or 0-100), watermark_present (bool). Without it,
    adaptive degrades to a single template run (never blind escalation).
    """
    cfg = normalize_ds_remint_v6_settings(settings)
    report = {
        "enabled": bool(cfg["enabled"]),
        "pipeline": "ds_remint_v6",
        "engine": "ds_remint_v6",
        "generative": bool(cfg["pre_regen"]),
        "applied": False,
        "settings": _public_settings(cfg),
        "layers": {},
        "attempts": [],
        "quality_floor_gate": {},
        "detector_gate": {"evaluated": False},
    }
    if not cfg["enabled"]:
        return report

    started = time.time()
    original = Image.open(input_path).convert("RGB")
    src_long = max(original.size)

    # --- layer 0: pre-regeneration (the SynthID killer). --------------------
    base = original
    if cfg["pre_regen"]:
        regen_path = Path(output_path).with_name(".ds-v6-regen.png")
        try:
            regen_report = _run_regen(
                input_path, str(regen_path), cfg, _seed(creator_id, seed_extra, original.size, 900)
            )
            base = Image.open(regen_path).convert("RGB")
            report["layers"]["pre_regeneration"] = regen_report
        finally:
            try:
                Path(regen_path).unlink()
            except OSError:
                pass

        if cfg["color_restore"]:
            if cfg["color_restore_method"] == "histogram":
                base = _histogram_match(base, original, cfg["color_restore_strength"])
                restore_method = "per_channel_histogram_match_to_original"
            else:
                base = _color_transfer(base, original, cfg["color_restore_strength"])
                restore_method = "per_channel_mean_std_match_to_original"
            report["layers"]["color_restore"] = {
                "method": restore_method,
                "strength": cfg["color_restore_strength"],
                "reimports_synthid": False,
            }

    preset = QUALITY_FLOOR_PRESETS[cfg["quality_floor"]]
    target = cfg["target_long_edge"] or preset["target_long_edge"]
    # Never upscale during sanitization, never exceed the source, never below
    # the hard floor unless the source itself is smaller.
    target = min(target, src_long)
    target = max(target, min(HARD_MIN_LONG_EDGE, src_long))
    report["source_long_edge"] = src_long
    report["sanitize_long_edge"] = target

    adaptive = cfg["engine_mode"] == "adaptive"
    if adaptive and detector is None:
        report["detector_gate"]["note"] = "no_detector_supplied_degraded_to_single_template_run"
        adaptive = False

    rung_count = cfg["max_rungs"] if adaptive else 1
    chosen = None
    for rung_index in range(rung_count):
        rung = _rung_config(rung_index, target, preset, cfg)
        seed = _seed(creator_id, seed_extra, base.size, rung_index)
        candidate = _sanitize_once(base, rung, seed, cfg)

        metrics = compare_images(base.resize(candidate.size, Image.Resampling.LANCZOS), candidate)
        floor_ok = float(metrics.get("ssim_luma_window11_mean", 0.0)) >= rung["min_ssim"]

        attempt = {
            "rung": rung_index,
            "params": _public_rung(rung),
            "metrics": {"psnr": _num(metrics.get("psnr")),
                        "ssim": _num(metrics.get("ssim_luma_window11_mean"))},
            "quality_floor_ok": floor_ok,
        }

        detector_ok = None
        if adaptive:
            probe_path = str(Path(output_path).with_name(".ds-v6-probe.jpg"))
            _encode_probe(candidate, probe_path)
            det = _safe_detect(detector, probe_path)
            detector_ok = _detector_pass(det, cfg)
            attempt["detector"] = det
            attempt["detector_ok"] = detector_ok
            try:
                Path(probe_path).unlink()
            except OSError:
                pass

        report["attempts"].append(attempt)
        chosen = _keep_better(chosen, {"image": candidate, "metrics": metrics, "rung": rung,
                                       "detector_ok": detector_ok, "floor_ok": floor_ok})
        if not adaptive:
            break
        if detector_ok and floor_ok:
            break  # minimum destruction that clears -> max quality

    final_image = chosen["image"]
    process_long = max(final_image.size)

    # --- reconstruction to delivery size -------------------------------------
    delivery = cfg["output_target"] or min(src_long, 1440)
    delivery = max(delivery, min(HARD_MIN_LONG_EDGE, src_long))
    delivery = min(delivery, src_long if cfg["output_target"] is None else delivery)
    if delivery > process_long:
        rng = np.random.default_rng(_seed(creator_id, seed_extra, final_image.size, 700))
        final_image = _reconstruct(final_image, delivery, cfg)
        report["layers"]["reconstruction"] = {
            "process_long_edge": process_long,
            "delivery_long_edge": max(final_image.size),
            "method": "anti_ringing_upscale + dehalo + luma_unsharp",
            "non_generative": True,
            "reintroduces_fingerprint": False,
        }
    else:
        report["layers"]["reconstruction"] = {
            "process_long_edge": process_long,
            "delivery_long_edge": process_long,
            "method": "none (delivery == process)",
        }

    # --- final-resolution passes (all non-generative) ------------------------
    if cfg["spectral_reshape"] and cfg["spectral_strength"] > 0:
        final_image = _fft_radial_amplitude_match(
            final_image,
            strength=cfg["spectral_strength"],
            alpha=cfg["spectral_alpha"],
            noise_floor=cfg["spectral_noise_floor"],
        )
        report["layers"]["final_spectral_reshape"] = {
            "strength": cfg["spectral_strength"],
            "alpha": cfg["spectral_alpha"],
            "noise_floor": cfg["spectral_noise_floor"],
            "resolution": list(final_image.size),
        }

    # Tone lock vs the original at final resolution (no spatial copy, so no
    # SynthID re-import).
    if cfg["color_restore"]:
        original_ref = original if original.size == final_image.size else original.resize(
            final_image.size, Image.Resampling.LANCZOS
        )
        final_image = _histogram_match(final_image, original_ref, cfg["color_restore_strength"])
        report["layers"]["final_tone_lock"] = {"strength": cfg["color_restore_strength"]}

    # Lens realism (chromatic aberration + light vignette) before texture.
    if cfg["realism_boost"] > 0:
        final_image = apply_lens_character(final_image, amount=0.35 * cfg["realism_boost"])

    # ONE masked sensor-texture pass at the delivered resolution. Flat areas
    # (skies, gradients) get only a light anti-banding grain; textured areas
    # get the full camera signature. This replaces v5's triple noise stack.
    texture_rng = np.random.default_rng(_seed(creator_id, seed_extra, final_image.size, 800))
    rung_acq = ACQUISITION_PRESETS[cfg["acquisition"]]
    final_image = _masked_texture(
        final_image,
        texture_rng,
        amount=rung_acq["noise"] * chosen["rung"]["noise_mult"],
        texture_amount=cfg["texture_amount"],
        vignette=rung_acq["vignette"],
    )
    report["layers"]["camera_texture"] = {
        "method": "masked_sensor_grain_once_at_final_resolution",
        "non_generative": True,
    }

    # --- one encode ----------------------------------------------------------
    exif_report = {"enabled": False}
    if cfg["iphone_exif"]:
        exif_bytes, exif_report = iphone_exif.build_iphone_exif(
            final_image.width,
            final_image.height,
            creator_id,
            seed_extra,
            device=cfg["device"],
            resolution_mode=cfg["resolution_mode"],
            x_resolution=cfg["x_resolution"],
            y_resolution=cfg["y_resolution"],
        )
        iphone_exif.write_exif_jpeg(
            final_image, output_path, exif_bytes, cfg["jpeg_quality"], cfg["jpeg_subsampling"]
        )
    else:
        final_image.save(
            output_path, format="JPEG", quality=cfg["jpeg_quality"], optimize=True,
            subsampling=cfg["jpeg_subsampling"],
        )
    report["layers"]["iphone_exif"] = exif_report
    report["layers"]["encode"] = {
        "format": "JPEG",
        "quality": cfg["jpeg_quality"],
        "subsampling": cfg["jpeg_subsampling"],
        "encodes": 1,
    }

    # --- final-byte QC -------------------------------------------------------
    qc = _final_qc(original, output_path)
    report["final_qc"] = qc

    floor_min_ssim = chosen["rung"]["min_ssim"]
    report["quality_floor_gate"] = {
        "preset": cfg["quality_floor"],
        "min_ssim": floor_min_ssim,
        "ssim": _num(chosen["metrics"].get("ssim_luma_window11_mean")),
        "psnr": _num(chosen["metrics"].get("psnr")),
        "accepted": bool(chosen["floor_ok"]),
        "output_long_edge": max(final_image.size),
        "beats_competitor_free_768": max(final_image.size) > 768,
    }
    if adaptive:
        report["detector_gate"] = {
            "evaluated": True,
            "cleared": bool(chosen["detector_ok"]),
            "ai_threshold": cfg["ai_threshold"],
            "rungs_tried": len(report["attempts"]),
            "note": None if chosen["detector_ok"] else "could_not_fully_clear_within_quality_floor_shipped_best_effort",
        }

    report["applied"] = True
    report["runtime_ms"] = int((time.time() - started) * 1000)
    return report


# ---------------------------------------------------------------------------
# Pipeline stages
# ---------------------------------------------------------------------------

def _sanitize_once(base, rung, seed, cfg):
    """Single consolidated shift+downscale (the whole removal mechanism)."""
    work = _shift_resample(
        base, rung["target_long_edge"], rung["degrid_shift"], cfg["resample_kernel"],
        np.random.default_rng(seed),
    )

    # Optional kernel-diverse bounce (off by default in v6).
    if rung["bounce"] < 1.0:
        w, h = work.size
        bw = max(1, int(round(w * rung["bounce"])))
        bh = max(1, int(round(h * rung["bounce"])))
        work = work.resize((bw, bh), Image.Resampling.BICUBIC).resize((w, h), Image.Resampling.LANCZOS)

    # Light spectral reshape at process resolution so adaptive detector probes
    # reflect near-final statistics (full strength re-applied at final res).
    if cfg["spectral_reshape"] and cfg["spectral_strength"] > 0:
        work = _fft_radial_amplitude_match(
            work,
            strength=cfg["spectral_strength"] * 0.5,
            alpha=cfg["spectral_alpha"],
            noise_floor=cfg["spectral_noise_floor"],
        )
    return work.convert("RGB")


def _shift_resample(image, target_long, degrid, kernel, rng):
    """Degrid sub-pixel shift + downscale.

    v5 chained subpixel_translate (BICUBIC transform) -> resize (LANCZOS) ->
    optional bounce, and then sharpened + added noise at the low resolution.
    PIL's transform() only offers non-antialiased kernels (BICUBIC sampling
    over 4x4 taps aliases badly on downscales), so the quality ceiling is:
    a near-lossless bilinear micro-shift at FULL resolution (a sub-pixel
    displacement attenuates only the very top frequencies) followed by ONE
    antialiased Lanczos downscale. The bounce is removed and no sharpen/noise
    happens at the process resolution anymore -- the v5 blur/crunch stack.
    """
    if degrid > 0:
        image = _subpixel_shift(image, rng, degrid)

    resample = (
        Image.Resampling.LANCZOS
        if kernel in ("ewi-lanczos", "lanczos")
        else Image.Resampling.BICUBIC
    )
    w, h = image.size
    long_edge = max(w, h)
    scale = target_long / float(long_edge)
    tw, th = max(1, int(round(w * scale))), max(1, int(round(h * scale)))
    return image.resize((tw, th), resample).convert("RGB")


def _subpixel_shift(image, rng, amount):
    """Bilinear sub-pixel shift at full resolution (near-lossless for
    |shift| <= ~1.2px)."""
    from photo_naturalization import bilinear_sample

    width, height = image.size
    shift_x = float(rng.uniform(-amount, amount))
    shift_y = float(rng.uniform(-amount, amount))
    pad = 4
    padded = np.asarray(edge_pad(image, pad)).astype(np.float32)
    src_y = np.arange(height, dtype=np.float32)[:, None] + pad + shift_y
    src_x = np.arange(width, dtype=np.float32)[None, :] + pad + shift_x
    sampled = bilinear_sample(padded, src_x, src_y)
    return Image.fromarray(np.clip(sampled + 0.5, 0, 255).astype(np.uint8), mode="RGB")


def _reconstruct(image, target_long, cfg):
    """Classical non-generative reconstruction: anti-ringing upscale + dehalo
    + single luma unsharp. Interpolation cannot re-create a destroyed
    fingerprint, and no neural model is involved, so nothing new is stamped."""
    w, h = image.size
    long_edge = max(w, h)
    if target_long <= long_edge:
        return image
    scale = target_long / float(long_edge)
    tw, th = max(1, int(round(w * scale))), max(1, int(round(h * scale)))

    # Plain Lanczos upscale; ringing is handled by the edge-masked dehalo
    # right after (a pre-blur would trade sharpness for a problem dehalo
    # already solves).
    up = image.resize((tw, th), Image.Resampling.LANCZOS)

    if cfg["dehalo_strength"] > 0:
        up = _dehalo(up, cfg["dehalo_strength"])
    if cfg["sharpen_percent"] > 0:
        up = _luma_unsharp(up, cfg["sharpen_percent"])
    return up.convert("RGB")


def _dehalo(image, strength):
    """Suppress thin overshoot halos around STRONG EDGES only.

    Halos are the classic GAN/SR tell and a quality defect at once. A global
    pull toward the local blur (v1 of this function) destroyed texture, so the
    correction is now masked to strong edges: flat areas and fine texture are
    untouched, while bright/dark overshoot bands around edges are compressed
    back toward the local mean."""
    if strength <= 0:
        return image
    arr = np.asarray(image).astype(np.float32)
    blurred_arr = np.asarray(
        image.filter(ImageFilter.GaussianBlur(radius=2.0))
    ).astype(np.float32)

    # Edge mask: where the luma deviates strongly from its 2px blur (real
    # edges), not texture-level wobble.
    gray = arr[..., 0] * 0.2126 + arr[..., 1] * 0.7152 + arr[..., 2] * 0.0722
    gray_blur = np.asarray(
        image.convert("L").filter(ImageFilter.GaussianBlur(radius=2.0))
    ).astype(np.float32)
    edge = np.clip((np.abs(gray - gray_blur) - 6.0) / 18.0, 0.0, 1.0)[..., None]

    over = arr - blurred_arr    # bright-side halo
    under = blurred_arr - arr   # dark-side halo
    corrected = arr - over * (strength * 0.55) * edge + under * (strength * 0.30) * edge
    return Image.fromarray(np.clip(corrected + 0.5, 0, 255).astype(np.uint8), mode="RGB")


def _luma_unsharp(image, percent):
    """Sharpening on the luminance channel only -- no chroma halos."""
    if percent <= 0:
        return image
    y, cb, cr = image.convert("YCbCr").split()
    y = y.filter(ImageFilter.UnsharpMask(radius=1.4, percent=percent, threshold=2))
    return Image.merge("YCbCr", (y, cb, cr)).convert("RGB")


def _masked_texture(image, rng, amount, texture_amount, vignette):
    """Sensor grain applied ONCE, at final resolution, strength-masked by local
    detail. Flat areas get a light anti-banding grain; textured areas get the
    full camera signature. Replaces v5's noise-at-process-res stack that
    upscaled into crunchy blobs."""
    luma = np.asarray(image.convert("L")).astype(np.float32)
    blurred = np.asarray(
        image.convert("L").filter(ImageFilter.GaussianBlur(radius=1.6))
    ).astype(np.float32)
    detail = np.abs(luma - blurred)
    t0, t1 = 2.5, 9.0
    mask = np.clip((detail - t0) / (t1 - t0), 0.0, 1.0)[..., None]

    light = np.asarray(apply_acquisition_noise_rgb(image, rng, amount * 0.35)).astype(np.float32)
    full = np.asarray(
        apply_acquisition_noise_rgb(image, rng, amount * texture_amount)
    ).astype(np.float32)
    blended = light * (1.0 - mask) + full * mask
    out = Image.fromarray(np.clip(blended + 0.5, 0, 255).astype(np.uint8), mode="RGB")
    if vignette > 0:
        out = apply_micro_vignette(out, vignette)
    return out


def _run_regen(input_path, output_path, cfg, seed):
    """Pre-regeneration reusing the proven ComfyUI purification pass that
    removed SynthID in the live test (adaptive_level 8). Raises on ComfyUI
    failure so the worker fails the job honestly rather than shipping a
    still-watermarked image."""
    from max_optimised_remint import _run_purification  # proven; ComfyUI-backed

    report = _run_purification(
        input_path=input_path,
        output_path=output_path,
        adaptive_level=cfg["regen_level"],
        process_cap=cfg["regen_process_cap"],
        timeout=cfg["regen_timeout"],
        seed=seed,
    )
    report["purpose"] = "break_synthid_carrier_before_laundering"
    return report


def _color_transfer(source, reference, strength):
    """Per-channel mean/std transfer (global stats only; no spatial copy)."""
    if strength <= 0.0:
        return source
    s = np.asarray(source).astype(np.float32)
    ref = reference if reference.size == source.size else reference.resize(
        source.size, Image.Resampling.LANCZOS
    )
    r = np.asarray(ref).astype(np.float32)
    out = s.copy()
    for c in range(3):
        s_mean, s_std = float(s[..., c].mean()), float(s[..., c].std()) + 1e-5
        r_mean, r_std = float(r[..., c].mean()), float(r[..., c].std()) + 1e-5
        matched = (s[..., c] - s_mean) * (r_std / s_std) + r_mean
        out[..., c] = s[..., c] * (1.0 - strength) + matched * strength
    return Image.fromarray(np.clip(out + 0.5, 0, 255).astype(np.uint8), mode="RGB")


# ---------------------------------------------------------------------------
# Detector gate (adaptive mode)
# ---------------------------------------------------------------------------

def _encode_probe(image, path):
    image.save(path, format="JPEG", quality=92, optimize=True, subsampling="4:2:0")


def _safe_detect(detector, path):
    try:
        result = detector(path)
        return result if isinstance(result, dict) else {"ok": False, "reason": "detector_returned_non_dict"}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "reason": f"detector_error: {str(exc)[:200]}"}


def _detector_pass(result, cfg):
    if not isinstance(result, dict) or result.get("ok") is False:
        return False
    ai = result.get("ai_probability")
    if ai is None:
        return False
    ai = float(ai)
    if ai > 1.0:  # normalize 0-100 -> 0-1
        ai = ai / 100.0
    if result.get("watermark_present") is True:
        return False
    return ai <= cfg["ai_threshold"]


# ---------------------------------------------------------------------------
# Rungs
# ---------------------------------------------------------------------------

def _rung_config(index, target, preset, cfg):
    """Escalation ladder: increase degrid + texture rungs first, then step the
    sanitize floor down as the last resort. Bounce stays off unless enabled."""
    acq = ACQUISITION_PRESETS[cfg["acquisition"]]
    ladder = [
        {"bounce": 1.00, "degrid": 0.6, "noise_mult": 1.00, "target_delta": 0},
        {"bounce": 1.00, "degrid": 0.8, "noise_mult": 1.10, "target_delta": 0},
        {"bounce": 1.00, "degrid": 1.0, "noise_mult": 1.25, "target_delta": -96},
        {"bounce": 1.00, "degrid": 1.0, "noise_mult": 1.35, "target_delta": -128},
        {"bounce": 1.00, "degrid": 1.2, "noise_mult": 1.50, "target_delta": -192},
    ]
    if cfg["bounce"]:
        for i, b in enumerate((1.00, 0.94, 0.88, 0.85, 0.82)):
            ladder[i]["bounce"] = b
    step = ladder[min(index, len(ladder) - 1)]
    rung_target = max(HARD_MIN_LONG_EDGE, target + step["target_delta"])
    return {
        "target_long_edge": rung_target,
        "bounce": step["bounce"],
        "degrid_shift": step["degrid"],
        "noise_mult": step["noise_mult"],
        "min_ssim": preset["min_ssim"],
    }


def _keep_better(current, candidate):
    if current is None:
        return candidate
    def rank(c):
        det = 1 if c.get("detector_ok") else 0
        ssim = float(c["metrics"].get("ssim_luma_window11_mean", 0.0))
        return (det, ssim, 1 if c.get("floor_ok") else 0)
    return candidate if rank(candidate) > rank(current) else current


# ---------------------------------------------------------------------------
# Final-byte QC
# ---------------------------------------------------------------------------

def _final_qc(original, output_path):
    out = Image.open(output_path).convert("RGB")
    src = original if original.size == out.size else original.resize(out.size, Image.Resampling.LANCZOS)
    metrics = compare_images(src, out)

    lap_out = _laplacian_variance(out)
    lap_src = _laplacian_variance(src)
    out_arr = np.asarray(out).astype(np.float32)
    src_arr = np.asarray(src).astype(np.float32)
    halo = float(np.maximum(out_arr - np.asarray(out.filter(ImageFilter.GaussianBlur(radius=2.0))).astype(np.float32), 0).mean() / 255.0)
    return {
        "psnr": _num(metrics.get("psnr")),
        "ssim_luma_window11_mean": _num(metrics.get("ssim_luma_window11_mean")),
        "sharpness_ratio": _num(lap_out / max(lap_src, 1e-6)),
        "laplacian_var_out": _num(lap_out),
        "laplacian_var_src": _num(lap_src),
        "halo_score": _num(halo),
        "blockiness_ratio": _num(_blockiness_ratio(out_arr)),
        "blockiness_ratio_src": _num(_blockiness_ratio(src_arr)),
        "output_size": list(out.size),
    }


def _laplacian_variance(image):
    lap = image.convert("L").filter(
        ImageFilter.Kernel((3, 3), [0, 1, 0, 1, -4, 1, 0, 1, 0], scale=1, offset=128)
    )
    arr = np.asarray(lap).astype(np.float32) - 128.0
    return float(arr.var())


def _blockiness_ratio(arr):
    """JPEG-grid blockiness: mean |diff| across 8x8 grid boundaries (4 offsets)
    divided by the global mean |diff|. Structures like fences score the same on
    boundary and off-boundary pixels, so the ratio stays near 1.0; true JPEG
    blocking pushes boundary differences above the background."""
    gray = (
        arr[..., 0].astype(np.float32) * 0.2126
        + arr[..., 1].astype(np.float32) * 0.7152
        + arr[..., 2].astype(np.float32) * 0.0722
    )
    dv = np.abs(np.diff(gray, axis=0))
    dh = np.abs(np.diff(gray, axis=1))
    boundary = []
    for offset in range(4):
        rows = np.arange(offset, dv.shape[0], 8)
        cols = np.arange(offset, dh.shape[1], 8)
        boundary.append(float(dv[rows].mean()) if rows.size else 0.0)
        boundary.append(float(dh[:, cols].mean()) if cols.size else 0.0)
    b_mean = float(np.mean(boundary))
    g_mean = max(float((dv.mean() + dh.mean()) / 2.0), 1e-6)
    return b_mean / g_mean


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _public_settings(cfg):
    return {k: cfg[k] for k in (
        "engine_mode", "quality_floor", "target_long_edge", "acquisition",
        "iphone_exif", "device", "resolution_mode", "x_resolution", "y_resolution",
        "pre_regen", "regen_level", "regen_process_cap", "regen_timeout",
        "spectral_reshape", "spectral_strength", "spectral_alpha", "spectral_noise_floor",
        "color_restore", "color_restore_strength", "color_restore_method",
        "resample_kernel", "bounce", "realism_boost",
        "output_target", "dehalo_strength", "sharpen_percent", "texture_amount",
        "jpeg_quality", "jpeg_subsampling", "ai_threshold", "max_rungs",
    )}


def _public_rung(rung):
    return {
        "target_long_edge": rung["target_long_edge"],
        "bounce": rung["bounce"],
        "degrid_shift": rung["degrid_shift"],
        "noise_mult": rung["noise_mult"],
    }


def _num(value):
    try:
        return round(float(value), 4)
    except (TypeError, ValueError):
        return None


def _clamp(value, low, high):
    try:
        v = float(value)
    except (TypeError, ValueError):
        return low
    if not np.isfinite(v):
        return low
    return max(low, min(high, v))


def _seed(creator_id, seed_extra, size, index):
    material = f"ds-remint-v6:{creator_id}:{seed_extra}:{size[0]}x{size[1]}:r{index}"
    return int(hashlib.sha256(material.encode("utf-8")).hexdigest()[:16], 16) & 0xFFFFFFFF
