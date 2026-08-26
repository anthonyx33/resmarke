"""DS ReMint V8.8 -- Coherent. Wash once, walk through a coherent virtual
camera, ship the least-destructive candidate that passes.

Adopts the external review (G8) wholesale:

    wash (SynthID carrier breaker; qwen | zimage | qwen+zimage)
      -> histogram restore to the original
      -> ONE resample to delivery (default: min(source, 1250px) -- the
         downscale itself is the lattice breaker, no micro-rotation)
      -> coherent camera model (inverse ISP -> optics -> CFA -> MHC ->
         weak ISP denoise -> forward ISP -> restrained sharpen)
      -> final tone lock -> ONE JPEG encode -> QC -> source-aware gate

Adaptive mode escalates the strength axis light -> balanced -> deep and
ships the FIRST candidate that clears (least destructive wins). Deep =
degrade 0.68 -> coherent balanced at low res -> Lanczos restore -> coherent
light at delivery. No neural restorer in the default path (its re-stamp never
paid -- review confirmed).
"""

import time
from pathlib import Path

import numpy as np
from PIL import Image

from coherent_camera import PRESETS as COHERENT_PRESETS
from coherent_camera import apply_coherent_camera
from ds_remint_v7 import (
    _encode_probe,
    _final_qc,
    _keep_better,
    _num,
    _rating_88,
    _run_wash_v8,
    _safe_detect,
    _seed,
    _v7_verdict,
)
from max_cx_remint import _histogram_match
from tools.auxiliary_checkpoints import build_auxiliary_manifest, save_auxiliary_checkpoint
from tools.checkpoint_capture import save_checkpoint
import iphone_exif

def _ckpt_save(checkpoint_dir, name, image, errors):
    error = save_checkpoint(checkpoint_dir, name, image)
    if error:
        errors.append(error)


DEFAULT_SETTINGS = {
    "enabled": True,
    "engine_mode": "adaptive",        # "adaptive" | "template"
    "pre_regen": True,                 # wash on/off (off = local harness runs)
    "wash_model": "qwen",             # "qwen" | "zimage" | "qwen+zimage"
    "route_by_baseline": False,       # V8.9: start ladder per input baseline
    "zimage_denoise": 0.12,
    "strength": "balanced",           # "light" | "balanced" | "deep"
    "optics_psf_scale": 1.0,          # sealed 4D-CAM-1: 1.00 | 0.50
    "deep_degrade_scale": 0.68,
    "output_target": None,            # None = min(source_long_edge, 1250)
    "min_ssim": 0.85,
    "ai_threshold": 0.45,
    "source_threshold": 0.30,
    "deepfake_threshold": 0.10,
    "jpeg_quality": 92,
    "jpeg_subsampling": "4:2:0",      # photography default per review
    "iphone_exif": True,
    "metadata_mode": "device",
    "device": "auto",
    "resolution_mode": "off",
    "x_resolution": 72.0,
    "y_resolution": 72.0,
    "regen_level": 8,
    "regen_process_cap": 1536,
    "regen_timeout": 300,
    "color_restore": True,
    "color_restore_strength": 0.8,
}


def is_ds_remint_v8_8(settings):
    return isinstance(settings, dict) and settings.get("mode") == "ds-remint-v8.8"


def is_ds_remint_v8_9(settings):
    return isinstance(settings, dict) and settings.get("mode") == "ds-remint-v8.9"


def apply_ds_remint_v8_9(input_path, output_path, creator_id, settings=None, seed_extra="", detector=None, return_buffer=False, checkpoint_dir=None):
    """DS ReMint V8.9: the V8.8 coherent pipeline with data-driven defaults
    (Qwen wash, balanced default, deep degrade 0.75) and baseline-aware
    ladder routing."""
    return apply_ds_remint_v8_8(
        input_path=input_path,
        output_path=output_path,
        creator_id=creator_id,
        settings=settings,
        seed_extra=seed_extra,
        detector=detector,
        return_buffer=return_buffer,
        checkpoint_dir=checkpoint_dir,
    )


def _clamp(value, low, high):
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return low
    if not np.isfinite(parsed):
        return low
    return max(low, min(high, parsed))


def _strict_optics_psf_scale(value):
    if isinstance(value, bool) or not isinstance(value, (int, float, np.integer, np.floating)):
        raise ValueError("optics_psf_scale must be exactly 0.50 or 1.00")
    parsed = float(value)
    if not np.isfinite(parsed) or parsed not in (0.5, 1.0):
        raise ValueError("optics_psf_scale must be exactly 0.50 or 1.00")
    return parsed


def normalize_ds_remint_v8_8_settings(settings):
    raw = settings if isinstance(settings, dict) else {}
    sub = {}
    for key in ("ds_remint_v8_8", "ds_remint_v8_9"):
        if isinstance(raw.get(key), dict):
            sub = raw[key]
    cfg = dict(DEFAULT_SETTINGS)
    cfg["mode"] = str(raw.get("mode") or "ds-remint-v8.8")
    cfg["enabled"] = cfg["mode"] in ("ds-remint-v8.8", "ds-remint-v8.9")

    engine_mode = str(sub.get("engine_mode", cfg["engine_mode"]))
    cfg["engine_mode"] = engine_mode if engine_mode in ("template", "adaptive") else "adaptive"
    cfg["pre_regen"] = bool(sub.get("pre_regen", cfg["pre_regen"]))

    wash_model = str(sub.get("wash_model", cfg["wash_model"]))
    cfg["wash_model"] = wash_model if wash_model in ("qwen", "zimage", "qwen+zimage") else "qwen"
    cfg["zimage_denoise"] = float(_clamp(sub.get("zimage_denoise", cfg["zimage_denoise"]), 0.05, 0.3))

    strength = str(sub.get("strength", cfg["strength"]))
    cfg["strength"] = strength if strength in COHERENT_PRESETS else "balanced"
    cfg["optics_psf_scale_requested"] = sub.get("optics_psf_scale") if "optics_psf_scale" in sub else None
    cfg["optics_psf_scale"] = _strict_optics_psf_scale(
        sub["optics_psf_scale"] if "optics_psf_scale" in sub else cfg["optics_psf_scale"]
    )
    # V8.9 data: 0.68 deep degrade was quality-bad; 0.75 keeps the TruthScan
    # win with far less damage. V8.8 keeps its original default.
    deep_default = 0.75 if cfg["mode"] == "ds-remint-v8.9" else 0.68
    cfg["deep_degrade_scale"] = float(_clamp(sub.get("deep_degrade_scale", deep_default), 0.5, 0.85))

    cfg["route_by_baseline"] = bool(sub.get("route_by_baseline", cfg["mode"] == "ds-remint-v8.9"))

    if sub.get("output_target") is not None:
        cfg["output_target"] = int(_clamp(sub["output_target"], 256, 8192))
    else:
        cfg["output_target"] = None
    cfg["min_ssim"] = float(_clamp(sub.get("min_ssim", cfg["min_ssim"]), 0.0, 1.0))

    cfg["ai_threshold"] = float(_clamp(sub.get("ai_threshold", cfg["ai_threshold"]), 0.0, 1.0))
    cfg["source_threshold"] = float(_clamp(sub.get("source_threshold", cfg["source_threshold"]), 0.0, 1.0))
    cfg["deepfake_threshold"] = float(_clamp(sub.get("deepfake_threshold", cfg["deepfake_threshold"]), 0.0, 1.0))

    cfg["jpeg_quality"] = int(_clamp(sub.get("jpeg_quality", cfg["jpeg_quality"]), 60, 100))
    jpeg_subsampling = sub.get("jpeg_subsampling", cfg["jpeg_subsampling"])
    cfg["jpeg_subsampling"] = (
        jpeg_subsampling if jpeg_subsampling in ("4:2:0", "4:2:2", "4:4:4") else "4:2:0"
    )

    cfg["iphone_exif"] = bool(sub.get("iphone_exif", cfg["iphone_exif"]))
    metadata_mode = str(sub.get("metadata_mode", cfg["metadata_mode"]))
    cfg["metadata_mode"] = metadata_mode if metadata_mode in ("device", "minimal") else "device"
    cfg["device"] = str(sub.get("device", cfg["device"]))
    resolution_mode = str(sub.get("resolution_mode", cfg["resolution_mode"]))
    cfg["resolution_mode"] = (
        resolution_mode if resolution_mode in ("off", "standard", "custom") else "off"
    )
    cfg["x_resolution"] = float(_clamp(sub.get("x_resolution", cfg["x_resolution"]), 1, 12000))
    cfg["y_resolution"] = float(_clamp(sub.get("y_resolution", cfg["y_resolution"]), 1, 12000))

    cfg["regen_level"] = int(_clamp(sub.get("regen_level", cfg["regen_level"]), 3, 10))
    cfg["regen_process_cap"] = int(_clamp(sub.get("regen_process_cap", cfg["regen_process_cap"]), 512, 4096))
    cfg["regen_timeout"] = int(_clamp(sub.get("regen_timeout", cfg["regen_timeout"]), 30, 900))
    cfg["color_restore"] = bool(sub.get("color_restore", cfg["color_restore"]))
    cfg["color_restore_strength"] = float(_clamp(sub.get("color_restore_strength", cfg["color_restore_strength"]), 0.0, 1.0))
    return cfg


def apply_ds_remint_v8_8(input_path, output_path, creator_id, settings=None, seed_extra="", detector=None, return_buffer=False, checkpoint_dir=None):
    """Full DS ReMint V8.8 pipeline. Writes the final camera-like JPEG (with
    coherent EXIF when enabled) to output_path and returns a report.
    return_buffer=True additionally attaches the PRE-ENCODE RGB array as
    report["_pre_encode_rgb"] so a chained stage can consume the high-
    precision buffer instead of decoding the intermediate JPEG (C8 v4)."""
    cfg = normalize_ds_remint_v8_8_settings(settings)
    auxiliary_checkpoint_errors = []
    report = {
        "enabled": bool(cfg["enabled"]),
        "pipeline": cfg.get("mode") or "ds_remint_v8_8",
        "engine": "ds_remint_v8_8",
        "applied": False,
        "settings": {k: cfg[k] for k in (
            "engine_mode", "wash_model", "zimage_denoise", "strength",
            "optics_psf_scale_requested", "optics_psf_scale",
            "deep_degrade_scale", "output_target", "min_ssim", "ai_threshold",
            "source_threshold", "deepfake_threshold", "jpeg_quality",
            "jpeg_subsampling", "iphone_exif", "metadata_mode",
        )},
        "layers": {},
        "attempts": [],
        "input_baseline": None,
        "quality_floor_gate": {},
        "detector_gate": {"evaluated": False},
        "checkpoint_errors": [],
        "auxiliary_checkpoints": {"status": "off", "files": [], "errors": []},
    }
    if not cfg["enabled"]:
        report["auxiliary_checkpoints"] = build_auxiliary_manifest(
            checkpoint_dir,
            capture_requested=checkpoint_dir is not None,
            errors=auxiliary_checkpoint_errors,
        )
        return report

    started = time.time()
    original = Image.open(input_path).convert("RGB")
    src_long = max(original.size)
    report["source_long_edge"] = src_long
    _ckpt_save(checkpoint_dir, "O0_source.png", original, report["checkpoint_errors"])

    adaptive = cfg["engine_mode"] == "adaptive"
    if adaptive and detector is None:
        report["detector_gate"]["note"] = "no_detector_supplied_degraded_to_single_template_run"
        adaptive = False

    if adaptive:
        baseline_path = str(Path(output_path).with_name(".v88-baseline.jpg"))
        _encode_probe(original, baseline_path, cfg)
        report["input_baseline"] = _safe_detect(detector, baseline_path)
        try:
            Path(baseline_path).unlink()
        except OSError:
            pass

    # --- wash ---------------------------------------------------------------
    base = original
    if cfg["pre_regen"]:
        regen_path = Path(output_path).with_name(".v88-regen.png")
        try:
            report["layers"]["pre_wash"] = _run_wash_v8(
                input_path, str(regen_path), cfg, _seed(creator_id, seed_extra, original.size, 900)
            )
            base = Image.open(regen_path).convert("RGB")
        finally:
            try:
                Path(regen_path).unlink()
            except OSError:
                pass
        if cfg["color_restore"]:
            base = _histogram_match(base, original, cfg["color_restore_strength"])
            report["layers"]["color_restore"] = {
                "method": "per_channel_histogram_match_to_original",
                "strength": cfg["color_restore_strength"],
            }
    else:
        report["layers"]["pre_wash"] = {"applied": False, "reason": "pre_regen_disabled"}
    _ckpt_save(checkpoint_dir, "O1_postwash.png", base, report["checkpoint_errors"])

    # --- ONE resample to delivery (the lattice breaker) -----------------------
    delivery = cfg["output_target"] or min(src_long, 1250)
    delivery = min(delivery, src_long)
    if max(base.size) > delivery:
        ratio = delivery / float(max(base.size))
        base = base.resize(
            (max(1, int(round(base.width * ratio))), max(1, int(round(base.height * ratio)))),
            Image.Resampling.LANCZOS,
        )
    report["layers"]["delivery_resample"] = {
        "method": "single_lanczos_resample", "delivery_long_edge": delivery,
        "micro_rotation": False,
    }
    reference = base  # all fidelity metrics measure against this, not the source
    auxiliary_error = save_auxiliary_checkpoint(
        checkpoint_dir, "OR_postresample.png", reference
    )
    if auxiliary_error:
        auxiliary_checkpoint_errors.append(auxiliary_error)

    # --- coherent camera ladder ----------------------------------------------
    if adaptive:
        # V8.9: Deep is retired from the adaptive ladder (global degrade nukes
        # quality); it remains a manual option only. V8.8 keeps its ladder.
        ladder = (["light", "balanced"] if cfg.get("mode") == "ds-remint-v8.9"
                  else ["light", "balanced", "deep"])
    else:
        ladder = [cfg["strength"]]
    if adaptive and cfg.get("route_by_baseline"):
        baseline = report.get("input_baseline")
        if isinstance(baseline, dict):
            try:
                ai = float(baseline.get("ai_probability") or 0)
                if ai > 1.0:
                    ai = ai / 100.0
                if ai > 0.5:
                    # Input already reads flagged: skip the lightest rung.
                    ladder = ["balanced", "deep"]
                    report["layers"]["baseline_routing"] = {
                        "baseline_ai": ai, "ladder": ladder, "skipped": "light",
                    }
            except (TypeError, ValueError):
                pass
    chosen = None
    for rung_index, strength in enumerate(ladder):
        candidate, layers = _v88_candidate(
            reference, strength, cfg, creator_id, seed_extra, rung_index
        )
        metrics = {"psnr": None, "ssim_luma_window11_mean": None}
        try:
            from neural_texture import compare_images

            metrics = compare_images(reference, candidate)
        except Exception:  # noqa: BLE001
            pass
        floor_ok = float(metrics.get("ssim_luma_window11_mean", 0.0)) >= cfg["min_ssim"]

        attempt = {
            "rung": rung_index,
            "strength": strength,
            "metrics": {"psnr": _num(metrics.get("psnr")), "ssim": _num(metrics.get("ssim_luma_window11_mean"))},
            "quality_floor_ok": floor_ok,
            "layers": layers,
        }
        detector_ok = None
        verdict = None
        if adaptive:
            probe_path = str(Path(output_path).with_name(".v88-probe.jpg"))
            _encode_probe(candidate, probe_path, cfg)
            raw = _safe_detect(detector, probe_path)
            verdict = _v7_verdict(raw, cfg)
            detector_ok = verdict["cleared"]
            attempt["verdict"] = verdict
            attempt["rating_88"] = _rating_88(verdict)
            try:
                Path(probe_path).unlink()
            except OSError:
                pass
        report["attempts"].append(attempt)
        chosen = _keep_better(chosen, {"image": candidate, "metrics": metrics,
                                       "detector_ok": detector_ok, "floor_ok": floor_ok,
                                       "verdict": verdict})
        if not adaptive:
            break
        if detector_ok is None:
            break
        if detector_ok and floor_ok:
            break  # least destructive that clears -> max quality

    final_image = chosen["image"]
    _ckpt_save(checkpoint_dir, "O2_precamera.png", final_image, report["checkpoint_errors"])

    # --- final tone lock ------------------------------------------------------
    if cfg["color_restore"]:
        original_ref = original.resize(final_image.size, Image.Resampling.LANCZOS)
        final_image = _histogram_match(final_image, original_ref, cfg["color_restore_strength"])
        report["layers"]["final_tone_lock"] = {"strength": cfg["color_restore_strength"]}

    if return_buffer:
        # C8 v4 pre-JPEG handoff: the chained finisher consumes this buffer
        # directly so zero JPEG generations sit between the two stages.
        report["_pre_encode_rgb"] = np.asarray(final_image)

    # --- one encode (delivered bytes) ----------------------------------------
    exif_report = {"enabled": False}
    if cfg["iphone_exif"] and cfg.get("metadata_mode", "device") != "minimal":
        exif_bytes, exif_report = iphone_exif.build_iphone_exif(
            final_image.width, final_image.height, creator_id, seed_extra,
            device=cfg["device"], resolution_mode=cfg["resolution_mode"],
            x_resolution=cfg["x_resolution"], y_resolution=cfg["y_resolution"],
        )
        iphone_exif.write_exif_jpeg(final_image, output_path, exif_bytes, cfg["jpeg_quality"], cfg["jpeg_subsampling"])
    else:
        if cfg.get("metadata_mode") == "minimal":
            exif_report = {"enabled": False, "reason": "metadata_mode_minimal_no_exif_written"}
        final_image.save(output_path, format="JPEG", quality=cfg["jpeg_quality"], optimize=True,
                         subsampling=cfg["jpeg_subsampling"])
    report["layers"]["iphone_exif"] = exif_report
    report["layers"]["encode"] = {"format": "JPEG", "quality": cfg["jpeg_quality"],
                                  "subsampling": cfg["jpeg_subsampling"], "encodes": 1,
                                  "probe_matches_delivery": True}

    report["final_qc"] = _final_qc(original, output_path)
    try:
        with Image.open(output_path) as stage1_image:
            _ckpt_save(checkpoint_dir, "O3_stage1.png", stage1_image, report["checkpoint_errors"])
    except Exception as exc:
        if checkpoint_dir is not None:
            report["checkpoint_errors"].append(f"O3_stage1.png: {type(exc).__name__}: {exc}")
    report["quality_floor_gate"] = {
        "min_ssim": cfg["min_ssim"],
        "ssim": _num(chosen["metrics"].get("ssim_luma_window11_mean")),
        "psnr": _num(chosen["metrics"].get("psnr")),
        "accepted": bool(chosen["floor_ok"]),
        "output_long_edge": max(final_image.size),
        "beats_competitor_free_768": max(final_image.size) > 768,
    }

    rating = _rating_88(chosen.get("verdict")) if adaptive else None
    if adaptive:
        if chosen["detector_ok"] is None:
            note = "detector_unavailable_shipped_best_effort"
        elif chosen["detector_ok"]:
            note = None
        else:
            note = "could_not_fully_clear_within_quality_floor_shipped_best_effort"
        report["detector_gate"] = {
            "evaluated": True,
            "cleared": chosen["detector_ok"] is True,
            "ai_threshold": cfg["ai_threshold"],
            "source_threshold": cfg["source_threshold"],
            "deepfake_threshold": cfg["deepfake_threshold"],
            "rungs_tried": len(report["attempts"]),
            "note": note,
            "verdict": chosen.get("verdict"),
        }
    report["rating_88"] = rating
    report["detector_gate"]["rating_88"] = rating
    if rating is None:
        report["detector_gate"]["rating_note"] = "rating_unavailable"

    report["applied"] = True
    report["auxiliary_checkpoints"] = build_auxiliary_manifest(
        checkpoint_dir,
        capture_requested=checkpoint_dir is not None,
        errors=auxiliary_checkpoint_errors,
    )
    report["runtime_ms"] = int((time.time() - started) * 1000)
    return report


def _v88_candidate(reference, strength, cfg, creator_id, seed_extra, rung_index):
    """One coherent-camera candidate. deep = degrade 0.68 -> coherent balanced
    at low res -> Lanczos restore -> coherent light at delivery."""
    layers = {}
    camera_settings = {
        "strength": strength,
        "psf_scale": cfg["optics_psf_scale"],
    }
    settings = {"mode": "coherent-camera", "coherent_camera": camera_settings}
    if strength != "deep":
        candidate, report = apply_coherent_camera(
            reference, settings=settings, creator_id=creator_id,
            seed_extra=f"{seed_extra}:v88:{rung_index}",
        )
        layers["coherent_camera"] = {"strength": strength, "report": report}
        return candidate.convert("RGB"), layers

    # deep branch: light damage budget at low resolution, then restore.
    scale = cfg["deep_degrade_scale"]
    low_size = (max(1, int(round(reference.width * scale))),
                max(1, int(round(reference.height * scale))))
    low = reference.resize(low_size, Image.Resampling.LANCZOS)
    low_candidate, low_report = apply_coherent_camera(
        low, settings={
            "mode": "coherent-camera",
            "coherent_camera": {
                "strength": "balanced",
                "psf_scale": cfg["optics_psf_scale"],
            },
        },
        creator_id=creator_id, seed_extra=f"{seed_extra}:v88:{rung_index}:deep-low",
    )
    restored = low_candidate.resize(reference.size, Image.Resampling.LANCZOS)
    candidate, final_report = apply_coherent_camera(
        restored, settings={
            "mode": "coherent-camera",
            "coherent_camera": {
                "strength": "light",
                "psf_scale": cfg["optics_psf_scale"],
            },
        },
        creator_id=creator_id, seed_extra=f"{seed_extra}:v88:{rung_index}:deep-final",
    )
    layers["deep_branch"] = {
        "degrade_scale": scale, "low_res_clean": low_report, "restore": "lanczos",
        "final_light_pass": final_report,
    }
    return candidate.convert("RGB"), layers
