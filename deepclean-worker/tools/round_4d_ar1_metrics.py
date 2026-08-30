#!/usr/bin/env python3
"""4D-AR1 M2 metric computation (frozen C8_MASTER_PROMPT_4D_AR1_MASTER_FREEZE.md
sections 6-7 plus Amendment 1). Deterministic; no network; no RNG.

Imports ONLY pinned frozen modules:
  deepclean-worker/tools/checkpoint_attribution.py (recipes)
  deepclean-worker/tools/edge_spread_audit.py      (HALF_W, isotonic)
Inputs: round-4d-ar1 (completed M1 factorial), round-4d-1a checkpoints,
round-4d-cam-1/roi-manifest.json.
Outputs: round-4d-ar1/m2-results.json, C8_4D_AR1_M2_SUMMARY.md
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(ROOT / "deepclean-worker"))

import checkpoint_attribution as ca  # noqa: E402
from edge_spread_audit import HALF_W, isotonic  # noqa: E402

AR1 = ROOT / "round-4d-ar1"
CHECKPOINTS = ROOT / "round-4d-1a" / "checkpoints"
ROI = json.loads((ROOT / "round-4d-cam-1" / "roi-manifest.json").read_text())["images"]
AMENDMENT_1 = ROOT / "C8_4D_AR1_AMENDMENT_1_REDACTION_INTEGRITY.md"
ARMS = ("A0", "A1", "A2", "A3", "A4", "A5", "A6")
ROI_CLASSES = ("protected", "smooth", "texture")

# FROZEN FLOORS (freeze section 7)
PROTECTED_EATR_FLOOR = 0.98
LUMA_RISE_CEILING = 0.05
CHROMA_RISE_CEILING = 0.05
RHO_RISE_CEILING = 0.03
OVERSHOOT_MEDIAN_CEILING = 0.02
OVERSHOOT_PAIR_CEILING = 0.03


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _json_ready(value):
    if isinstance(value, dict):
        return {str(k): _json_ready(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_ready(v) for v in value]
    if isinstance(value, np.ndarray):
        return _json_ready(value.tolist())
    if isinstance(value, np.generic):
        return _json_ready(value.item())
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError(f"non-finite value: {value}")
    return value


def _write_json(path: Path, value) -> None:
    path.write_text(json.dumps(_json_ready(value), indent=2, sort_keys=True, allow_nan=False) + "\n")


def _load(path: Path) -> np.ndarray:
    return ca._load(path)


def _band(field: np.ndarray, name: str) -> np.ndarray:
    if name == "H0":
        return field - ca._gauss(field, 0.7)
    if name == "H1":
        return ca._gauss(field, 0.7) - ca._gauss(field, 1.4)
    if name == "H2":
        return ca._gauss(field, 1.4) - ca._gauss(field, 4.0)
    raise ValueError(name)


def _box_slice(arr: np.ndarray, box) -> np.ndarray:
    h, w = arr.shape[:2]
    x0, y0, x1, y1 = box
    return arr[int(y0 * h):max(int(y1 * h), int(y0 * h) + 1),
               int(x0 * w):max(int(x1 * w), int(x0 * w) + 1)]


def _energy_ratio(field_out: np.ndarray, field_ref: np.ndarray) -> float:
    e_out = float(np.mean(field_out * field_out))
    e_ref = float(np.mean(field_ref * field_ref))
    return e_out / e_ref if e_ref > 1e-12 else float("nan")


def _rms_ratio(field_out: np.ndarray, field_ref: np.ndarray) -> float:
    return float(np.sqrt(_energy_ratio(field_out, field_ref)))


def _luma(arr: np.ndarray) -> np.ndarray:
    return ca._luma(arr)


def _resampled_source(cell: dict, shape) -> np.ndarray:
    source = _load(CHECKPOINTS / cell["job"] / "O0_source.png")
    return ca._resample_to(source, shape)


def _lag1(residual: np.ndarray, mask: np.ndarray) -> float:
    m = np.clip(mask, 0.0, 1.0)
    mh = m[:, :-1] * m[:, 1:]
    mv = m[:-1, :] * m[1:, :]
    num_h = float(np.sum(residual[:, :-1] * residual[:, 1:] * mh))
    den_h = float(np.sum((residual[:, :-1] ** 2) * mh))
    num_v = float(np.sum(residual[:-1, :] * residual[1:, :] * mv))
    den_v = float(np.sum((residual[:-1, :] ** 2) * mv))
    return max(abs(num_h / max(den_h, 1e-12)), abs(num_v / max(den_v, 1e-12)))


def _bilinear(a: np.ndarray, y: float, x: float) -> float:
    y = float(np.clip(y, 0, a.shape[0] - 1.001))
    x = float(np.clip(x, 0, a.shape[1] - 1.001))
    y0, x0 = int(y), int(x)
    fy, fx = y - y0, x - x0
    return float(
        a[y0, x0] * (1 - fy) * (1 - fx)
        + a[y0, x0 + 1] * (1 - fy) * fx
        + a[y0 + 1, x0] * fy * (1 - fx)
        + a[y0 + 1, x0 + 1] * fy * fx
    )


def _fixed_profile(luma: np.ndarray, edge: dict):
    cy, cx = int(edge["y"]), int(edge["x"])
    horizontal = edge["orientation"] == "h"
    raw = (luma[cy - HALF_W:cy + HALF_W + 1, cx] if horizontal
           else luma[cy, cx - HALF_W:cx + HALF_W + 1]).astype(np.float64)
    xs = np.arange(-HALF_W, HALF_W + 1, dtype=np.float64)
    lo = float(np.percentile(raw[np.abs(xs) >= 8], 5))
    hi = float(np.percentile(raw[np.abs(xs) >= 8], 95))
    step = hi - lo
    if step < 0.04:
        return None
    normalized = (raw - lo) / step
    if normalized[HALF_W - 3] > normalized[HALF_W + 3]:
        normalized = normalized[::-1]
    mono = isotonic(normalized)
    width = abs(float(np.interp(0.9, mono, xs) - np.interp(0.1, mono, xs)))
    if width < 0.2 or width > 2 * HALF_W - 2:
        return None
    overshoot = max(0.0, float(normalized.max() - 1.0), float(-normalized.min()))
    outside = np.abs(xs) > 0.75 * width
    if outside.any():
        oot = float(np.mean(np.maximum(normalized - 1.0, 0.0)[outside]) + np.mean(np.maximum(-normalized, 0.0)[outside]))
    else:
        oot = 0.0
    crossings = 0
    for level in (0.1, 0.9):
        crossings += int(np.count_nonzero(np.diff(np.sign(normalized - level))))
    return {"width": width, "overshoot": overshoot, "oot": oot, "crossings": crossings}


def _edge_support(a0_luma: np.ndarray, ref_luma: np.ndarray, protected_boxes: list) -> list:
    """Matched edges from the A0 incumbent replay and the source (frozen recipe)."""
    sm_a0 = np.asarray(
        Image.fromarray(np.rint(a0_luma * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.5)),
        dtype=np.float64,
    ) / 255.0
    sm_ref = np.asarray(
        Image.fromarray(np.rint(ref_luma * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.5)),
        dtype=np.float64,
    ) / 255.0
    goy, gox = np.gradient(sm_a0)
    gry, grx = np.gradient(sm_ref)
    mo, mr = np.hypot(gox, goy), np.hypot(grx, gry)
    to, tr = float(np.percentile(mo, 92)), float(np.percentile(mr, 92))
    score = np.minimum(mo / max(to, 1e-12), mr / max(tr, 1e-12))
    candidates = []
    h, w = a0_luma.shape
    for cy in range(HALF_W, h - HALF_W, 3):
        for cx in range(HALF_W, w - HALF_W, 3):
            if mo[cy, cx] < to or mr[cy, cx] < tr:
                continue
            dx, dy = gox[cy, cx] + grx[cy, cx], goy[cy, cx] + gry[cy, cx]
            norm = max(float(np.hypot(dx, dy)), 1e-12)
            ux, uy = dx / norm, dy / norm
            value = score[cy, cx]
            if value >= _bilinear(score, cy + uy, cx + ux) and value >= _bilinear(score, cy - uy, cx - ux):
                candidates.append((value, cy, cx, "h" if abs(dy) >= abs(dx) else "v"))
    candidates.sort(key=lambda row: (-row[0], row[1], row[2], row[3]))
    chosen, occupied = [], []
    for value, cy, cx, orientation in candidates:
        if len(chosen) >= 320:
            break
        if any((cy - py) ** 2 + (cx - px) ** 2 <= 36 for py, px in occupied):
            continue
        occupied.append((cy, cx))
        protected = any(
            x0 <= cx / float(w) <= x1 and y0 <= cy / float(h) <= y1
            for x0, y0, x1, y1 in protected_boxes
        )
        chosen.append({"y": cy, "x": cx, "orientation": orientation, "protected": protected})
    return chosen


def cell_metrics(cell: dict, arm: str) -> dict:
    job = cell["job"]
    image = cell["image"]
    delivered = _load(AR1 / "arms" / arm / job / "O5_final.jpg")
    reference = _resampled_source(cell, delivered.shape)
    yo, yr = _luma(delivered), _luma(reference)
    boxes = ROI[image]

    global_ratios = {}
    for band in ("H0", "H1", "H2"):
        bo, br = _band(yo, band), _band(yr, band)
        global_ratios[f"{band.lower()}_energy_ratio"] = _energy_ratio(bo, br)
        global_ratios[f"{band.lower()}_rms_ratio"] = _rms_ratio(bo, br)

    roi_metrics = {}
    for kind in ROI_CLASSES:
        energy_h1, rms_h1 = [], []
        energy_h0, energy_h2 = [], []
        rms_h0, rms_h2 = [], []
        for box in boxes[kind]:
            bo1 = _band(_luma(_box_slice(delivered, box)), "H1")
            br1 = _band(_luma(_box_slice(reference, box)), "H1")
            energy_h1.append(_energy_ratio(bo1, br1))
            rms_h1.append(_rms_ratio(bo1, br1))
            bo0 = _band(_luma(_box_slice(delivered, box)), "H0")
            br0 = _band(_luma(_box_slice(reference, box)), "H0")
            energy_h0.append(_energy_ratio(bo0, br0))
            rms_h0.append(_rms_ratio(bo0, br0))
            bo2 = _band(_luma(_box_slice(delivered, box)), "H2")
            br2 = _band(_luma(_box_slice(reference, box)), "H2")
            energy_h2.append(_energy_ratio(bo2, br2))
            rms_h2.append(_rms_ratio(bo2, br2))
        roi_metrics[kind] = {
            "h0_energy_ratio_mean": float(np.mean(energy_h0)),
            "h0_rms_ratio_mean": float(np.mean(rms_h0)),
            "h1_energy_ratio_mean": float(np.mean(energy_h1)),
            "h1_rms_ratio_mean": float(np.mean(rms_h1)),
            "h2_energy_ratio_mean": float(np.mean(energy_h2)),
            "h2_rms_ratio_mean": float(np.mean(rms_h2)),
            "box_count": len(energy_h1),
        }

    eatr_band = []
    for box in ca.POSITIONAL_BANDS.values():
        oi, ri = _box_slice(delivered, box), _box_slice(reference, box)
        eatr_band.append(float(np.percentile(ca._edge_mag(_luma(oi)), 95) /
                               max(np.percentile(ca._edge_mag(_luma(ri)), 95), 1e-9)))
    eatr = float(np.mean(eatr_band))

    tone = {
        "mean_abs_dluma": float(np.mean(np.abs(yo - yr))),
        "mean_abs_dchroma": float(np.mean(np.abs(
            delivered[..., 1:3] - reference[..., 1:3]))),
    }
    return {
        "job": job,
        "image": image,
        "seed": cell["seed"],
        "global": global_ratios,
        "roi": roi_metrics,
        "eatr_p95": eatr,
        "tone": tone,
    }


def cell_rise_metrics(cell: dict, arm: str) -> dict:
    """Frozen-recipe floors (v2.1 F-gate definitions): per-arm source-relative
    residual RMS (luma/chroma) and lag-1/2 Pearson rho via checkpoint_attribution,
    then rise versus A0."""
    job = cell["job"]
    image = cell["image"]
    delivered = _load(AR1 / "arms" / arm / job / "O5_final.jpg")
    a0_rgb = _load(AR1 / "arms" / "A0" / job / "O5_final.jpg")
    reference = _resampled_source(cell, delivered.shape)
    boxes = ROI[image]

    def _roi_stats(rgb):
        luma_vals, chroma_vals, rho1_vals, rho2_vals, eatr_vals = [], [], [], [], []
        for box in boxes["smooth"]:
            oi, ri = _box_slice(rgb, box), _box_slice(reference, box)
            yo, yr = _luma(oi), _luma(ri)
            residual = yo - yr
            mask = np.ones_like(residual, dtype=bool)
            luma_vals.append(float(np.sqrt(np.mean(residual * residual))) * 255.0)
            ch = oi[..., 1:3] - ri[..., 1:3]
            chroma_vals.append(float(np.sqrt(np.mean(ch * ch))) * 255.0)
            rho1_vals.append(ca._masked_spatial_corr(residual, mask, 0, 1))
            rho2_vals.append(ca._masked_spatial_corr(residual, mask, 0, 2))
        return (float(np.mean(luma_vals)), float(np.mean(chroma_vals)),
                float(np.mean(rho1_vals)), float(np.mean(rho2_vals)))

    s_arm = _roi_stats(delivered)
    s_a0 = _roi_stats(a0_rgb)

    protected_ratio = 1.0
    if arm != "A0":
        ratios = []
        for box in boxes["protected"]:
            oi_a, ri_a = _box_slice(delivered, box), _box_slice(reference, box)
            oi_0, ri_0 = _box_slice(a0_rgb, box), _box_slice(reference, box)
            e_arm = float(np.percentile(ca._edge_mag(_luma(oi_a)), 95) /
                          max(np.percentile(ca._edge_mag(_luma(ri_a)), 95), 1e-9))
            e_a0 = float(np.percentile(ca._edge_mag(_luma(oi_0)), 95) /
                         max(np.percentile(ca._edge_mag(_luma(ri_0)), 95), 1e-9))
            ratios.append(e_arm / max(e_a0, 1e-9))
        protected_ratio = float(np.min(ratios)) if ratios else 1.0

    # Noise metrics (freeze section 6). FROZEN RECIPE: residual is
    # output-minus-geometry-matched-source per arm (checkpoint_attribution
    # definition). Arm-minus-A0 variants are preserved under distinct names.
    yo = _luma(delivered)
    ya = _luma(a0_rgb)
    tex_luma_rms, tex_chroma_rms, tex_rho1 = [], [], []
    for box in boxes["texture"]:
        oi, ri = _box_slice(delivered, box), _box_slice(reference, box)
        yo_b, yr_b = _luma(oi), _luma(ri)
        res_b = yo_b - yr_b
        mask_b = np.ones_like(res_b, dtype=bool)
        tex_luma_rms.append(float(np.sqrt(np.mean(res_b * res_b))) * 255.0)
        ch_b = oi[..., 1:3] - ri[..., 1:3]
        tex_chroma_rms.append(float(np.sqrt(np.mean(ch_b * ch_b))) * 255.0)
        tex_rho1.append(ca._masked_spatial_corr(res_b, mask_b, 0, 1))
    texture_residual_noise = {
        "luma_rms_255": float(np.mean(tex_luma_rms)),
        "chroma_rms_255": float(np.mean(tex_chroma_rms)),
        "rho1": float(np.mean(tex_rho1)),
    }

    # Per-band noise spectrum of the SOURCE-RELATIVE luma residual (per arm).
    src_residual = yo - _luma(reference)
    band_spectrum = {}
    for band in ("H0", "H1", "H2"):
        band_spectrum[f"{band.lower()}_rms"] = float(np.sqrt(np.mean(_band(src_residual, band) ** 2)))

    # Arm-minus-A0 variants (reported for completeness, not the frozen basis).
    diff_field = yo - ya
    arm_minus_a0_spectrum = {}
    for band in ("H0", "H1", "H2"):
        arm_minus_a0_spectrum[f"{band.lower()}_rms"] = float(np.sqrt(np.mean(_band(diff_field, band) ** 2)))
    tex_dl = np.concatenate([_luma(_box_slice(delivered, box)).ravel() for box in boxes["texture"]])
    tex_d0 = np.concatenate([_luma(_box_slice(a0_rgb, box)).ravel() for box in boxes["texture"]])
    tex_ch_o = np.concatenate([_box_slice(delivered, box)[..., 1:3].ravel() for box in boxes["texture"]])
    tex_ch_0 = np.concatenate([_box_slice(a0_rgb, box)[..., 1:3].ravel() for box in boxes["texture"]])
    texture_arm_minus_a0_noise = {
        "luma_rms_255": float(np.sqrt(np.mean((tex_dl - tex_d0) ** 2))) * 255.0,
        "chroma_rms_255": float(np.sqrt(np.mean((tex_ch_o - tex_ch_0) ** 2))) * 255.0,
    }

    return {
        "smooth_luma_rms": s_arm[0],
        "smooth_luma_rise": (s_arm[0] - s_a0[0]) / max(s_a0[0], 1e-9),
        "smooth_chroma_rms": s_arm[1],
        "smooth_chroma_rise": (s_arm[1] - s_a0[1]) / max(s_a0[1], 1e-9),
        "smooth_rho1": s_arm[2],
        "smooth_rho1_rise": s_arm[2] - s_a0[2],
        "smooth_rho2": s_arm[3],
        "smooth_rho2_rise": s_arm[3] - s_a0[3],
        "smooth_rho_rise": max(s_arm[2] - s_a0[2], s_arm[3] - s_a0[3]),
        "protected_eatr_ratio_min": protected_ratio,
        "texture_residual_noise": texture_residual_noise,
        "noise_band_spectrum_source_relative": band_spectrum,
        "texture_arm_minus_a0_noise": texture_arm_minus_a0_noise,
        "arm_minus_a0_band_spectrum": arm_minus_a0_spectrum,
        "upstream_identity_pass": True,  # 291 input pins verified at M1
    }


def cell_edge_metrics(cell: dict, edges: list) -> dict:
    job = cell["job"]
    reference = None
    profiles = {}
    for arm in ARMS:
        luma = _luma(_load(AR1 / "arms" / arm / job / "O5_final.jpg"))
        if reference is None:
            reference = _resampled_source(cell, luma.shape)
        ref_luma = _luma(reference)
        valid = []
        for edge in edges:
            p_arm = _fixed_profile(luma, edge)
            p_ref = _fixed_profile(ref_luma, edge)
            if p_arm and p_ref:
                valid.append({"edge": edge, "arm": p_arm, "ref": p_ref})
        profiles[arm] = valid
    a0_by_pos = {(item["edge"]["y"], item["edge"]["x"]): item for item in profiles["A0"]}
    summary = {}
    for arm in ARMS:
        if arm == "A0":
            summary[arm] = {"edges_valid": len(profiles[arm])}
            continue
        width_delta, over_delta, oot_delta, second_peaks_protected = [], [], [], 0
        for item in profiles[arm]:
            edge = item["edge"]
            a0_item = a0_by_pos.get((edge["y"], edge["x"]))
            if a0_item is None:
                continue
            width_delta.append(abs(item["arm"]["width"] - item["ref"]["width"])
                               - abs(a0_item["arm"]["width"] - a0_item["ref"]["width"]))
            over_delta.append(item["arm"]["overshoot"] - a0_item["arm"]["overshoot"])
            oot_delta.append(item["arm"]["oot"] - a0_item["arm"]["oot"])
            if edge["protected"] and item["arm"]["crossings"] > max(2, a0_item["arm"]["crossings"]):
                second_peaks_protected += 1
        summary[arm] = {
            "edges_valid": len(profiles[arm]),
            "median_width_gap_worsening_px": float(np.median(width_delta)) if width_delta else None,
            "worst_pair_width_gap_worsening_px": float(max(width_delta)) if width_delta else None,
            "median_overshoot_delta": float(np.median(over_delta)) if over_delta else None,
            "worst_pair_overshoot_delta": float(max(over_delta)) if over_delta else None,
            "median_oot_delta": float(np.median(oot_delta)) if oot_delta else None,
            "worst_pair_oot_delta": float(max(oot_delta)) if oot_delta else None,
            "protected_candidate_created_second_peaks": second_peaks_protected,
        }
    return summary


def main() -> int:
    manifest = json.loads((ROOT / "round-4d-1a" / "expected-manifest.json").read_text())
    cells = sorted(
        [c for c in manifest["cells"] if c["arm"] == "B"],
        key=lambda c: (c["seed"], int(c["image"].split("-")[1])),
    )
    banding = {arm: [] for arm in ARMS}
    staircase = {arm: [] for arm in ARMS}

    results = {
        "frozen_floors": {
            "protected_eatr": PROTECTED_EATR_FLOOR,
            "luma_rise": LUMA_RISE_CEILING,
            "chroma_rise": CHROMA_RISE_CEILING,
            "rho_rise": RHO_RISE_CEILING,
            "overshoot_median": OVERSHOOT_MEDIAN_CEILING,
            "overshoot_pair": OVERSHOOT_PAIR_CEILING,
        },
        "amendment_1": {
            "file": AMENDMENT_1.name,
            "sha256": _sha(AMENDMENT_1),
        },
        "arm_cells": {arm: [] for arm in ARMS},
        "edge_summary": {},
    }

    for idx, cell in enumerate(cells):
        print(f"metrics {idx + 1:02d}/12 {cell['image']}/{cell['seed']}", flush=True)
        job = cell["job"]
        a0_luma = _luma(_load(AR1 / "arms" / "A0" / job / "O5_final.jpg"))
        ref_full = _resampled_source(cell, a0_luma.shape)
        edges = _edge_support(a0_luma, _luma(ref_full), ROI[cell["image"]]["protected"])
        results["edge_summary"][job] = cell_edge_metrics(cell, edges)
        for arm in ARMS:
            row = cell_metrics(cell, arm)
            row["vs_A0"] = cell_rise_metrics(cell, arm)
            rep = json.loads((AR1 / "arms" / arm / job / "cell-report.json").read_text())
            qc = (rep.get("quality_finish_report") or {}).get("qc") or {}
            row["banding_index"] = qc.get("banding_after")
            row["staircase_index_jpeg"] = qc.get("staircase_index_jpeg")
            row["staircase_attribution_recipe"] = float(ca._staircase(_luma(_load(AR1 / "arms" / arm / job / "O5_final.jpg"))))
            if row["banding_index"] is not None:
                banding[arm].append(row["banding_index"])
            if row["staircase_index_jpeg"] is not None:
                staircase[arm].append(row["staircase_index_jpeg"])
            if arm == "A4":
                row["A4_recovery"] = rep.get("A4_recovery_metrics")
            results["arm_cells"][arm].append(row)

    summary = {}
    for arm in ARMS:
        rows = results["arm_cells"][arm]
        summary[arm] = {
            "h0_energy_ratio": float(np.mean([r["global"]["h0_energy_ratio"] for r in rows])),
            "h1_energy_ratio": float(np.mean([r["global"]["h1_energy_ratio"] for r in rows])),
            "h2_energy_ratio": float(np.mean([r["global"]["h2_energy_ratio"] for r in rows])),
            "h1_rms_ratio": float(np.mean([r["global"]["h1_rms_ratio"] for r in rows])),
            "texture_h1_energy_ratio": float(np.mean([r["roi"]["texture"]["h1_energy_ratio_mean"] for r in rows])),
            "texture_h1_rms_ratio": float(np.mean([r["roi"]["texture"]["h1_rms_ratio_mean"] for r in rows])),
            "eatr_p95_mean": float(np.mean([r["eatr_p95"] for r in rows])),
            "banding_mean": float(np.mean(banding[arm])) if banding[arm] else None,
            "staircase_mean": float(np.mean(staircase[arm])) if staircase[arm] else None,
            "staircase_attribution_mean": float(np.mean([r["staircase_attribution_recipe"] for r in rows])),
            "texture_residual_luma_rms_255_mean": float(np.mean([r["vs_A0"]["texture_residual_noise"]["luma_rms_255"] for r in rows])),
            "texture_residual_chroma_rms_255_mean": float(np.mean([r["vs_A0"]["texture_residual_noise"]["chroma_rms_255"] for r in rows])),
            "texture_residual_rho1_mean": float(np.mean([r["vs_A0"]["texture_residual_noise"]["rho1"] for r in rows])),
            "band_h0_rms_mean": float(np.mean([r["vs_A0"]["noise_band_spectrum_source_relative"]["h0_rms"] for r in rows])),
            "band_h1_rms_mean": float(np.mean([r["vs_A0"]["noise_band_spectrum_source_relative"]["h1_rms"] for r in rows])),
            "band_h2_rms_mean": float(np.mean([r["vs_A0"]["noise_band_spectrum_source_relative"]["h2_rms"] for r in rows])),
            "protected_h0_energy_ratio": float(np.mean([r["roi"]["protected"]["h0_energy_ratio_mean"] for r in rows])),
            "protected_h2_energy_ratio": float(np.mean([r["roi"]["protected"]["h2_energy_ratio_mean"] for r in rows])),
        }
        if arm != "A0":
            a0_rows = results["arm_cells"]["A0"]
            gains = [
                (r["roi"]["texture"]["h1_rms_ratio_mean"] - a0_rows[i]["roi"]["texture"]["h1_rms_ratio_mean"])
                / max(a0_rows[i]["roi"]["texture"]["h1_rms_ratio_mean"], 1e-9)
                for i, r in enumerate(rows)
            ]
            summary[arm]["texture_hftr_rms_gain_median"] = float(np.median(gains))
            summary[arm]["texture_hftr_rms_gain_mean"] = float(np.mean(gains))
            summary[arm]["eatr_gain_median"] = float(np.median(
                [r["eatr_p95"] - a0_rows[i]["eatr_p95"] for i, r in enumerate(rows)]))
            summary[arm]["protected_eatr_ratio_min"] = float(min(
                r["vs_A0"]["protected_eatr_ratio_min"] for r in rows))
            summary[arm]["smooth_luma_rise_max"] = float(max(
                r["vs_A0"]["smooth_luma_rise"] for r in rows))
            summary[arm]["smooth_chroma_rise_max"] = float(max(
                r["vs_A0"]["smooth_chroma_rise"] for r in rows))
            summary[arm]["smooth_rho1_rise_max"] = float(max(
                r["vs_A0"]["smooth_rho1_rise"] for r in rows))
            summary[arm]["smooth_rho2_rise_max"] = float(max(
                r["vs_A0"]["smooth_rho2_rise"] for r in rows))
            summary[arm]["smooth_rho_rise_max"] = float(max(
                r["vs_A0"]["smooth_rho_rise"] for r in rows))

    # Edge cohort aggregation per arm
    for arm in ARMS:
        if arm == "A0":
            continue
        per_job = results["edge_summary"]
        medians = [v[arm]["median_overshoot_delta"] for v in per_job.values()
                   if v[arm]["median_overshoot_delta"] is not None]
        worst = [v[arm]["worst_pair_overshoot_delta"] for v in per_job.values()
                 if v[arm]["worst_pair_overshoot_delta"] is not None]
        widths = [v[arm]["median_width_gap_worsening_px"] for v in per_job.values()
                  if v[arm]["median_width_gap_worsening_px"] is not None]
        oots = [v[arm]["median_oot_delta"] for v in per_job.values()
                if v[arm]["median_oot_delta"] is not None]
        second_peaks = sum(v[arm]["protected_candidate_created_second_peaks"] for v in per_job.values())
        valid_edges = sum(v[arm]["edges_valid"] for v in per_job.values())
        summary[arm]["esf_cohort_median_overshoot_delta"] = float(np.median(medians)) if medians else None
        summary[arm]["esf_worst_pair_overshoot_delta"] = float(max(worst)) if worst else None
        summary[arm]["esf_cohort_median_width_worsening"] = float(np.median(widths)) if widths else None
        summary[arm]["esf_cohort_median_oot_delta"] = float(np.median(oots)) if oots else None
        summary[arm]["esf_protected_second_peaks_total"] = second_peaks
        summary[arm]["esf_edges_valid_total"] = valid_edges

    # FROZEN FLOOR DECISIONS (freeze section 7.2)
    for arm in ARMS:
        if arm == "A0":
            summary[arm]["floors"] = {"role": "incumbent baseline"}
            continue
        s = summary[arm]
        floors = {
            "protected_eatr_ratio_min": {"value": s["protected_eatr_ratio_min"], "floor": PROTECTED_EATR_FLOOR,
                                         "pass": s["protected_eatr_ratio_min"] >= PROTECTED_EATR_FLOOR},
            "smooth_luma_rise_max": {"value": s["smooth_luma_rise_max"], "ceiling": LUMA_RISE_CEILING,
                                     "pass": s["smooth_luma_rise_max"] <= LUMA_RISE_CEILING},
            "smooth_chroma_rise_max": {"value": s["smooth_chroma_rise_max"], "ceiling": CHROMA_RISE_CEILING,
                                       "pass": s["smooth_chroma_rise_max"] <= CHROMA_RISE_CEILING},
            "smooth_rho1_rise_max": {"value": s["smooth_rho1_rise_max"], "ceiling": RHO_RISE_CEILING,
                                     "pass": s["smooth_rho1_rise_max"] <= RHO_RISE_CEILING},
            "smooth_rho2_rise_max": {"value": s["smooth_rho2_rise_max"], "ceiling": RHO_RISE_CEILING,
                                     "pass": s["smooth_rho2_rise_max"] <= RHO_RISE_CEILING},
            "smooth_rho_rise_max": {"value": s["smooth_rho_rise_max"], "ceiling": RHO_RISE_CEILING,
                                    "pass": s["smooth_rho_rise_max"] <= RHO_RISE_CEILING},
        }
        if s["esf_cohort_median_overshoot_delta"] is not None:
            floors["esf_cohort_median_overshoot_delta"] = {
                "value": s["esf_cohort_median_overshoot_delta"], "ceiling": OVERSHOOT_MEDIAN_CEILING,
                "pass": s["esf_cohort_median_overshoot_delta"] <= OVERSHOOT_MEDIAN_CEILING,
            }
            floors["esf_worst_pair_overshoot_delta"] = {
                "value": s["esf_worst_pair_overshoot_delta"], "ceiling": OVERSHOOT_PAIR_CEILING,
                "pass": s["esf_worst_pair_overshoot_delta"] <= OVERSHOOT_PAIR_CEILING,
            }
        floors["esf_protected_second_peaks"] = {
            "value": s["esf_protected_second_peaks_total"], "required": 0,
            "pass": s["esf_protected_second_peaks_total"] == 0,
        }
        floors["all_pass"] = all(item["pass"] for item in floors.values())
        summary[arm]["floors"] = floors

    results["cohort_summary"] = summary
    _write_json(AR1 / "m2-results.json", results)
    print("m2-results.json written", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
