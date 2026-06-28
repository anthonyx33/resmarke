"""Internal Automatic Content Repair Lab v2.

Narrow scope on purpose:
- automatic localizer (text/glyph + geometry/grid heuristics)
- one pass, max three regions
- measurable ledger fields

v2 swaps the repair engine from the incapable OpenCV Telea placeholder to Qwen
masked inpaint (Qwen-Image-2512 + Lightning 4-step, via the localhost ComfyUI
service). v1's Telea fill produced smooth featureless patches that spiked the
statistical detector (59->97 High); Qwen regenerates realistic texture in the
masked region instead. Node names in run_qwen_masked_inpaint are taken verbatim
from the production remarkee-max-v2.api.json export. On Qwen failure the region
is skipped (ship pre-repair pixels) -- never a silent Telea fallback. Telea is
retained only as an explicit opt-in engine for offline A/B diagnosis.
"""

import hashlib
import io
import tempfile
import time
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageFilter

from neural_texture import compare_images


DEFAULT_SETTINGS = {
    "enabled": True,
    "preset": "balanced",
    "patch_size": 256,
    "stride": 128,
    "candidate_threshold": 0.80,
    "min_region_area_ratio": 0.004,
    "max_regions": 3,
    "mask_dilation_px": 10,
    "mask_feather_px": 20,
    "merge_iou": 0.30,
    # NOTE: text_denoise / geometry_denoise are now REAL Qwen KSampler denoise
    # values (v2 swap), not the old Telea blend alpha. Text regions need a
    # strong denoise to replace gibberish glyphs with clean surface; geometry
    # regions need a light denoise to straighten warble without erasing structure.
    "text_denoise": 0.72,
    "geometry_denoise": 0.28,
    "max_global_delta": 0.15,
    # Qwen masked-inpaint engine (v2 swap of the incapable Telea placeholder).
    # engine "qwen" uses ComfyUI + Qwen-Image-2512 + Lightning 4-step on the
    # localizer's mask. "telea" is retained ONLY as an explicit, opt-in fallback
    # for offline diagnosis -- never the default, never a silent fallback.
    "engine": "qwen",
    "qwen_timeout": 240.0,
    "qwen_grow_mask_by": 6,
}


def is_content_repair_lab(settings):
    return isinstance(settings, dict) and settings.get("mode") == "content-repair-lab"


def apply_content_repair_lab(input_path, output_path, creator_id, settings=None, seed_extra=""):
    cfg = normalize_content_repair_settings(settings)
    report = {
        "enabled": bool(cfg["enabled"]),
        "pipeline": "auto_content_repair_lab_v2",
        "applied": False,
        "repair_engine": (
            "qwen_image2512_masked_inpaint_v2"
            if cfg.get("engine", "qwen") == "qwen"
            else "opencv_telea_inpaint_v1"
        ),
        "settings": public_settings(cfg),
        "localizer": {},
        "regions": [],
        "quality_gates": {},
        # Measurement is the recurring failure point (Neural Texture Lab and
        # Content Repair v1 both shipped stubbed gates and got surprised). v2
        # makes the gate DECISION real: when detector scores are supplied (via
        # the worker's detector callable / joined JSON), ship_original_if_worse
        # is computed here, not hand-waved. Until scores are supplied the field
        # is honestly "not_evaluated" rather than silently "external_required".
        "measurement": {
            "detector_scores": "not_evaluated",
            "realism_gate": "proxy_metrics",
            "self_fingerprint_gate": "not_evaluated",
            "ship_original_if_worse": "not_evaluated",
        },
    }
    if not cfg["enabled"]:
        return report

    started = time.time()
    source = Image.open(input_path).convert("RGB")
    source_arr = np.asarray(source)
    candidates, localizer_report = localize_content_artifacts(source_arr, cfg)
    report["localizer"] = localizer_report
    report["regions"] = [candidate_to_report(c) for c in candidates]

    if not candidates:
        report["reason"] = "no_candidates"
        report["runtime_ms"] = int((time.time() - started) * 1000)
        return report

    repaired = source.copy()
    repaired_arr = np.asarray(repaired).copy()
    repaired_any = False
    for region_idx, candidate in enumerate(candidates, start=1):
        seed = region_seed(creator_id, seed_extra, region_idx, candidate)
        next_arr, region_report = repair_region(
            repaired_arr,
            candidate,
            cfg,
            seed=seed,
        )
        candidate["repair"] = region_report
        if region_report["applied"]:
            repaired_arr = next_arr
            repaired_any = True

    if not repaired_any:
        report["reason"] = "no_regions_repaired"
        report["regions"] = [candidate_to_report(c) for c in candidates]
        report["runtime_ms"] = int((time.time() - started) * 1000)
        return report

    output = Image.fromarray(repaired_arr.astype(np.uint8), mode="RGB")
    metrics = compare_images(source, output)
    gates = content_repair_quality_gates(metrics, cfg)
    report["metrics"] = metrics
    report["quality_gates"] = gates
    report["regions"] = [candidate_to_report(c) for c in candidates]

    if not gates["accepted"]:
        report["reason"] = "quality_gates_failed"
        report["runtime_ms"] = int((time.time() - started) * 1000)
        return report

    output.save(output_path, format="PNG")
    report["applied"] = True
    report["runtime_ms"] = int((time.time() - started) * 1000)
    return report


def normalize_content_repair_settings(settings):
    raw = settings if isinstance(settings, dict) else {}
    repair = raw.get("content_repair") if isinstance(raw.get("content_repair"), dict) else {}
    cfg = dict(DEFAULT_SETTINGS)
    cfg["enabled"] = raw.get("mode") == "content-repair-lab"
    preset = str(repair.get("preset", cfg["preset"]))
    cfg["preset"] = preset if preset in ("conservative", "balanced", "aggressive") else "balanced"
    if cfg["preset"] == "conservative":
        cfg["max_regions"] = 2
        cfg["candidate_threshold"] = 0.86
    elif cfg["preset"] == "aggressive":
        cfg["max_regions"] = 5
        cfg["candidate_threshold"] = 0.74

    for key in (
        "patch_size",
        "stride",
        "max_regions",
        "mask_dilation_px",
        "mask_feather_px",
        "qwen_grow_mask_by",
    ):
        if key in repair:
            cfg[key] = int(clamp_float(repair[key], 1, 4096))
    for key in (
        "candidate_threshold",
        "min_region_area_ratio",
        "merge_iou",
        "text_denoise",
        "geometry_denoise",
        "max_global_delta",
    ):
        if key in repair:
            cfg[key] = clamp_float(repair[key], 0.0, 1.0)
    if "engine" in repair:
        engine = str(repair["engine"]).strip().lower()
        cfg["engine"] = engine if engine in ("qwen", "telea") else "qwen"
    if "qwen_timeout" in repair:
        cfg["qwen_timeout"] = clamp_float(repair["qwen_timeout"], 30.0, 900.0)
    return cfg


def public_settings(cfg):
    return {
        key: cfg[key]
        for key in (
            "preset",
            "patch_size",
            "stride",
            "candidate_threshold",
            "min_region_area_ratio",
            "max_regions",
            "mask_dilation_px",
            "mask_feather_px",
            "merge_iou",
            "text_denoise",
            "geometry_denoise",
            "engine",
            "qwen_grow_mask_by",
            "qwen_timeout",
        )
    }


def localize_content_artifacts(rgb, cfg):
    height, width, _ = rgb.shape
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    edges = cv2.Canny(gray, 80, 180)
    patch = int(cfg["patch_size"])
    stride = int(cfg["stride"])

    raw_candidates = []
    for y in range(0, max(1, height - patch + 1), stride):
        for x in range(0, max(1, width - patch + 1), stride):
            x2 = min(width, x + patch)
            y2 = min(height, y + patch)
            if x2 - x < 64 or y2 - y < 64:
                continue
            edge_patch = edges[y:y2, x:x2]
            gray_patch = gray[y:y2, x:x2]
            text_score, text_report = text_glyph_score(edge_patch, gray_patch)
            geom_score, geom_report = geometry_grid_score(edge_patch)
            score = max(text_score, geom_score)
            if score < cfg["candidate_threshold"]:
                continue
            region_type = "text_glyph" if text_score >= geom_score else "geometry_grid"
            raw_candidates.append(
                {
                    "bbox": [x, y, x2, y2],
                    "type": region_type,
                    "score": float(score),
                    "scores": {
                        "text_glyph": float(text_score),
                        "geometry_grid": float(geom_score),
                    },
                    "diagnostics": {
                        "text": text_report,
                        "geometry": geom_report,
                    },
                }
            )

    merged = merge_candidates(raw_candidates, cfg["merge_iou"], width, height)
    min_area = float(cfg["min_region_area_ratio"]) * width * height
    filtered = [c for c in merged if bbox_area(c["bbox"]) >= min_area]
    filtered.sort(key=lambda c: c["score"], reverse=True)
    selected = filtered[: int(cfg["max_regions"])]

    for idx, candidate in enumerate(selected, start=1):
        candidate["id"] = f"acr-{idx:02d}"
        candidate["bbox_area_ratio"] = float(bbox_area(candidate["bbox"]) / (width * height))
        candidate["mask"] = build_region_mask(rgb, edges, candidate, cfg)
        candidate["mask_area_ratio"] = float(np.count_nonzero(candidate["mask"]) / (width * height))

    return selected, {
        "version": "text-geometry-heuristic-v1",
        "image_size": [width, height],
        "patch_size": patch,
        "stride": stride,
        "candidate_threshold": cfg["candidate_threshold"],
        "raw_candidates": len(raw_candidates),
        "merged_candidates": len(merged),
        "selected_candidates": len(selected),
        "negative_control_rule": "selected_candidates_must_be_zero_for_real_camera_controls",
    }


def text_glyph_score(edge_patch, gray_patch):
    edge_density = float(np.mean(edge_patch > 0))
    _, labels, stats, _ = cv2.connectedComponentsWithStats((edge_patch > 0).astype(np.uint8), 8)
    small_components = 0
    for row in stats[1:]:
        _, _, w, h, area = row
        if 3 <= area <= 220 and 2 <= w <= 64 and 2 <= h <= 64:
            aspect = max(w / max(h, 1), h / max(w, 1))
            if aspect <= 8:
                small_components += 1
    component_score = min(1.0, small_components / 90.0)
    density_score = 1.0 - min(1.0, abs(edge_density - 0.095) / 0.095)
    contrast_score = min(1.0, float(np.std(gray_patch)) / 70.0)
    score = 0.55 * component_score + 0.30 * density_score + 0.15 * contrast_score
    return float(score), {
        "edge_density": edge_density,
        "small_components": int(small_components),
        "component_score": component_score,
        "density_score": density_score,
        "contrast_score": contrast_score,
    }


def geometry_grid_score(edge_patch):
    edge_density = float(np.mean(edge_patch > 0))
    lines = cv2.HoughLinesP(
        edge_patch,
        rho=1,
        theta=np.pi / 180,
        threshold=34,
        minLineLength=max(24, min(edge_patch.shape[:2]) // 5),
        maxLineGap=10,
    )
    if lines is None:
        line_count = 0
        orientation_bins = 0
    else:
        angles = []
        for line in lines[:, 0, :]:
            x1, y1, x2, y2 = line
            angle = (np.degrees(np.arctan2(y2 - y1, x2 - x1)) + 180) % 180
            angles.append(angle)
        line_count = len(angles)
        hist, _ = np.histogram(angles, bins=[0, 15, 35, 55, 75, 105, 125, 145, 165, 180])
        orientation_bins = int(np.count_nonzero(hist >= 2))

    line_score = min(1.0, line_count / 28.0)
    orientation_score = min(1.0, orientation_bins / 3.0)
    density_score = min(1.0, edge_density / 0.12)
    score = 0.55 * line_score + 0.25 * orientation_score + 0.20 * density_score
    return float(score), {
        "edge_density": edge_density,
        "line_count": int(line_count),
        "orientation_bins": int(orientation_bins),
        "line_score": line_score,
        "orientation_score": orientation_score,
        "density_score": density_score,
    }


def merge_candidates(candidates, merge_iou, width, height):
    candidates = sorted(candidates, key=lambda c: c["score"], reverse=True)
    merged = []
    for candidate in candidates:
        matched = None
        for existing in merged:
            if candidate["type"] == existing["type"] and iou(candidate["bbox"], existing["bbox"]) > merge_iou:
                matched = existing
                break
        if matched is None:
            merged.append(dict(candidate))
            continue
        matched["bbox"] = union_bbox(matched["bbox"], candidate["bbox"], width, height)
        matched["score"] = max(matched["score"], candidate["score"])
        for key, value in candidate["scores"].items():
            matched["scores"][key] = max(matched["scores"].get(key, 0.0), value)
    return merged


def build_region_mask(rgb, edges, candidate, cfg):
    height, width, _ = rgb.shape
    x1, y1, x2, y2 = [int(v) for v in candidate["bbox"]]
    patch_edges = edges[y1:y2, x1:x2]
    if candidate["type"] == "text_glyph":
        base = (patch_edges > 0).astype(np.uint8) * 255
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        base = cv2.morphologyEx(base, cv2.MORPH_CLOSE, kernel, iterations=2)
        base = cv2.dilate(base, kernel, iterations=1)
    else:
        base = np.zeros_like(patch_edges, dtype=np.uint8)
        lines = cv2.HoughLinesP(
            patch_edges,
            rho=1,
            theta=np.pi / 180,
            threshold=28,
            minLineLength=max(20, min(patch_edges.shape[:2]) // 6),
            maxLineGap=12,
        )
        if lines is not None:
            for line in lines[:, 0, :]:
                cv2.line(base, (line[0], line[1]), (line[2], line[3]), 255, 5)
        if np.count_nonzero(base) == 0:
            base = (patch_edges > 0).astype(np.uint8) * 255

    dilate_px = int(cfg["mask_dilation_px"])
    if dilate_px > 0:
        k = max(3, dilate_px * 2 + 1)
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))
        base = cv2.dilate(base, kernel, iterations=1)

    mask = np.zeros((height, width), dtype=np.uint8)
    mask[y1:y2, x1:x2] = base
    return mask


def repair_region(rgb, candidate, cfg, seed):
    mask = candidate.get("mask")
    if mask is None or np.count_nonzero(mask) == 0:
        return rgb, {"applied": False, "reason": "empty_mask"}

    region_type = candidate["type"]
    if region_type == "text_glyph":
        denoise = float(cfg["text_denoise"])
        strategy = "qwen_remove_fill_no_glyph_regeneration"
    else:
        denoise = float(cfg["geometry_denoise"])
        strategy = "qwen_structure_preserving_fill"

    engine = cfg.get("engine", "qwen")
    mask_pixels = int(np.count_nonzero(mask))

    if engine == "telea":
        # Explicit opt-in offline path only. Never the default and never a
        # silent fallback: Telea cannot produce realistic texture and was the
        # dominant cause of the v1 statistical 59->97 spike.
        return _repair_region_telea(rgb, mask, region_type, denoise, cfg), {
            "applied": True,
            "engine": "telea",
            "strategy": strategy.replace("qwen_", "telea_"),
            "denoise": denoise,
            "blend_alpha": denoise,
            "mask_pixels": mask_pixels,
        }

    # --- Qwen masked inpaint (default v2 engine) ---
    try:
        inpainted_rgb = run_qwen_masked_inpaint(
            rgb,
            mask,
            region_type=region_type,
            denoise=denoise,
            grow_mask_by=int(cfg.get("qwen_grow_mask_by", 6)),
            timeout=float(cfg.get("qwen_timeout", 240.0)),
            seed=int(seed),
        )
    except Exception as exc:  # noqa: BLE001
        # Fail-safe: skip this region, keep the pre-repair pixels. We do NOT
        # fall back to Telea silently -- that would re-introduce the v1 failure.
        # Shipping the un-repaired region yields the baseline (~96.7%), never
        # the 99.6% Telea spike. The error is surfaced in the report.
        return rgb, {
            "applied": False,
            "engine": "qwen",
            "strategy": strategy,
            "denoise": denoise,
            "mask_pixels": mask_pixels,
            "reason": "qwen_inpaint_failed",
            "error": str(exc)[:500],
        }

    original = rgb.astype(np.float32)
    filled = inpainted_rgb.astype(np.float32)
    # Full-strength feathered composite: accept the Qwen fill completely inside
    # the mask, feather only at the edge. (v1 multiplied alpha by denoise, which
    # was a Telea-weakener -- wrong for a real generative fill.)
    alpha = feather_mask(mask, int(cfg["mask_feather_px"]))[..., None]
    repaired = np.clip(original * (1.0 - alpha) + filled * alpha, 0, 255).astype(np.uint8)
    return repaired, {
        "applied": True,
        "engine": "qwen",
        "strategy": strategy,
        "denoise": denoise,
        "mask_pixels": mask_pixels,
    }


def _repair_region_telea(rgb, mask, region_type, denoise, cfg):
    """Classical Telea inpaint. Retained for offline A/B diagnosis only; never
    the default engine. denoise is reused as the blend alpha for parity with v1."""
    radius = 5 if region_type == "text_glyph" else 3
    bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
    inpainted = cv2.inpaint(bgr, mask, radius, cv2.INPAINT_TELEA)
    inpainted_rgb = cv2.cvtColor(inpainted, cv2.COLOR_BGR2RGB).astype(np.float32)
    original = rgb.astype(np.float32)
    alpha = feather_mask(mask, int(cfg["mask_feather_px"]))[..., None] * float(denoise)
    return np.clip(original * (1.0 - alpha) + inpainted_rgb * alpha, 0, 255).astype(np.uint8)


def run_qwen_masked_inpaint(rgb, mask, region_type, denoise, grow_mask_by, timeout, seed):
    """Run Qwen-Image-2512 masked inpaint on the full image for one mask.

    Graph node names are taken verbatim from the production
    remarkee-max-v2.api.json export (UnetLoaderGGUF + CLIPLoaderGGUF lumina2 +
    VAELoader qwen_image_vae + Power Lora Loader Lightning-4step @0.8 +
    KSampler steps=4 cfg=1 dpmpp_2m/sgm_uniform), so this is a proven node set,
    not a hand-guessed graph. VAEEncodeForInpaint noise-fills only the masked
    latent region; KSampler regenerates there; the unmasked area round-trips
    through VAE and is discarded by the feathered composite in repair_region.
    """
    import comfyui_client as cc

    height, width = rgb.shape[:2]

    if region_type == "text_glyph":
        positive = "smooth clean plain surface, no text, no letters, no glyphs, no watermark, no logo, even background"
        negative = "text, letters, glyphs, writing, watermark, logo, signature, scribbles"
    else:
        positive = "clean straight regular grid lines, even consistent geometry"
        negative = "warped, wavy, bent, curved, irregular, crooked lines"

    with tempfile.TemporaryDirectory(prefix="content-repair-qwen-") as tmpd:
        tmp = Path(tmpd)
        img_png = tmp / "src.png"
        mask_png = tmp / "mask.png"

        Image.fromarray(rgb, mode="RGB").save(img_png, format="PNG")
        # Save mask as RGB so ComfyUI LoadImage + ImageToMask(channel=red) get a
        # clean single-channel signal regardless of how LoadImage decodes it.
        mask_rgb = np.repeat(mask[..., None], 3, axis=2)
        Image.fromarray(mask_rgb, mode="RGB").save(mask_png, format="PNG")

        img_filename = cc.upload_image(str(img_png))
        mask_filename = cc.upload_image(str(mask_png))

        graph = {
            "1": {"class_type": "LoadImage", "inputs": {"image": img_filename}},
            "2": {"class_type": "LoadImage", "inputs": {"image": mask_filename}},
            "3": {"class_type": "ImageToMask", "inputs": {"image": ["2", 0], "channel": "red"}},
            "10": {"class_type": "UnetLoaderGGUF",
                   "inputs": {"unet_name": "qwen-image-2512-Q4_K_M.gguf"}},
            "11": {"class_type": "CLIPLoaderGGUF",
                   "inputs": {"clip_name": "Qwen2.5-VL-7B-Instruct-Q4_K_M.gguf", "type": "lumina2"}},
            "12": {"class_type": "VAELoader", "inputs": {"vae_name": "qwen_image_vae.safetensors"}},
            "13": {"class_type": "Power Lora Loader (rgthree)", "inputs": {
                "PowerLoraLoaderHeaderWidget": {"type": "PowerLoraLoaderHeaderWidget"},
                "lora_1": {"on": True, "lora": "Qwen-Image-2512-Lightning-4steps-V1.0-fp32.safetensors", "strength": 0.8},
                "model": ["10", 0], "clip": ["11", 0]}},
            "20": {"class_type": "CLIPTextEncode", "inputs": {"text": positive, "clip": ["13", 1]}},
            "21": {"class_type": "CLIPTextEncode", "inputs": {"text": negative, "clip": ["13", 1]}},
            "30": {"class_type": "VAEEncodeForInpaint", "inputs": {
                "pixels": ["1", 0], "vae": ["12", 0], "mask": ["3", 0],
                "grow_mask_by": int(grow_mask_by)}},
            "40": {"class_type": "KSampler", "inputs": {
                "seed": int(seed), "steps": 4, "cfg": 1.0,
                "sampler_name": "dpmpp_2m", "scheduler": "sgm_uniform",
                "denoise": float(denoise), "model": ["13", 0],
                "positive": ["20", 0], "negative": ["21", 0],
                "latent_image": ["30", 0]}},
            "50": {"class_type": "VAEDecode", "inputs": {"samples": ["40", 0], "vae": ["12", 0]}},
            "60": {"class_type": "SaveImage", "inputs": {
                "filename_prefix": "remarkee_content_repair", "images": ["50", 0]}},
        }

        prompt_id = cc.post_prompt(graph)
        entry = cc.wait_for_prompt(prompt_id, timeout=timeout)
        out_bytes = cc.get_output_image(entry)
        image = Image.open(io.BytesIO(out_bytes)).convert("RGB")
        if image.size != (width, height):
            image = image.resize((width, height), Image.Resampling.LANCZOS)
        return np.asarray(image)


def content_repair_quality_gates(metrics, cfg):
    failures = []
    if metrics["ssim_luma_window11_mean"] < 0.85:
        failures.append("ssim_luma_window11_mean_below_0.85")
    if metrics["tile_detail_ratio_p95"] > 1.8:
        failures.append("tile_detail_ratio_p95_above_1.8")
    if metrics["tile_detail_ratio_p95"] < 0.55:
        failures.append("tile_detail_ratio_p95_below_0.55")
    if (100.0 - metrics["psnr"]) / 100.0 > float(cfg["max_global_delta"]):
        failures.append("global_delta_proxy_above_limit")
    return {
        "accepted": not failures,
        "failures": failures,
        "version": "content-repair-local-quality-v1",
    }


def evaluate_detector_gate(baseline_scores, repaired_scores, tolerance=1.0):
    """The ship-original-if-worse gate -- the one that would have stopped the v1
    failure (deep 96.7->99.6, stat 59->97) from ever being shipped.

    Pure and unit-testable; called by the harness after it joins the external
    detector scores to the job. Inputs are normalized confidence dicts:
        {"deep": 96.7, "statistical": 59.0}   # 0..100, higher = more AI
    The harness is responsible for extracting each detector's confidence into
    this flat numeric form (the raw detector JSON schemas differ per provider).

    Rule: if ANY detector's repaired confidence exceeds its baseline by more
    than `tolerance` points, the repair made the image MORE detectable and the
    original (pre-repair) output must be shipped instead. A neutral/small
    improvement ships the repaired output.
    """
    deltas = {}
    failures = []
    for name, base in (baseline_scores or {}).items():
        rep = (repaired_scores or {}).get(name)
        if rep is None:
            continue
        delta = float(rep) - float(base)
        deltas[name] = round(delta, 3)
        if delta > float(tolerance):
            failures.append(f"{name}_worsened_by_{abs(round(delta,2))}")
    ship_original = bool(failures)
    return {
        "ship_original": ship_original,
        "deltas": deltas,
        "failures": failures,
        "tolerance": float(tolerance),
        "rule": "ship_original_if_any_detector_worsened_beyond_tolerance",
        "version": "detector-gate-v1",
    }


def evaluate_self_fingerprint(output_path, fingerprint_detector=None):
    """Self-fingerprint gate: run a GAN / universal-fake detector on the OUTPUT
    to catch repaired regions carrying a fresh diffusion fingerprint with
    mismatched acquisition stats vs their surroundings (the next likely failure
    mode after the Telea swap). The detector is an injected callable:
    fingerprint_detector(path) -> {"confidence": 0..1, "label": str}.

    Returns "not_evaluated" honestly when no detector is wired, rather than the
    v1 "external_required" stub. The worker/harness wires the callable on the
    box where the detector model lives.
    """
    if fingerprint_detector is None:
        return {"status": "not_evaluated", "reason": "no_fingerprint_detector_wired"}
    try:
        result = fingerprint_detector(output_path)
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "error": str(exc)[:500]}
    confidence = float(result.get("confidence", 0.0)) if isinstance(result, dict) else 0.0
    return {
        "status": "evaluated",
        "confidence": confidence,
        "label": (result or {}).get("label") if isinstance(result, dict) else None,
        "flagged": confidence >= 0.5,
        "version": "self-fingerprint-v1",
    }


def render_regions_mask(size, regions):
    width, height = size
    mask = np.zeros((height, width), dtype=np.uint8)
    for region in regions:
        region_mask = region.get("mask")
        if region_mask is not None:
            mask = np.maximum(mask, region_mask.astype(np.uint8))
            continue
        if "bbox" in region:
            x1, y1, x2, y2 = [int(v) for v in region["bbox"]]
            mask[y1:y2, x1:x2] = 255
    return Image.fromarray(mask, mode="L")


def mask_precision_recall(predicted_mask, truth_mask):
    pred = np.asarray(predicted_mask.convert("L")) > 0
    truth = np.asarray(truth_mask.convert("L")) > 0
    if pred.shape != truth.shape:
        truth = np.asarray(truth_mask.resize(predicted_mask.size, Image.Resampling.NEAREST).convert("L")) > 0
    tp = int(np.count_nonzero(pred & truth))
    fp = int(np.count_nonzero(pred & ~truth))
    fn = int(np.count_nonzero(~pred & truth))
    precision = tp / max(tp + fp, 1)
    recall = tp / max(tp + fn, 1)
    return {
        "precision": precision,
        "recall": recall,
        "tp": tp,
        "fp": fp,
        "fn": fn,
    }


def candidate_to_report(candidate):
    bbox = [int(v) for v in candidate["bbox"]]
    return {
        "id": candidate.get("id"),
        "type": candidate["type"],
        "score": candidate["score"],
        "scores": candidate.get("scores", {}),
        "bbox": bbox,
        "bbox_area_ratio": candidate.get("bbox_area_ratio", None) or 0.0,
        "mask_area_ratio": candidate.get("mask_area_ratio", 0.0),
        "diagnostics": candidate.get("diagnostics", {}),
        "repair": candidate.get("repair", {"applied": False}),
    }


def feather_mask(mask, radius):
    mask_img = Image.fromarray(mask, mode="L")
    if radius > 0:
        mask_img = mask_img.filter(ImageFilter.GaussianBlur(radius=radius))
    return np.asarray(mask_img).astype(np.float32) / 255.0


def bbox_area(bbox):
    x1, y1, x2, y2 = bbox
    return max(0, x2 - x1) * max(0, y2 - y1)


def iou(a, b):
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1 = max(ax1, bx1)
    iy1 = max(ay1, by1)
    ix2 = min(ax2, bx2)
    iy2 = min(ay2, by2)
    intersection = bbox_area([ix1, iy1, ix2, iy2])
    union = bbox_area(a) + bbox_area(b) - intersection
    return intersection / max(union, 1)


def union_bbox(a, b, width, height):
    return [
        max(0, min(a[0], b[0])),
        max(0, min(a[1], b[1])),
        min(width, max(a[2], b[2])),
        min(height, max(a[3], b[3])),
    ]


def region_seed(creator_id, seed_extra, region_idx, candidate):
    material = (
        f"content-repair-v1:{creator_id}:{seed_extra}:"
        f"{region_idx}:{candidate.get('type')}:{candidate.get('bbox')}"
    )
    return int(hashlib.sha256(material.encode("utf-8")).hexdigest()[:16], 16) & 0xFFFFFFFF


def clamp_float(value, low, high):
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        parsed = low
    if not np.isfinite(parsed):
        parsed = low
    return max(low, min(high, parsed))
