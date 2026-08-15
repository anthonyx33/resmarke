"""DS ReMint V7 -- wash once, re-life once, gate everything.

V7 keeps the full-frame Qwen pre-wash (the only proven SynthID carrier
breaker) UNCHANGED, then runs the non-generative camera re-life stack
(camera_relife) to replace the wash's generative fingerprint with camera
statistics, then encodes once and gates the DELIVERED bytes against a
source-aware detector.

Pipeline (default, adaptive):

    decode
      -> input baseline probe (detector on the ORIGINAL, recorded)
      -> pre-wash: ComfyUI purification (adaptive_level 8, process_cap 1536)
         -- identical to the proven live-test pass (SynthID carrier break)
      -> color restore (histogram match to the original)
      -> per-rung: camera re-life preset ladder light -> balanced -> strong
         (escalates ONLY the non-generative acquisition simulation, never
         global downscaling -- v6's destruction ladder is retired)
      -> final tone lock (histogram match to original, final size)
      -> ONE JPEG encode with coherent EXIF (delivered bytes == probed bytes)
      -> final-byte QC (PSNR/SSIM vs original)
      -> source-aware detector gate:
           ai_probability <= ai_threshold
           AND flux-family source <= source_threshold
           AND deepfake <= deepfake_threshold

What V7 deliberately does NOT do: a second generative pass (re-stamps), the
global downscale escalation ladder (dead by launch data), or silently
shipping a known-flagged file (the gate verdict is recorded AND used to pick
the best candidate).
"""

import time
from pathlib import Path

import numpy as np
from PIL import Image

from camera_relife import PRESETS as RELIFE_PRESETS
from camera_relife import apply_camera_relife
from max_cx_remint import _histogram_match
from neural_texture import compare_images
import iphone_exif


DEFAULT_SETTINGS = {
    "enabled": True,
    "engine_mode": "adaptive",        # "adaptive" (detector-gated) | "template"
    # --- wash (unchanged from the proven live-test pass) ---------------------
    "pre_regen": True,
    "regen_level": 8,
    "regen_process_cap": 1536,
    "regen_timeout": 300,
    # --- re-life -------------------------------------------------------------
    "color_restore": True,
    "color_restore_strength": 0.8,
    "relife_ladder": ["light", "balanced", "strong"],
    "template_preset": "balanced",    # single-run preset in template mode
    "max_rungs": 3,
    # --- gate ----------------------------------------------------------------
    "ai_threshold": 0.45,
    "source_threshold": 0.30,         # flux-family attribution ceiling
    "deepfake_threshold": 0.10,
    "min_ssim": 0.80,                 # content-faithfulness floor vs original
    # --- output --------------------------------------------------------------
    "output_target": None,            # None = min(source_long_edge, 1440)
    "jpeg_quality": 94,
    "jpeg_subsampling": "4:2:2",
    "iphone_exif": True,
    "metadata_mode": "device",       # "device" (coherent EXIF) | "minimal" (no EXIF)
    "device": "auto",
    "resolution_mode": "off",
    "x_resolution": 72.0,
    "y_resolution": 72.0,
}

# Source keys that belong to the AuraFlow/Flux VAE family. The launch detector
# attributed our Qwen wash as "flux: 72.5%" -- this is the family to gate.
FLUX_FAMILY_HINTS = ("flux", "auraflow")

# V8 quality floors: the owner-selected trade between quality preservation and
# laundering headroom. Lower SSIM floors allow stronger re-life presets (the
# pixel budget the heavier camera simulation spends), so "strong" buys more
# detector headroom and "studio" buys more fidelity.
V8_QUALITY_FLOOR_PRESETS = {
    "studio": {
        "min_ssim": 0.88,
        "relife_ladder": ["light", "balanced"],
        "label": "Studio (max quality)",
    },
    "high": {
        "min_ssim": 0.85,
        "relife_ladder": ["light", "balanced", "strong"],
        "label": "High",
    },
    "balanced": {
        "min_ssim": 0.82,
        "relife_ladder": ["light", "balanced", "strong"],
        "label": "Balanced (recommended)",
    },
    "strong": {
        "min_ssim": 0.75,
        "relife_ladder": ["balanced", "strong", "ghost"],
        "label": "Strong (max laundering headroom)",
    },
}

# V8.1 quality-first floors: the live V8 data showed full ghost pushing
# source-attribution graders the wrong way. V8.1 routes the ladder through
# ghost_lite (Malvar + noise-floor matching without heavy FPN/hot pixels) so
# quality stays closer to V7 balanced while CFA/noise-mapping graders still
# see camera structure.
V8_1_QUALITY_FLOOR_PRESETS = {
    "studio": {
        "min_ssim": 0.88,
        "relife_ladder": ["light"],
        "label": "Studio (max quality)",
    },
    "high": {
        "min_ssim": 0.85,
        "relife_ladder": ["light", "balanced"],
        "label": "High",
    },
    "balanced": {
        "min_ssim": 0.82,
        "relife_ladder": ["light", "balanced", "ghost_lite"],
        "label": "Balanced (recommended)",
    },
    "strong": {
        "min_ssim": 0.75,
        "relife_ladder": ["balanced", "ghost_lite", "ghost"],
        "label": "Strong (max laundering headroom)",
    },
}


def is_ds_remint_v7(settings):
    return isinstance(settings, dict) and settings.get("mode") == "ds-remint-v7"


def is_ds_remint_v8(settings):
    return isinstance(settings, dict) and settings.get("mode") == "ds-remint-v8"


def is_ds_remint_v8_1(settings):
    return isinstance(settings, dict) and settings.get("mode") == "ds-remint-v8.1"


def apply_ds_remint_v8(input_path, output_path, creator_id, settings=None, seed_extra="", detector=None):
    """DS ReMint V8: the V7 pipeline with the V8 quality-floor extension.

    Same wash -> camera re-life -> source-aware gate architecture. V8 adds the
    owner-selectable quality floor (studio / high / balanced / strong) that
    trades fidelity for laundering headroom via the min-SSIM floor and the
    re-life ladder (strong reaches the ghost preset)."""
    return apply_ds_remint_v7(
        input_path=input_path,
        output_path=output_path,
        creator_id=creator_id,
        settings=settings,
        seed_extra=seed_extra,
        detector=detector,
    )


def apply_ds_remint_v8_1(input_path, output_path, creator_id, settings=None, seed_extra="", detector=None):
    """DS ReMint V8.1: the V8 pipeline with quality-first floors.

    Same architecture as V8; the quality-floor ladders route through
    ghost_lite instead of full ghost until the strong floor, and the gate
    accepts per-grader (ensemble) verdicts."""
    return apply_ds_remint_v7(
        input_path=input_path,
        output_path=output_path,
        creator_id=creator_id,
        settings=settings,
        seed_extra=seed_extra,
        detector=detector,
    )


def normalize_ds_remint_v7_settings(settings):
    raw = settings if isinstance(settings, dict) else {}
    sub = {}
    for key in ("ds_remint_v7", "ds_remint_v8", "ds_remint_v8_1"):
        if isinstance(raw.get(key), dict):
            sub = raw[key]
    cfg = dict(DEFAULT_SETTINGS)
    cfg["mode"] = str(raw.get("mode") or "ds-remint-v7")
    cfg["enabled"] = cfg["mode"] in ("ds-remint-v7", "ds-remint-v8", "ds-remint-v8.1")

    engine_mode = str(sub.get("engine_mode", cfg["engine_mode"]))
    cfg["engine_mode"] = engine_mode if engine_mode in ("template", "adaptive") else "adaptive"

    cfg["pre_regen"] = bool(sub.get("pre_regen", cfg["pre_regen"]))
    cfg["regen_level"] = int(_clamp(sub.get("regen_level", cfg["regen_level"]), 3, 10))
    cfg["regen_process_cap"] = int(_clamp(sub.get("regen_process_cap", cfg["regen_process_cap"]), 512, 4096))
    cfg["regen_timeout"] = int(_clamp(sub.get("regen_timeout", cfg["regen_timeout"]), 30, 900))

    cfg["color_restore"] = bool(sub.get("color_restore", cfg["color_restore"]))
    cfg["color_restore_strength"] = float(_clamp(sub.get("color_restore_strength", cfg["color_restore_strength"]), 0.0, 1.0))

    # V8/V8.1 quality floor: applies the floor's min-SSIM + ladder defaults
    # unless explicitly overridden (V7 requests without quality_floor keep the
    # V7 defaults byte-for-byte).
    quality_floor = str(sub.get("quality_floor", ""))
    floors = (
        V8_1_QUALITY_FLOOR_PRESETS
        if cfg["mode"] == "ds-remint-v8.1"
        else V8_QUALITY_FLOOR_PRESETS
    )
    if quality_floor in floors:
        floor = floors[quality_floor]
        cfg["quality_floor"] = quality_floor
        if "min_ssim" not in sub:
            cfg["min_ssim"] = floor["min_ssim"]
        if "relife_ladder" not in sub:
            cfg["relife_ladder"] = list(floor["relife_ladder"])

    ladder = sub.get("relife_ladder", cfg["relife_ladder"])
    if isinstance(ladder, list):
        ladder = [p for p in ladder if p in RELIFE_PRESETS]
    else:
        ladder = []
    cfg["relife_ladder"] = ladder or list(DEFAULT_SETTINGS["relife_ladder"])
    template_preset = str(sub.get("template_preset", cfg["template_preset"]))
    cfg["template_preset"] = template_preset if template_preset in RELIFE_PRESETS else "balanced"
    cfg["max_rungs"] = int(_clamp(sub.get("max_rungs", cfg["max_rungs"]), 1, 5))

    cfg["ai_threshold"] = float(_clamp(sub.get("ai_threshold", cfg["ai_threshold"]), 0.0, 1.0))
    cfg["source_threshold"] = float(_clamp(sub.get("source_threshold", cfg["source_threshold"]), 0.0, 1.0))
    cfg["deepfake_threshold"] = float(_clamp(sub.get("deepfake_threshold", cfg["deepfake_threshold"]), 0.0, 1.0))
    cfg["min_ssim"] = float(_clamp(sub.get("min_ssim", cfg["min_ssim"]), 0.0, 1.0))

    if sub.get("output_target") is not None:
        cfg["output_target"] = int(_clamp(sub["output_target"], 256, 8192))
    else:
        cfg["output_target"] = None

    cfg["jpeg_quality"] = int(_clamp(sub.get("jpeg_quality", cfg["jpeg_quality"]), 60, 100))
    jpeg_subsampling = sub.get("jpeg_subsampling", cfg["jpeg_subsampling"])
    cfg["jpeg_subsampling"] = (
        jpeg_subsampling if jpeg_subsampling in ("4:2:0", "4:2:2", "4:4:4") else "4:2:2"
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
    import hashlib

    material = f"ds-remint-v7:{creator_id}:{seed_extra}:{size[0]}x{size[1]}:{salt}"
    return int(hashlib.sha256(material.encode("utf-8")).hexdigest()[:16], 16) & 0xFFFFFFFF


def apply_ds_remint_v7(input_path, output_path, creator_id, settings=None, seed_extra="", detector=None):
    """Full DS ReMint V7 pipeline. Writes the FINAL camera-like JPEG (with
    coherent EXIF when enabled) to output_path and returns a report.

    detector: optional callable(path)->dict for adaptive mode; expected keys
    ai_probability (0-1 or 0-100), watermark_present (bool), sources (dict),
    and optionally deepfake_probability. Without it, adaptive degrades to a
    single balanced template run (never blind escalation).
    """
    cfg = normalize_ds_remint_v7_settings(settings)
    report = {
        "enabled": bool(cfg["enabled"]),
        "pipeline": cfg.get("mode") or "ds_remint_v7",
        "engine": "ds_remint_v7",
        "applied": False,
        "settings": _public_settings(cfg),
        "layers": {},
        "attempts": [],
        "input_baseline": None,
        "quality_floor_gate": {},
        "detector_gate": {"evaluated": False},
    }
    if not cfg["enabled"]:
        return report

    started = time.time()
    original = Image.open(input_path).convert("RGB")
    src_long = max(original.size)
    report["source_long_edge"] = src_long

    adaptive = cfg["engine_mode"] == "adaptive"
    if adaptive and detector is None:
        report["detector_gate"]["note"] = "no_detector_supplied_degraded_to_single_template_run"
        adaptive = False

    # --- input baseline probe (what the grader reads BEFORE we touch it) ------
    if adaptive:
        baseline_path = str(Path(output_path).with_name(".v7-baseline.jpg"))
        _encode_probe(original, baseline_path, cfg)
        baseline = _safe_detect(detector, baseline_path)
        report["input_baseline"] = baseline
        try:
            Path(baseline_path).unlink()
        except OSError:
            pass

    # --- layer 0: the wash (unchanged SynthID carrier breaker) ---------------
    base = original
    if cfg["pre_regen"]:
        regen_path = Path(output_path).with_name(".v7-regen.png")
        try:
            regen_report = _run_regen(input_path, str(regen_path), cfg, _seed(creator_id, seed_extra, original.size, 900))
            base = Image.open(regen_path).convert("RGB")
            report["layers"]["pre_wash"] = regen_report
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
                "reimports_synthid": False,
            }
    else:
        report["layers"]["pre_wash"] = {"applied": False, "reason": "pre_regen_disabled"}

    # --- per-rung camera re-life ladder ---------------------------------------
    rung_count = cfg["max_rungs"] if adaptive else 1
    chosen = None
    for rung_index in range(rung_count):
        preset = (
            cfg["relife_ladder"][min(rung_index, len(cfg["relife_ladder"]) - 1)]
            if adaptive
            else cfg["template_preset"]
        )
        relife_settings = {"mode": "camera-relife", "camera_relife": {"preset": preset}}
        candidate, relife_report = apply_camera_relife(
            base,
            settings=relife_settings,
            creator_id=creator_id,
            seed_extra=f"{seed_extra}:rung{rung_index}",
        )

        original_ref = (
            original
            if original.size == candidate.size
            else original.resize(candidate.size, Image.Resampling.LANCZOS)
        )
        metrics = compare_images(original_ref, candidate)
        floor_ok = float(metrics.get("ssim_luma_window11_mean", 0.0)) >= cfg["min_ssim"]

        attempt = {
            "rung": rung_index,
            "relife_preset": preset,
            "metrics": {
                "psnr": _num(metrics.get("psnr")),
                "ssim": _num(metrics.get("ssim_luma_window11_mean")),
            },
            "quality_floor_ok": floor_ok,
            "relife_report": relife_report,
        }

        detector_ok = None
        verdict = None
        if adaptive:
            probe_path = str(Path(output_path).with_name(".v7-probe.jpg"))
            # Probe bytes == delivered bytes: same quality + subsampling as the
            # final encode (v6 probed q92/4:2:0 but delivered q94/4:2:2).
            _encode_probe(candidate, probe_path, cfg)
            raw = _safe_detect(detector, probe_path)
            verdict = _v7_verdict(raw, cfg)
            detector_ok = verdict["cleared"]
            attempt["detector"] = raw
            attempt["verdict"] = verdict
            attempt["rating_88"] = _rating_88(verdict)
            try:
                Path(probe_path).unlink()
            except OSError:
                pass

        report["attempts"].append(attempt)
        chosen = _keep_better(
            chosen,
            {"image": candidate, "metrics": metrics, "preset": preset,
             "detector_ok": detector_ok, "floor_ok": floor_ok, "verdict": verdict},
        )
        if not adaptive:
            break
        if detector_ok is None:
            # No usable verdict (detector infra error): never blind-escalate.
            break
        if detector_ok and floor_ok:
            break  # minimum intervention that clears -> maximum quality

    final_image = chosen["image"]

    # --- delivery sizing (never upscale past the source) ----------------------
    delivery = cfg["output_target"] or min(src_long, 1440)
    delivery = max(delivery, 1)
    delivery = min(delivery, src_long)
    if max(final_image.size) > delivery:
        ratio = delivery / float(max(final_image.size))
        new_size = (
            max(1, int(round(final_image.width * ratio))),
            max(1, int(round(final_image.height * ratio))),
        )
        final_image = final_image.resize(new_size, Image.Resampling.LANCZOS)
        report["layers"]["delivery_resize"] = {
            "method": "lanczos_downscale_to_delivery_cap",
            "delivery_long_edge": delivery,
        }
    else:
        report["layers"]["delivery_resize"] = {"applied": False}

    # --- final tone lock (histogram match to original at final size) ----------
    if cfg["color_restore"]:
        original_ref = (
            original
            if original.size == final_image.size
            else original.resize(final_image.size, Image.Resampling.LANCZOS)
        )
        final_image = _histogram_match(final_image, original_ref, cfg["color_restore_strength"])
        report["layers"]["final_tone_lock"] = {"strength": cfg["color_restore_strength"]}

    # --- one encode (delivered bytes) ----------------------------------------
    exif_report = {"enabled": False}
    if cfg["iphone_exif"] and cfg.get("metadata_mode", "device") != "minimal":
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
        if cfg.get("metadata_mode") == "minimal":
            exif_report = {"enabled": False, "reason": "metadata_mode_minimal_no_exif_written"}
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
        "probe_matches_delivery": True,
    }

    # --- final-byte QC --------------------------------------------------------
    qc = _final_qc(original, output_path)
    report["final_qc"] = qc

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
    report["runtime_ms"] = int((time.time() - started) * 1000)
    return report


# ---------------------------------------------------------------------------
# Wash (reuses the proven purification pass; NOT re-implemented)
# ---------------------------------------------------------------------------

def _run_regen(input_path, output_path, cfg, seed):
    """Full-frame pre-wash: the exact ComfyUI purification pass that removed
    SynthID in live tests. Raises on ComfyUI failure so the worker fails the
    job honestly rather than shipping a still-watermarked image."""
    from max_optimised_remint import _run_purification  # proven; ComfyUI-backed

    report = _run_purification(
        input_path=input_path,
        output_path=output_path,
        adaptive_level=cfg["regen_level"],
        process_cap=cfg["regen_process_cap"],
        timeout=cfg["regen_timeout"],
        seed=seed,
    )
    report["purpose"] = "break_synthid_carrier_before_re_life"
    return report


# ---------------------------------------------------------------------------
# Detector gate (source-aware; probe bytes == delivery bytes)
# ---------------------------------------------------------------------------

def _encode_probe(image, path, cfg):
    image.save(
        path, format="JPEG", quality=cfg["jpeg_quality"], optimize=True,
        subsampling=cfg["jpeg_subsampling"],
    )


def _safe_detect(detector, path):
    try:
        result = detector(path)
        if isinstance(result, dict):
            return dict(result)
        return {"ok": False, "reason": "detector_returned_non_dict", "infra_error": True}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "reason": f"detector_error: {str(exc)[:200]}", "infra_error": True}


def _norm01(value):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    if not np.isfinite(value):
        return None
    if value > 1.0:
        value = value / 100.0
    return max(0.0, min(1.0, value))


def _single_verdict(result, cfg):
    """Verdict for ONE grader's normalized payload: ai, flux-family, deepfake,
    watermark, reasons. Cleared requires ALL measured signals under threshold
    and no watermark; missing measurements block a clear upstream."""
    v = {"ai": None, "flux_family": None, "deepfake": None, "watermark": None, "reasons": []}

    watermark = result.get("watermark_present")
    if isinstance(watermark, bool):
        v["watermark"] = watermark
        if watermark:
            v["reasons"].append("watermark_present")

    ai = _norm01(result.get("ai_probability"))
    v["ai"] = ai
    if ai is not None and ai > cfg["ai_threshold"]:
        v["reasons"].append("ai_probability_over_threshold")

    sources = result.get("sources") if isinstance(result.get("sources"), dict) else None
    flux_score = 0.0
    if sources:
        for key, value in sources.items():
            key_l = str(key).lower()
            if "deepfake" in key_l:
                df = _norm01(value)
                if df is not None:
                    v["deepfake"] = max(v["deepfake"] or 0.0, df)
            if any(hint in key_l for hint in FLUX_FAMILY_HINTS):
                score = _norm01(value)
                if score is not None:
                    flux_score = max(flux_score, score)
        v["flux_family"] = flux_score
    else:
        v["flux_family"] = None

    if v["deepfake"] is not None and v["deepfake"] > cfg["deepfake_threshold"]:
        v["reasons"].append("deepfake_over_threshold")
    if v["flux_family"] is not None and v["flux_family"] > cfg["source_threshold"]:
        v["reasons"].append("flux_family_over_threshold")
    return v


def _v7_verdict(result, cfg):
    """Ensemble-aware verdict.

    V8.1: if the detector proxy returns a `graders` list (one normalized
    payload per detector), the gate requires EVERY grader to clear and
    reports the worst ai/flux/deepfake across the ensemble. You are scored by
    the harshest grader, so the gate is too. Single-payload responses keep the
    V7 behaviour exactly."""
    verdict = {
        "ai": None, "flux_family": None, "deepfake": None, "watermark": None,
        "cleared": None, "reasons": [],
    }
    if not isinstance(result, dict) or result.get("infra_error") or result.get("ok") is False:
        return verdict

    graders = result.get("graders")
    if isinstance(graders, list) and graders:
        per = []
        usable = 0
        clear_all = True
        for grader in graders:
            if not isinstance(grader, dict):
                continue
            usable += 1
            single = _single_verdict(grader, cfg)
            per.append({
                "grader": grader.get("name") or grader.get("provider") or f"grader_{usable}",
                **single,
            })
            for key in ("ai", "flux_family", "deepfake"):
                value = single[key]
                if value is not None:
                    verdict[key] = max(verdict[key] or 0.0, value)
            if single["watermark"] is True:
                verdict["watermark"] = True
            verdict["reasons"].extend(single["reasons"])
            if single["reasons"]:
                clear_all = False
        verdict["graders"] = per
        if usable == 0:
            return verdict
        verdict["cleared"] = clear_all
        return verdict

    single = _single_verdict(result, cfg)
    for key in ("ai", "flux_family", "deepfake", "watermark"):
        verdict[key] = single[key]
    verdict["reasons"] = single["reasons"]
    # Cleared only when every measured signal is under threshold and no
    # watermark is present. Missing measurements block a clear.
    if single["ai"] is None or single["watermark"] is None:
        verdict["cleared"] = None  # unusable verdict, never a pass
    else:
        verdict["cleared"] = not single["reasons"]
    return verdict


def _rating_88(verdict):
    """0-88 AI-flag risk score: 0 = lowest risk, 88 = highest. Reporting only."""
    if not isinstance(verdict, dict):
        return None
    if verdict.get("watermark") is True:
        return 88
    components = []
    for key in ("ai", "flux_family", "deepfake"):
        value = verdict.get(key)
        if isinstance(value, (int, float)):
            components.append(value)
    if not components:
        return None
    return int(round(max(components) * 88))


def _keep_better(current, candidate):
    if current is None:
        return candidate

    def rank(c):
        det = 1 if c.get("detector_ok") else 0
        ssim = float(c["metrics"].get("ssim_luma_window11_mean", 0.0))
        return (det, ssim, 1 if c.get("floor_ok") else 0)

    return candidate if rank(candidate) > rank(current) else current


def _final_qc(original, output_path):
    out = Image.open(output_path).convert("RGB")
    src = original if original.size == out.size else original.resize(out.size, Image.Resampling.LANCZOS)
    metrics = compare_images(src, out)
    return {
        "psnr": _num(metrics.get("psnr")),
        "ssim": _num(metrics.get("ssim_luma_window11_mean")),
        "output_size": list(out.size),
        "source_long_edge": max(original.size),
    }


def _num(value):
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return round(parsed, 4) if np.isfinite(parsed) else None


def _public_settings(cfg):
    return {k: cfg.get(k) for k in (
        "engine_mode", "pre_regen", "regen_level", "regen_process_cap",
        "regen_timeout", "color_restore", "color_restore_strength",
        "quality_floor", "relife_ladder", "template_preset", "max_rungs",
        "ai_threshold", "source_threshold", "deepfake_threshold", "min_ssim",
        "output_target", "jpeg_quality", "jpeg_subsampling", "iphone_exif",
    )}
