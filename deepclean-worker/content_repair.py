"""Internal Automatic Content Repair Lab v1.

Narrow scope on purpose:
- automatic localizer
- text/glyph + geometry/grid candidates only
- one pass, max three regions
- deterministic local repair and measurable ledger fields

The repair engine is currently local Telea inpaint. The module is structured so
the region repair function can be swapped for a ComfyUI/Qwen masked repair path
after the automatic localizer proves useful.
"""

import hashlib
import time

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
    "text_denoise": 0.72,
    "geometry_denoise": 0.28,
    "max_global_delta": 0.15,
}


def is_content_repair_lab(settings):
    return isinstance(settings, dict) and settings.get("mode") == "content-repair-lab"


def apply_content_repair_lab(input_path, output_path, creator_id, settings=None, seed_extra=""):
    cfg = normalize_content_repair_settings(settings)
    report = {
        "enabled": bool(cfg["enabled"]),
        "pipeline": "auto_content_repair_lab_v1",
        "applied": False,
        "repair_engine": "opencv_telea_inpaint_v1",
        "settings": public_settings(cfg),
        "localizer": {},
        "regions": [],
        "quality_gates": {},
        "measurement": {
            "detector_scores": "external_required",
            "realism_gate": "proxy_metrics",
            "self_fingerprint_gate": "external_required",
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
    _ = seed
    mask = candidate.get("mask")
    if mask is None or np.count_nonzero(mask) == 0:
        return rgb, {"applied": False, "reason": "empty_mask"}

    if candidate["type"] == "text_glyph":
        radius = 5
        blend_strength = float(cfg["text_denoise"])
        strategy = "remove_fill_no_glyph_regeneration"
    else:
        radius = 3
        blend_strength = float(cfg["geometry_denoise"])
        strategy = "structure_preserving_line_fill"

    bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
    inpainted = cv2.inpaint(bgr, mask, radius, cv2.INPAINT_TELEA)
    inpainted_rgb = cv2.cvtColor(inpainted, cv2.COLOR_BGR2RGB).astype(np.float32)
    original = rgb.astype(np.float32)

    alpha = feather_mask(mask, int(cfg["mask_feather_px"]))[..., None] * blend_strength
    repaired = np.clip(original * (1.0 - alpha) + inpainted_rgb * alpha, 0, 255).astype(np.uint8)
    return repaired, {
        "applied": True,
        "strategy": strategy,
        "inpaint_radius": radius,
        "blend_strength": blend_strength,
        "mask_pixels": int(np.count_nonzero(mask)),
    }


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
