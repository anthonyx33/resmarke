"""CX Remint -- non-generative "capture laundering" for false-flagged creator images.

The problem the earlier profiles could not solve (confirmed by live detector
tests against Hive / TruthScan):

  - Max Mint (full regen) DID clear the SynthID watermark decoder, but the VAE
    stamped a fresh *flux* fingerprint -- source-attribution and the general
    AI-vs-real classifier still fired (89.8% AI, flux 80.9%). Regeneration is a
    fingerprint SWAP, not a removal.
  - Max ReMint (non-generative statistical reshape) preserved quality but never
    broke the SynthID carrier (gemini3 99.8%).
  - Max Optimised Re Mint's premise that a MODERATE regen (adaptive_level 4)
    removes SynthID was refuted live: gemini3 99.7%. No moderate regen removes
    it; only a full-frame overwrite does, and that is exactly what re-flags.

CX Remint abandons regeneration entirely. It follows what the strongest
competitor (twotensors) demonstrably does -- destroy the watermark + diffusion
fingerprint at the SIGNAL level and re-acquire the image as a real camera
capture -- but three ways smarter so we don't ship the competitor's 768px mush:

  1. Carrier-breaking resample. A genuine downscale to a target long edge
     (default 1080 from ~2048 sources) with a de-grid pre-shift and an optional
     kernel-diverse "bounce". This disrupts the SynthID spatial carrier AND the
     grid-locked diffusion fingerprint -- non-generatively, so NOTHING new is
     stamped (the whole point).
  2. Structure-preserving restoration. Classical edge-aware sharpening recovers
     perceived detail the resample softened -- never a neural SR (that would
     re-add a fingerprint). This is the edge over a naive hard downscale.
  3. Camera re-acquisition. The existing optical-pro capture sim + full-spectrum
     acquisition noise give the high-frequency band a real-sensor signature so
     the general classifier reads "camera", not "AI" or "denoised-empty".
     Optional coherent iPhone EXIF (iphone_exif) rebuilds the metadata half.

Two run modes (both shipped, per product decision):
  - template : run once at the selected quality-floor preset. Fast, predictable,
               no detector calls. The hand-tuned path.
  - adaptive : escalate strength rung-by-rung against a REAL detector callable,
               stopping at the first rung that clears all three signals. Yields
               the minimum destruction -- hence highest quality -- that passes
               for THAT image. Closes the loop the old profiles never had: they
               gated on the local `identify` oracle, which cannot see pixel
               SynthID, so they passed locally and failed live.

Quality-floor slider (output long edge). The hard floor NEVER drops below 896px
-- strictly above twotensors' free-tier 768px output -- so even the most
aggressive rung stays better than the competitor's free result.
"""

import hashlib
import time
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

from neural_texture import compare_images
from photo_naturalization import (
    apply_acquisition_noise_rgb,
    apply_lens_character,
    apply_micro_vignette,
    apply_optical_pro_capture,
    subpixel_translate,
)
import iphone_exif


# Absolute output floor: always strictly greater than twotensors' free tier
# (768px). No preset and no adaptive rung may take the long edge below this.
HARD_MIN_LONG_EDGE = 896

# Quality-floor presets -> (target output long edge, matched-resolution SSIM
# floor). Higher target = more quality, weaker carrier break (adaptive may need
# more rungs). "balanced" (1080) is the product default.
QUALITY_FLOOR_PRESETS = {
    "studio":   {"target_long_edge": 1536, "min_ssim": 0.72, "label": "Studio (max quality)"},
    "high":     {"target_long_edge": 1280, "min_ssim": 0.70, "label": "High"},
    "balanced": {"target_long_edge": 1080, "min_ssim": 0.68, "label": "Balanced (recommended)"},
    "strong":   {"target_long_edge": 960,  "min_ssim": 0.64, "label": "Strong"},
    "floor":    {"target_long_edge": 896,  "min_ssim": 0.60, "label": "Floor (still > competitor free)"},
}

# Re-acquisition strength presets (how hard we push the camera signature).
ACQUISITION_PRESETS = {
    "conservative": {"noise": 0.12, "vignette": 0.10},
    "balanced":     {"noise": 0.18, "vignette": 0.14},
    "aggressive":   {"noise": 0.26, "vignette": 0.20},
}

DEFAULT_SETTINGS = {
    "enabled": True,
    "engine_mode": "template",        # "template" | "adaptive"
    "quality_floor": "balanced",      # key into QUALITY_FLOOR_PRESETS
    "target_long_edge": None,         # explicit override of the preset target
    "acquisition": "balanced",        # key into ACQUISITION_PRESETS
    "iphone_exif": True,              # coherent iPhone EXIF (user toggle)
    "device": "auto",                 # iphone_exif device key or "auto"
    # --- v2: pre-regeneration (the SynthID killer) ---------------------------
    # SynthID is robust by design: every non-generative pass we tried left it at
    # ~99% (Max ReMint, CX v1@896, Max Optimised L4). Only a full-frame VAE
    # regeneration actually removes it. v2 regenerates FIRST to break SynthID,
    # then the non-generative laundering below strips the diffusion (flux)
    # fingerprint the regen leaves -- which IS fragile, unlike SynthID. This is
    # the one combination the earlier profiles never assembled.
    "pre_regen": False,               # v2 sets True
    "regen_level": 8,                 # adaptive_level; 8 = the level that removed SynthID live
    "regen_process_cap": 1536,        # cap long edge fed to ComfyUI
    "regen_timeout": 300,
    # --- v2: FFT spectral reshaping (the statistical-classifier killer) -------
    # Phase-preserving reshape of the amplitude spectrum toward a real-camera
    # 1/f^alpha + noise-floor envelope. Attacks exactly what Hive's statistical
    # model reads (too-clean, too-steep diffusion spectrum). Non-generative.
    "spectral_reshape": False,        # v2 sets True
    "spectral_strength": 0.5,
    "spectral_alpha": 2.0,
    "spectral_noise_floor": 0.012,
    # --- v3: colour restoration (the quality fix) ----------------------------
    # Regeneration repaints the frame and shifts the palette away from the
    # original (the "colours drop, nowhere near nano banana" report). We transfer
    # the ORIGINAL's per-channel colour statistics (mean/std) onto the
    # regenerated structure. Global colour stats do NOT carry SynthID's spatial
    # pattern, so this restores the palette without re-importing the watermark.
    "color_restore": False,           # v3 sets True
    "color_restore_strength": 0.8,
    # v4: "histogram" matches the ORIGINAL's full per-channel tone distribution
    # (fixes the S-curve over-contrast + blown lights the regen adds, which
    # mean/std cannot). "mean_std" is the v3 behaviour.
    "color_restore_method": "mean_std",   # v4 sets "histogram"
    # v4: unsharp is the main contrast-adder in the laundering; lower it so the
    # restored tone is not re-hardened. v1-v3 effectively used 42.
    "sharpen_percent": 42,                # v4 sets ~24
    # v4: extra camera realism (grain + chroma aberration + vignette) to push a
    # general "looks-AI" classifier. Honest limit: the content is genuinely
    # AI-generated, so this reduces but may not zero such a detector.
    "realism_boost": 0.0,                 # v4 sets ~0.35 (0..1)
    # Final camera-like JPEG (a real edited iPhone JPEG, not a diffusion PNG).
    "jpeg_quality": 92,
    "jpeg_subsampling": "4:2:0",
    # Adaptive-only: detector pass thresholds.
    "ai_threshold": 0.50,             # ship if P(AI) <= this (0-1 scale)
    "max_rungs": 5,                   # escalation ladder length cap
}


def is_cx_remint(settings):
    return isinstance(settings, dict) and settings.get("mode") == "max-cx-remint"


def normalize_cx_remint_settings(settings):
    raw = settings if isinstance(settings, dict) else {}
    sub = raw.get("max_cx_remint") if isinstance(raw.get("max_cx_remint"), dict) else {}
    cfg = dict(DEFAULT_SETTINGS)
    cfg["enabled"] = raw.get("mode") == "max-cx-remint"

    engine_mode = str(sub.get("engine_mode", cfg["engine_mode"]))
    cfg["engine_mode"] = engine_mode if engine_mode in ("template", "adaptive") else "template"

    qf = str(sub.get("quality_floor", cfg["quality_floor"]))
    cfg["quality_floor"] = qf if qf in QUALITY_FLOOR_PRESETS else "balanced"

    acq = str(sub.get("acquisition", cfg["acquisition"]))
    cfg["acquisition"] = acq if acq in ACQUISITION_PRESETS else "balanced"

    if sub.get("target_long_edge") is not None:
        cfg["target_long_edge"] = max(HARD_MIN_LONG_EDGE, int(_clamp(sub["target_long_edge"], 64, 8192)))
    else:
        cfg["target_long_edge"] = None

    cfg["iphone_exif"] = bool(sub.get("iphone_exif", cfg["iphone_exif"]))
    cfg["device"] = str(sub.get("device", cfg["device"]))

    cfg["pre_regen"] = bool(sub.get("pre_regen", cfg["pre_regen"]))
    cfg["regen_level"] = int(_clamp(sub.get("regen_level", cfg["regen_level"]), 3, 10))
    cfg["regen_process_cap"] = int(_clamp(sub.get("regen_process_cap", cfg["regen_process_cap"]), 512, 4096))
    cfg["regen_timeout"] = int(_clamp(sub.get("regen_timeout", cfg["regen_timeout"]), 30, 900))
    cfg["spectral_reshape"] = bool(sub.get("spectral_reshape", cfg["spectral_reshape"]))
    cfg["spectral_strength"] = float(_clamp(sub.get("spectral_strength", cfg["spectral_strength"]), 0.0, 1.0))
    cfg["spectral_alpha"] = float(_clamp(sub.get("spectral_alpha", cfg["spectral_alpha"]), 0.5, 4.0))
    cfg["spectral_noise_floor"] = float(_clamp(sub.get("spectral_noise_floor", cfg["spectral_noise_floor"]), 0.0, 0.2))
    cfg["color_restore"] = bool(sub.get("color_restore", cfg["color_restore"]))
    cfg["color_restore_strength"] = float(_clamp(sub.get("color_restore_strength", cfg["color_restore_strength"]), 0.0, 1.0))
    method = str(sub.get("color_restore_method", cfg["color_restore_method"]))
    cfg["color_restore_method"] = method if method in ("mean_std", "histogram") else "mean_std"
    cfg["sharpen_percent"] = int(_clamp(sub.get("sharpen_percent", cfg["sharpen_percent"]), 0, 200))
    cfg["realism_boost"] = float(_clamp(sub.get("realism_boost", cfg["realism_boost"]), 0.0, 1.0))

    cfg["jpeg_quality"] = int(_clamp(sub.get("jpeg_quality", cfg["jpeg_quality"]), 60, 100))
    sub_sampling = sub.get("jpeg_subsampling", cfg["jpeg_subsampling"])
    cfg["jpeg_subsampling"] = sub_sampling if sub_sampling in ("4:2:0", "4:2:2", "4:4:4") else "4:2:0"
    cfg["ai_threshold"] = float(_clamp(sub.get("ai_threshold", cfg["ai_threshold"]), 0.0, 1.0))
    cfg["max_rungs"] = int(_clamp(sub.get("max_rungs", cfg["max_rungs"]), 1, 8))
    return cfg


def apply_cx_remint(input_path, output_path, creator_id, settings=None, seed_extra="", detector=None):
    """Non-generative de-flag + camera re-acquisition. Writes the final JPEG
    (with iPhone EXIF when enabled) to output_path and returns a report.

    detector: optional callable(path)->dict used only in adaptive mode. Expected
    keys: ai_probability (0-1 or 0-100), watermark_present (bool),
    sources (dict, optional). If None in adaptive mode, we degrade to a single
    template run and say so in the report (no blind escalation).
    """
    cfg = normalize_cx_remint_settings(settings)
    report = {
        "enabled": bool(cfg["enabled"]),
        "pipeline": "cx_remint_v2" if cfg["pre_regen"] else "cx_remint_v1",
        "engine": "cx_remint",
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

    # --- v2 layer 0: pre-regeneration (SynthID killer). --------------------
    # Runs BEFORE the laundering so the rest of the pipeline operates on a
    # SynthID-free frame and only has to strip the (fragile) diffusion
    # fingerprint the regen introduces. base = what we launder + measure
    # against; the true original is kept only for a transparency metric.
    base = original
    if cfg["pre_regen"]:
        regen_path = Path(output_path).with_name(".cx-remint-regen.png")
        try:
            regen_report = _run_regen(input_path, str(regen_path), cfg,
                                      _seed(creator_id, seed_extra, original.size, 900))
            base = Image.open(regen_path).convert("RGB")
            report["layers"]["pre_regeneration"] = regen_report
        finally:
            try:
                Path(regen_path).unlink()
            except OSError:
                pass

        # v3 colour restoration: pull the regen's palette back to the original's
        # (global colour stats only -> restores nano-banana look, no SynthID
        # re-import). Runs on the regen output before laundering.
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

    src_long = max(base.size)

    preset = QUALITY_FLOOR_PRESETS[cfg["quality_floor"]]
    target = cfg["target_long_edge"] or preset["target_long_edge"]
    # Never upscale, never exceed source; never below the hard floor unless the
    # source itself is already smaller than the floor.
    target = min(target, src_long)
    target = max(target, min(HARD_MIN_LONG_EDGE, src_long))
    report["source_long_edge"] = src_long
    report["target_long_edge"] = target

    adaptive = cfg["engine_mode"] == "adaptive"
    if adaptive and detector is None:
        report["detector_gate"]["note"] = "no_detector_supplied_degraded_to_single_template_run"
        adaptive = False

    rung_count = cfg["max_rungs"] if adaptive else 1
    chosen = None
    for rung_index in range(rung_count):
        rung = _rung_config(rung_index, target, preset, cfg)
        seed = _seed(creator_id, seed_extra, base.size, rung_index)
        candidate = _process_once(base, rung, seed, cfg)

        # Gate on laundering damage vs the base (regen output for v2, original
        # for v1) -- that is what the laundering is allowed to degrade.
        metrics = compare_images(base.resize(candidate.size, Image.Resampling.LANCZOS), candidate)
        floor_ok = float(metrics.get("ssim_luma_window11_mean", 0.0)) >= rung["min_ssim"]

        attempt = {
            "rung": rung_index,
            "params": _public_rung(rung),
            "metrics": {"psnr": _num(metrics.get("psnr")), "ssim": _num(metrics.get("ssim_luma_window11_mean"))},
            "quality_floor_ok": floor_ok,
        }

        detector_ok = None
        if adaptive:
            probe_path = str(Path(output_path).with_name(".cx-remint-probe.jpg"))
            _encode(candidate, probe_path, creator_id, seed_extra, cfg, embed_exif=cfg["iphone_exif"])
            det = _safe_detect(detector, probe_path)
            detector_ok = _detector_pass(det, cfg)
            attempt["detector"] = det
            attempt["detector_ok"] = detector_ok
            try:
                Path(probe_path).unlink()
            except OSError:
                pass

        report["attempts"].append(attempt)

        # Keep the best candidate we have seen so far (prefer detector pass, then
        # the highest-quality rung). Ensures we never ship worse than needed.
        chosen = _keep_better(chosen, {"image": candidate, "metrics": metrics, "rung": rung,
                                       "detector_ok": detector_ok, "floor_ok": floor_ok})

        if not adaptive:
            break
        if detector_ok and floor_ok:
            break  # minimum destruction that clears -> stop, this is max quality

    final_image = chosen["image"]
    final_metrics = chosen["metrics"]

    # v4 final tone lock: the laundering (unsharp/optical/spectral) re-hardens
    # contrast AFTER the post-regen colour restore, which is what still reads as
    # "over-contrasted". Re-match the finished frame's tone to the original as
    # the LAST pixel step so the output tone equals the creator's, regardless of
    # what the laundering did. Preserves the added grain (per-pixel remap only).
    if cfg["color_restore"] and cfg["pre_regen"]:
        original_ref = original if original.size == final_image.size else original.resize(
            final_image.size, Image.Resampling.LANCZOS
        )
        if cfg["color_restore_method"] == "histogram":
            final_image = _histogram_match(final_image, original_ref, cfg["color_restore_strength"])
        else:
            final_image = _color_transfer(final_image, original_ref, cfg["color_restore_strength"])
        report["layers"]["final_tone_lock"] = {
            "method": cfg["color_restore_method"],
            "strength": cfg["color_restore_strength"],
        }

    exif_report = {"enabled": False}
    if cfg["iphone_exif"]:
        _, exif_report = iphone_exif.build_iphone_exif(
            final_image.width, final_image.height, creator_id, seed_extra, device=cfg["device"]
        )
    _encode(final_image, output_path, creator_id, seed_extra, cfg, embed_exif=cfg["iphone_exif"])

    report["layers"]["carrier_break"] = {
        "method": "degrid_shift + downscale + kernel_diverse_bounce",
        "non_generative": True,
        "output_long_edge": max(final_image.size),
    }
    report["layers"]["structure_restoration"] = {"method": "edge_aware_unsharp", "non_generative": True}
    report["layers"]["camera_reacquisition"] = {
        "method": "optical_pro_capture + acquisition_noise_rgb + micro_vignette",
        "non_generative": True,
    }
    report["layers"]["iphone_exif"] = exif_report

    floor_min_ssim = chosen["rung"]["min_ssim"]
    report["quality_floor_gate"] = {
        "preset": cfg["quality_floor"],
        "min_ssim": floor_min_ssim,
        "ssim": _num(final_metrics.get("ssim_luma_window11_mean")),
        "psnr": _num(final_metrics.get("psnr")),
        "matched_resolution": True,
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
# Pipeline
# ---------------------------------------------------------------------------

def _process_once(base, rung, seed, cfg):
    rng = np.random.default_rng(seed)
    work = base.copy()

    # 1. De-grid pre-shift: break the watermark/diffusion grid alignment.
    work, _sx, _sy = subpixel_translate(work, rng, amount=rung["degrid_shift"])

    # 2. Carrier-breaking downscale to target long edge (the removal mechanism).
    work = _resize_long_edge(work, rung["target_long_edge"], Image.Resampling.LANCZOS)

    # 3. Kernel-diverse bounce (optional, stronger rungs): down then back up at
    #    fixed dims with mismatched kernels to further disrupt the grid.
    if rung["bounce"] < 1.0:
        w, h = work.size
        bw = max(1, int(round(w * rung["bounce"])))
        bh = max(1, int(round(h * rung["bounce"])))
        work = work.resize((bw, bh), Image.Resampling.BICUBIC).resize((w, h), Image.Resampling.LANCZOS)

    # 4. Structure-preserving restoration (classical, non-generative).
    work = work.filter(ImageFilter.UnsharpMask(radius=1.1, percent=rung["sharpen"], threshold=2))

    # 5. Spectral reshape (v2): pull the amplitude spectrum toward a real-camera
    #    1/f^alpha + noise-floor envelope. Phase-preserving, non-generative.
    #    This is what neutralises the diffusion "too-clean spectrum" the general
    #    AI classifier keys on, on top of the regen that killed SynthID.
    if cfg.get("spectral_reshape") and cfg.get("spectral_strength", 0.0) > 0:
        work = _fft_radial_amplitude_match(
            work,
            strength=cfg["spectral_strength"],
            alpha=cfg["spectral_alpha"],
            noise_floor=cfg["spectral_noise_floor"],
        )

    # 6. Camera re-acquisition: real optical + sensor signature.
    optical, _optical_report = apply_optical_pro_capture(work, rng)
    work = optical
    work = apply_acquisition_noise_rgb(work, rng, amount=rung["noise"])
    if rung["vignette"] > 0:
        work = apply_micro_vignette(work, rung["vignette"])

    # 7. v4 realism boost: extra sensor grain + lens chromatic aberration +
    #    vignette, to push a general "looks-AI" classifier toward "camera". Off
    #    unless realism_boost > 0. Honest limit: cannot make genuinely
    #    AI-generated content read as fully real without more destruction.
    if rung.get("realism", 0.0) > 0:
        r = rung["realism"]
        work = apply_lens_character(work, amount=0.35 * r)
        work = apply_acquisition_noise_rgb(work, rng, amount=0.18 * r)
        work = apply_micro_vignette(work, amount=0.5 * r)

    return work.convert("RGB")


def _run_regen(input_path, output_path, cfg, seed):
    """v2 pre-regeneration. Reuses the SAME proven ComfyUI purification pass that
    Max Optimised Re Mint runs in production (single VAE round-trip at a given
    adaptive_level, original resolution restored). At regen_level 8 this is the
    pass that removed SynthID in the live test. Raises on ComfyUI failure so the
    worker fails the job honestly rather than shipping a still-watermarked image.
    """
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
    """Match `source`'s per-channel mean/std to `reference` (classic global
    colour transfer). Reference is resized to the source grid first. Only global
    per-channel statistics move -- no spatial content is copied, so the
    reference's SynthID spatial pattern is NOT re-introduced. `strength` blends
    the corrected result with the source (1.0 = full match)."""
    if strength <= 0.0:
        return source
    s = np.asarray(source).astype(np.float32)
    ref = reference if reference.size == source.size else reference.resize(source.size, Image.Resampling.LANCZOS)
    r = np.asarray(ref).astype(np.float32)
    out = s.copy()
    for c in range(3):
        s_mean, s_std = float(s[..., c].mean()), float(s[..., c].std()) + 1e-5
        r_mean, r_std = float(r[..., c].mean()), float(r[..., c].std()) + 1e-5
        matched = (s[..., c] - s_mean) * (r_std / s_std) + r_mean
        out[..., c] = s[..., c] * (1.0 - strength) + matched * strength
    return Image.fromarray(np.clip(out + 0.5, 0, 255).astype(np.uint8), mode="RGB")


def _histogram_match(source, reference, strength):
    """Match `source`'s full per-channel tone distribution (CDF) to `reference`.
    Unlike mean/std transfer, this corrects the tone-CURVE shape -- the S-curve
    over-contrast and blown highlights regeneration adds -- not just the mean and
    spread. Reference is resized to source first; only per-channel intensity
    remapping happens (no spatial copy), so SynthID's spatial pattern is not
    re-imported. `strength` blends toward the match (1.0 = full)."""
    if strength <= 0.0:
        return source
    s = np.asarray(source)
    ref = reference if reference.size == source.size else reference.resize(source.size, Image.Resampling.LANCZOS)
    r = np.asarray(ref)
    out = s.astype(np.float32).copy()
    for c in range(3):
        s_ch = s[..., c].ravel()
        r_ch = r[..., c].ravel()
        s_vals, s_inv, s_counts = np.unique(s_ch, return_inverse=True, return_counts=True)
        r_vals, r_counts = np.unique(r_ch, return_counts=True)
        s_cdf = np.cumsum(s_counts).astype(np.float64) / s_ch.size
        r_cdf = np.cumsum(r_counts).astype(np.float64) / r_ch.size
        mapped_vals = np.interp(s_cdf, r_cdf, r_vals.astype(np.float64))
        matched = mapped_vals[s_inv].reshape(s[..., c].shape).astype(np.float32)
        out[..., c] = s[..., c].astype(np.float32) * (1.0 - strength) + matched * strength
    return Image.fromarray(np.clip(out + 0.5, 0, 255).astype(np.uint8), mode="RGB")


def _fft_radial_amplitude_match(image, strength, alpha, noise_floor):
    """Reshape each channel's amplitude spectrum toward a real-camera
    1/f^alpha + noise-floor envelope, phase-preserving (spatial structure kept).

    Ported from max_remint.fft_radial_amplitude_match. AI images tend to have a
    too-steep, too-clean radial amplitude falloff; real sensors carry a shallower
    falloff plus a high-frequency noise floor. Blending the input's radial
    amplitude profile toward that target attacks the statistical AI classifier
    without regenerating anything.
    """
    if strength <= 0.0:
        return image
    arr = np.asarray(image).astype(np.float32)
    h, w, _ = arr.shape
    cy, cx = h / 2.0, w / 2.0
    yy, xx = np.indices((h, w))
    dist = np.sqrt(((yy - cy) / max(cy, 1.0)) ** 2 + ((xx - cx) / max(cx, 1.0)) ** 2).astype(np.float32)
    max_r = float(dist.max())
    n_bins = max(8, min(96, int(max_r * 64)))
    bin_idx = np.clip((dist / max(max_r, 1e-6) * n_bins).astype(np.int32), 0, n_bins - 1)

    out = np.empty_like(arr)
    for c in range(arr.shape[2]):
        plane = arr[..., c]
        f = np.fft.fftshift(np.fft.fft2(plane))
        mag = np.abs(f).astype(np.float32)
        phase = np.angle(f).astype(np.float32)
        bin_sum = np.bincount(bin_idx.ravel(), weights=mag.ravel(), minlength=n_bins)
        bin_cnt = np.bincount(bin_idx.ravel(), minlength=n_bins).astype(np.float32)
        bin_cnt[bin_cnt == 0] = 1.0
        radial_in = (bin_sum / bin_cnt).astype(np.float32)

        d_bins = np.linspace(0.0, max_r, n_bins, dtype=np.float32)
        target_raw = 1.0 / (d_bins + 1.0) ** alpha + noise_floor
        low_ref = max(radial_in[0], 1e-6)
        tgt_low = max(target_raw[0], 1e-6)
        target = target_raw * (low_ref / tgt_low)

        scale = np.ones_like(radial_in)
        nz = radial_in > 1e-8
        # Tighter clamp than max_remint's [0.25, 4.0]: CX applies this AFTER a
        # regen + resample, so we only want a gentle nudge of the falloff shape,
        # never a magnitude swing large enough to ring edges / crush contrast.
        scale[nz] = np.clip(target[nz] / radial_in[nz], 0.6, 1.7)
        scale = _smooth(scale, passes=3)

        scale_plane = scale[bin_idx]
        blended_mag = (1.0 - strength) * mag + strength * (mag * scale_plane)
        new_f = blended_mag * np.exp(1j * phase)
        out[..., c] = np.real(np.fft.ifft2(np.fft.ifftshift(new_f)))

    return Image.fromarray(np.clip(out + 0.5, 0, 255).astype(np.uint8), mode="RGB")


def _smooth(values, passes=2):
    smoothed = values.astype(np.float32).copy()
    for _ in range(max(0, passes)):
        padded = np.pad(smoothed, (1, 1), mode="edge")
        smoothed = (padded[:-2] + padded[1:-1] + padded[2:]) / 3.0
    return smoothed


def _rung_config(index, target, preset, cfg):
    """Escalation ladder. Rung 0 is the gentlest (max quality) for the chosen
    preset; higher rungs increase carrier disruption and re-acquisition, then as
    a last resort step the target down toward the hard floor."""
    acq = ACQUISITION_PRESETS[cfg["acquisition"]]
    ladder = [
        {"bounce": 1.00, "degrid": 0.6, "noise_mult": 1.00, "target_delta": 0},
        {"bounce": 0.94, "degrid": 0.8, "noise_mult": 1.12, "target_delta": 0},
        {"bounce": 0.88, "degrid": 1.0, "noise_mult": 1.28, "target_delta": 0},
        {"bounce": 0.85, "degrid": 1.0, "noise_mult": 1.40, "target_delta": -128},
        {"bounce": 0.82, "degrid": 1.2, "noise_mult": 1.55, "target_delta": -192},
    ]
    step = ladder[min(index, len(ladder) - 1)]
    rung_target = max(HARD_MIN_LONG_EDGE, target + step["target_delta"])
    return {
        "target_long_edge": rung_target,
        "bounce": step["bounce"],
        "degrid_shift": step["degrid"],
        "noise": acq["noise"] * step["noise_mult"],
        "vignette": acq["vignette"],
        "sharpen": cfg["sharpen_percent"],
        "realism": cfg["realism_boost"],
        "min_ssim": preset["min_ssim"],
    }


def _keep_better(current, candidate):
    if current is None:
        return candidate
    # Prefer a detector pass; among equal detector status prefer higher SSIM
    # (higher quality). floor_ok breaks remaining ties.
    def rank(c):
        det = 1 if c.get("detector_ok") else 0
        ssim = float(c["metrics"].get("ssim_luma_window11_mean", 0.0))
        return (det, ssim, 1 if c.get("floor_ok") else 0)
    return candidate if rank(candidate) > rank(current) else current


def _encode(image, path, creator_id, seed_extra, cfg, embed_exif):
    if embed_exif:
        exif_bytes, _ = iphone_exif.build_iphone_exif(
            image.width, image.height, creator_id, seed_extra, device=cfg["device"]
        )
        iphone_exif.write_exif_jpeg(image, path, exif_bytes, cfg["jpeg_quality"], cfg["jpeg_subsampling"])
    else:
        image.save(path, format="JPEG", quality=cfg["jpeg_quality"], optimize=True,
                   subsampling=cfg["jpeg_subsampling"])


# ---------------------------------------------------------------------------
# Detector gate (adaptive mode)
# ---------------------------------------------------------------------------

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
    if ai > 1.0:  # normalize a 0-100 score to 0-1
        ai = ai / 100.0
    if result.get("watermark_present") is True:
        return False
    return ai <= cfg["ai_threshold"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resize_long_edge(image, target_long, resample):
    w, h = image.size
    long_edge = max(w, h)
    if long_edge == target_long:
        return image
    scale = target_long / float(long_edge)
    return image.resize((max(1, int(round(w * scale))), max(1, int(round(h * scale)))), resample)


def _public_settings(cfg):
    return {k: cfg[k] for k in (
        "engine_mode", "quality_floor", "target_long_edge", "acquisition",
        "iphone_exif", "device", "jpeg_quality", "jpeg_subsampling",
        "ai_threshold", "max_rungs",
        "pre_regen", "regen_level", "regen_process_cap", "regen_timeout",
        "spectral_reshape", "spectral_strength", "spectral_alpha", "spectral_noise_floor",
        "color_restore", "color_restore_strength", "color_restore_method",
        "sharpen_percent", "realism_boost",
    )}


def _public_rung(rung):
    return {
        "target_long_edge": rung["target_long_edge"],
        "bounce": rung["bounce"],
        "degrid_shift": rung["degrid_shift"],
        "noise": round(rung["noise"], 4),
        "vignette": rung["vignette"],
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


def _seed(creator_id, seed_extra, size, rung_index):
    material = f"cx-remint:{creator_id}:{seed_extra}:{size[0]}x{size[1]}:r{rung_index}"
    return int(hashlib.sha256(material.encode("utf-8")).hexdigest()[:16], 16) & 0xFFFFFFFF
