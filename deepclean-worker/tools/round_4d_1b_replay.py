#!/usr/bin/env python3
"""Fidelity-first, replay-only 4D-1b experiment harness.

No network client is imported.  The harness consumes the archived 4D-1a B
checkpoints, verifies every v2.1 evidence pin, proves unchanged-O2 downstream
fidelity, and only then permits the frozen OR->O2 H1 candidate to run.
"""

from __future__ import annotations

import hashlib
import json
import math
import platform
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

TOOLS_DIR = Path(__file__).resolve().parent
WORKER_DIR = TOOLS_DIR.parent
ROOT = WORKER_DIR.parent
sys.path.insert(0, str(TOOLS_DIR))
sys.path.insert(0, str(WORKER_DIR))

import checkpoint_attribution as ca  # noqa: E402
from checkpoint_capture import pixel_sha256  # noqa: E402
from edge_spread_audit import HALF_W, isotonic  # noqa: E402
from max_cx_remint import _histogram_match  # noqa: E402
from quality_finish import apply_quality_finish  # noqa: E402
from transfer_4d_1b import build_candidate  # noqa: E402


INPUT_DIR = ROOT / "round-4d-1a"
CHECKPOINTS = INPUT_DIR / "checkpoints"
MANIFEST_PATH = INPUT_DIR / "expected-manifest.json"
SETTINGS_PATH = INPUT_DIR / "cell-settings.json"
PINS_PATH = INPUT_DIR / "evidence-pins.json"
ROI_PATH = ROOT / "round-4d-cam-1" / "roi-manifest.json"
OUT = ROOT / "round-4d-1b-replay"
REPORT_PATH = ROOT / "C8_4D_1B_REPLAY_REPORT.md"
EDGE_ARTIFACT = OUT / "edge-support-artifact.json"
EDGE_PIN = OUT / "pre-candidate-edge-pin.json"

REQUIRED_CHECKPOINTS = (
    "O0_source.png",
    "O1_postwash.png",
    "OR_postresample.png",
    "O2_precamera.png",
    "O3_stage1.png",
    "O4_preencode.png",
    "O5_final.png",
)
HARD_IMAGES = {"IMG-5", "IMG-6", "IMG-9", "IMG-11"}
SIX_IMAGES = ("IMG-5", "IMG-6", "IMG-7", "IMG-8", "IMG-9", "IMG-11")


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json_write(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_json_ready(value), indent=2, sort_keys=True, allow_nan=False) + "\n")


def _json_ready(value):
    """Convert NumPy report scalars without relaxing strict finite JSON."""
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_ready(item) for item in value]
    if isinstance(value, np.ndarray):
        return _json_ready(value.tolist())
    if isinstance(value, np.generic):
        return _json_ready(value.item())
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError(f"non-finite value cannot enter deterministic JSON: {value}")
    return value


def _load_rgb(path: Path) -> np.ndarray:
    return np.asarray(Image.open(path).convert("RGB"), dtype=np.uint8)


def _delta_distribution(actual: Path, expected: Path) -> dict:
    a, e = _load_rgb(actual).astype(np.int16), _load_rgb(expected).astype(np.int16)
    if a.shape != e.shape:
        return {"shape_actual": list(a.shape), "shape_expected": list(e.shape), "shape_match": False}
    delta = a - e
    absolute = np.abs(delta)
    unique, counts = np.unique(delta, return_counts=True)
    ranked = sorted(zip(counts.tolist(), unique.tolist()), reverse=True)[:15]
    return {
        "shape_match": True,
        "changed_samples": int(np.count_nonzero(delta)),
        "changed_pixels": int(np.count_nonzero(np.any(delta != 0, axis=2))),
        "sample_count": int(delta.size),
        "max_abs_lsb": int(absolute.max()),
        "mean_abs_lsb": float(np.mean(absolute)),
        "rms_lsb": float(np.sqrt(np.mean(delta.astype(np.float64) ** 2))),
        "channel_max_abs_lsb": [int(absolute[..., c].max()) for c in range(3)],
        "most_common_signed_deltas": [{"delta": int(v), "count": int(n)} for n, v in ranked],
    }


def verify_inputs() -> tuple[dict, dict, list[dict], list[dict]]:
    pins = json.loads(PINS_PATH.read_text())
    pin_rows = []
    for rel, expected in sorted(pins.items()):
        path = ROOT / rel
        actual = _sha(path) if path.is_file() else None
        pin_rows.append({"path": rel, "expected": expected, "actual": actual, "pass": actual == expected})
    if not all(row["pass"] for row in pin_rows):
        raise RuntimeError("evidence pin mismatch")

    manifest = json.loads(MANIFEST_PATH.read_text())
    settings = json.loads(SETTINGS_PATH.read_text())
    manifest_rows = []
    for cell in manifest.get("cells", []):
        jid = cell["job"]
        for name in REQUIRED_CHECKPOINTS:
            path = CHECKPOINTS / jid / name
            expected = cell.get("files", {}).get(name)
            actual = pixel_sha256(path) if path.is_file() else None
            manifest_rows.append(
                {"job": jid, "file": name, "expected": expected, "actual": actual, "pass": actual == expected}
            )
    if len(manifest.get("cells", [])) != 24 or not all(row["pass"] for row in manifest_rows):
        raise RuntimeError("checkpoint manifest mismatch or incomplete 24-cell manifest")

    b_cells = sorted(
        (cell for cell in manifest["cells"] if cell["arm"] == "B"),
        key=lambda row: (int(row["image"].split("-")[1]), row["seed"]),
    )
    if len(b_cells) != 12:
        raise RuntimeError(f"expected 12 B cells, found {len(b_cells)}")
    setting_rows = []
    jobs = settings.get("jobs", {})
    for cell in b_cells:
        jid = cell["job"]
        block = jobs.get(jid)
        executed = block.get("executed") if isinstance(block, dict) else None
        errors = []
        if not isinstance(executed, dict):
            errors.append("executed block absent")
        else:
            checks = {
                "engine": executed.get("engine") == "ds_remint_v8_8",
                "profile": executed.get("profile") == "max",
                "effective_seed": executed.get("effective_seed") == f"lab:{cell['seed']}",
                "output_mode": executed.get("output_mode") == "stripped",
                "finish_preset": executed.get("finish_preset_selected") == "strong",
                "finish_qc": executed.get("finish_qc_passed") is True,
                "stage1": executed.get("stage1_encode") == {"quality": 92, "subsampling": "4:2:0"},
                "qf": executed.get("qf_encode")
                == {"quality": 97, "subsampling": "4:4:4", "single_encode": True},
                "finalize": executed.get("finalize_passthrough") is True,
                "naturalization": executed.get("finalize", {}).get("photo_naturalization_enabled") is False,
            }
            errors.extend(name for name, passed in checks.items() if not passed)
        setting_rows.append({"job": jid, "image": cell["image"], "seed": cell["seed"], "errors": errors, "pass": not errors})
    if not all(row["pass"] for row in setting_rows):
        raise RuntimeError("executed settings mismatch")
    return manifest, settings, b_cells, pin_rows + manifest_rows + setting_rows


def _finish_settings(block: dict) -> dict:
    requested = block["finish"]
    executed = block["executed"]
    return {
        "mode": "quality-finish",
        "quality_finish": {
            "preset": executed["finish_preset_selected"],
            "scale": executed["finish"]["scale"],
            "overrides": executed["finish"]["overrides"],
            "material_clean": bool(requested["material_clean"]),
            "finish_mode": "fixed-executed-replay",
        },
    }


def replay_downstream(input_rgb: np.ndarray, cell: dict, block: dict, target: Path) -> dict:
    target.mkdir(parents=True, exist_ok=True)
    source_path = CHECKPOINTS / cell["job"] / "O0_source.png"
    source = Image.open(source_path).convert("RGB")
    image = Image.fromarray(input_rgb, mode="RGB")
    remint = block["remint"]
    reference = source.resize(image.size, Image.Resampling.LANCZOS)
    tone_locked = _histogram_match(image, reference, float(remint["color_restore_strength"]))

    stage1_jpeg = target / "stage1-q92.jpg"
    tone_locked.save(
        stage1_jpeg,
        format="JPEG",
        quality=int(block["executed"]["stage1_encode"]["quality"]),
        optimize=True,
        subsampling=block["executed"]["stage1_encode"]["subsampling"],
    )
    o3_path = target / "O3_stage1.png"
    with Image.open(stage1_jpeg) as decoded:
        decoded.convert("RGB").save(o3_path, format="PNG")

    qf_jpeg = target / "qf-q97.jpg"
    qf_report = apply_quality_finish(
        input_path=stage1_jpeg,
        output_path=qf_jpeg,
        settings=_finish_settings(block),
        seed_extra=block["executed"]["effective_seed"],
        creator_id="unused-by-quality-finish",
        reference=source_path,
        checkpoint_dir=target,
    )
    o4_path = target / "O4_preencode.png"
    o5_path = target / "O5_final.png"
    with Image.open(qf_jpeg) as decoded:
        decoded.convert("RGB").save(o5_path, format="PNG")
    return {
        "paths": {"O3": str(o3_path), "O4": str(o4_path), "O5": str(o5_path)},
        "pixel_hashes": {"O3": pixel_sha256(o3_path), "O4": pixel_sha256(o4_path) if o4_path.is_file() else None,
                         "O5": pixel_sha256(o5_path)},
        "quality_finish": qf_report,
    }


def run_fidelity(b_cells: list[dict], settings: dict) -> dict:
    rows = []
    for index, cell in enumerate(b_cells, 1):
        jid = cell["job"]
        print(f"fidelity {index:02d}/12 {cell['image']}/{cell['seed']} {jid}", flush=True)
        result = replay_downstream(
            _load_rgb(CHECKPOINTS / jid / "O2_precamera.png"),
            cell,
            settings["jobs"][jid],
            OUT / "fidelity" / jid,
        )
        comparisons = {}
        for stage, name in (("O3", "O3_stage1.png"), ("O4", "O4_preencode.png"), ("O5", "O5_final.png")):
            actual = Path(result["paths"][stage])
            expected = CHECKPOINTS / jid / name
            exact = actual.is_file() and pixel_sha256(actual) == pixel_sha256(expected)
            comparisons[stage] = {
                "exact": exact,
                "expected": pixel_sha256(expected),
                "actual": pixel_sha256(actual) if actual.is_file() else None,
                "delta": None if exact else (_delta_distribution(actual, expected) if actual.is_file() else {"missing": True}),
            }
        rows.append(
            {
                "job": jid,
                "image": cell["image"],
                "seed": cell["seed"],
                "stages": comparisons,
                "quality_finish_applied": result["quality_finish"].get("applied"),
                "quality_finish_report": result["quality_finish"],
                "pass": all(v["exact"] for v in comparisons.values()),
            }
        )
    record = {
        "pass": all(row["pass"] for row in rows),
        "exact_cells": sum(row["pass"] for row in rows),
        "exact_stage_hashes": sum(v["exact"] for row in rows for v in row["stages"].values()),
        "required_cells": 12,
        "required_stage_hashes": 36,
        "cells": rows,
    }
    _json_write(OUT / "fidelity-results.json", record)
    return record


def _resampled_source(cell: dict, shape: tuple[int, ...]) -> np.ndarray:
    source = ca._load(CHECKPOINTS / cell["job"] / "O0_source.png")
    return ca._resample_to(source, shape)


def _inside_any_box(y: int, x: int, shape: tuple[int, int], boxes: list) -> bool:
    h, w = shape
    xn, yn = x / float(w), y / float(h)
    return any(x0 <= xn <= x1 and y0 <= yn <= y1 for x0, y0, x1, y1 in boxes)


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


def create_edge_support(b_cells: list[dict], roi: dict) -> dict:
    """Pin matched O2/R2 edges before any candidate pixels are created."""
    cells = []
    for cell in b_cells:
        jid = cell["job"]
        o2 = ca._load(CHECKPOINTS / jid / "O2_precamera.png")
        ref = _resampled_source(cell, o2.shape)
        y_o2, y_ref = ca._luma(o2), ca._luma(ref)
        sm_o2 = np.asarray(
            Image.fromarray(np.rint(y_o2 * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.5)),
            dtype=np.float64,
        ) / 255.0
        sm_ref = np.asarray(
            Image.fromarray(np.rint(y_ref * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.5)),
            dtype=np.float64,
        ) / 255.0
        goy, gox = np.gradient(sm_o2)
        gry, grx = np.gradient(sm_ref)
        mo, mr = np.hypot(gox, goy), np.hypot(grx, gry)
        to, tr = float(np.percentile(mo, 92)), float(np.percentile(mr, 92))
        score = np.minimum(mo / max(to, 1e-12), mr / max(tr, 1e-12))
        candidates = []
        h, w = y_o2.shape
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
        for score_value, cy, cx, orientation in candidates:
            if len(chosen) >= 320:
                break
            if any((cy - py) ** 2 + (cx - px) ** 2 <= 36 for py, px in occupied):
                continue
            occupied.append((cy, cx))
            chosen.append(
                {
                    "y": cy,
                    "x": cx,
                    "orientation": orientation,
                    "protected": _inside_any_box(cy, cx, (h, w), roi[cell["image"]].get("protected", [])),
                    "matched_score": score_value,
                }
            )
        cells.append(
            {
                "job": jid,
                "image": cell["image"],
                "seed": cell["seed"],
                "shape": [h, w],
                "o2_edge_p92": to,
                "r2_edge_p92": tr,
                "edges": chosen,
                "edge_count": len(chosen),
                "protected_edge_count": sum(item["protected"] for item in chosen),
            }
        )
    artifact = {
        "derivation_boundary": ["incumbent_B_O2_precamera", "geometry_matched_R2_from_O0"],
        "candidate_inspected": False,
        "center_smoothing_radius": 0.5,
        "edge_percentile_each_input": 92,
        "grid_stride": 3,
        "dedupe_radius_px": 6,
        "profile_half_width_px": HALF_W,
        "cells": cells,
    }
    _json_write(EDGE_ARTIFACT, artifact)
    pin = {
        "artifact": str(EDGE_ARTIFACT.relative_to(ROOT)),
        "sha256": _sha(EDGE_ARTIFACT),
        "recorded_before_candidate_output": True,
    }
    _json_write(EDGE_PIN, pin)
    return artifact


def run_candidates(b_cells: list[dict], settings: dict) -> dict:
    rows = []
    for index, cell in enumerate(b_cells, 1):
        jid = cell["job"]
        print(f"candidate {index:02d}/12 {cell['image']}/{cell['seed']} {jid}", flush=True)
        candidate = build_candidate(
            _load_rgb(CHECKPOINTS / jid / "OR_postresample.png"),
            _load_rgb(CHECKPOINTS / jid / "O2_precamera.png"),
        )
        cell_out = OUT / "candidate" / jid
        cell_out.mkdir(parents=True, exist_ok=True)
        _json_write(cell_out / "candidate-report.json", candidate.report)
        if not candidate.report["fail_closed"]:
            Image.fromarray(candidate.rgb, mode="RGB").save(cell_out / "O2_preserved.png", format="PNG")
        rows.append({"job": jid, "image": cell["image"], "seed": cell["seed"], **candidate.report})
    activations = [row["quantized_changed_pixels"] > 0 and not row["fail_closed"] for row in rows]
    recoveries = [row["recovery"]["eligible_recovery"] for row in rows]
    gate_a = {
        "checkpoint_activated_cells": int(sum(activations)),
        "required": 12,
        "o5_activated_cells": 0,
        "o5_pending": True,
        "pass": False,
    }
    numeric_recoveries = [value for value in recoveries if value is not None]
    gate_b = {
        "per_cell_recovery": recoveries,
        "cohort_mean": float(np.mean(numeric_recoveries)) if len(numeric_recoveries) == 12 else None,
        "minimum": float(np.min(numeric_recoveries)) if len(numeric_recoveries) == 12 else None,
        "mean_floor": 0.15,
        "cell_floor": 0.08,
        "pass": len(numeric_recoveries) == 12
        and float(np.mean(numeric_recoveries)) >= 0.15
        and float(np.min(numeric_recoveries)) >= 0.08,
    }
    record = {"cells": rows, "gate_A": gate_a, "gate_B": gate_b}
    _json_write(OUT / "candidate-results.json", record)
    return record


def _eatr_h1(image: np.ndarray, reference: np.ndarray) -> tuple[float, float]:
    eatrs, h1s = [], []
    for box in ca.POSITIONAL_BANDS.values():
        oi, ri = ca._crop(image, box), ca._crop(reference, box)
        yo, yr = ca._luma(oi), ca._luma(ri)
        eatrs.append(float(np.percentile(ca._edge_mag(yo), 95) / max(np.percentile(ca._edge_mag(yr), 95), 1e-9)))
        bo = ca._gauss(yo, 0.7) - ca._gauss(yo, 1.4)
        br = ca._gauss(yr, 0.7) - ca._gauss(yr, 1.4)
        h1s.append(float(np.sqrt(np.mean(bo * bo)) / max(np.sqrt(np.mean(br * br)), 1e-9)))
    return float(np.mean(eatrs)), float(np.mean(h1s))


def _full_h1_energy_ratio(image: np.ndarray, reference: np.ndarray) -> float:
    yo, yr = ca._luma(image), ca._luma(reference)
    bo = ca._gauss(yo, 0.7) - ca._gauss(yo, 1.4)
    br = ca._gauss(yr, 0.7) - ca._gauss(yr, 1.4)
    return float(np.mean(bo * bo) / max(np.mean(br * br), 1e-9))


def _roi_metrics(image: np.ndarray, reference: np.ndarray, boxes: list) -> dict:
    values = {key: [] for key in ("eatr", "hftr", "luma", "chroma", "rho1", "rho2")}
    for box in boxes:
        oi, ri = ca._crop(image, box), ca._crop(reference, box)
        yo, yr = ca._luma(oi), ca._luma(ri)
        eatr = float(np.percentile(ca._edge_mag(yo), 95) /
                     max(np.percentile(ca._edge_mag(yr), 95), 1e-9))
        bo = ca._gauss(yo, 0.7) - ca._gauss(yo, 1.4)
        br = ca._gauss(yr, 0.7) - ca._gauss(yr, 1.4)
        h1 = float(np.sqrt(np.mean(bo * bo)) /
                   max(np.sqrt(np.mean(br * br)), 1e-9))
        residual = yo - yr
        chroma = oi[..., 1:3] - ri[..., 1:3]
        mask = np.ones_like(residual, dtype=bool)
        values["eatr"].append(eatr)
        values["hftr"].append(h1)
        values["luma"].append(float(np.sqrt(np.mean(residual * residual))) * 255.0)
        values["chroma"].append(float(np.sqrt(np.mean(chroma * chroma))) * 255.0)
        values["rho1"].append(ca._masked_spatial_corr(residual, mask, 0, 1))
        values["rho2"].append(ca._masked_spatial_corr(residual, mask, 0, 2))
    return {key: float(np.mean(value)) for key, value in values.items()}


def _transition_loss(o2: np.ndarray, o5: np.ndarray, reference: np.ndarray) -> dict:
    e2, h2 = _eatr_h1(o2, reference)
    e5, h5 = _eatr_h1(o5, reference)
    de, dh = round(e5 - e2, 4), round(h5 - h2, 4)
    return {"dEATR": de, "dHFTR_H1": dh, "loss": round(max(abs(min(de, 0.0)), abs(min(dh, 0.0))), 4)}


def run_downstream_candidates(b_cells: list[dict], settings: dict, candidate_record: dict, roi: dict) -> dict:
    rows = []
    by_job = {row["job"]: row for row in candidate_record["cells"]}
    for index, cell in enumerate(b_cells, 1):
        jid = cell["job"]
        print(f"downstream {index:02d}/12 {cell['image']}/{cell['seed']} {jid}", flush=True)
        preserved_path = OUT / "candidate" / jid / "O2_preserved.png"
        result = replay_downstream(_load_rgb(preserved_path), cell, settings["jobs"][jid], OUT / "candidate" / jid)
        base_o2 = ca._load(CHECKPOINTS / jid / "O2_precamera.png")
        base_o5 = ca._load(CHECKPOINTS / jid / "O5_final.png")
        cand_o5 = ca._load(Path(result["paths"]["O5"]))
        reference = _resampled_source(cell, cand_o5.shape)
        base_eatr, base_hftr = _eatr_h1(base_o5, reference)
        cand_eatr, cand_hftr = _eatr_h1(cand_o5, reference)
        base_full_h1, cand_full_h1 = _full_h1_energy_ratio(base_o5, reference), _full_h1_energy_ratio(cand_o5, reference)
        texture = roi[cell["image"]].get("texture", [])
        protected = roi[cell["image"]].get("protected", [])
        smooth = roi[cell["image"]].get("smooth", [])
        row = {
            "job": jid,
            "image": cell["image"],
            "seed": cell["seed"],
            "o5_changed_pixels": int(np.count_nonzero(np.any(_load_rgb(Path(result["paths"]["O5"])) != _load_rgb(CHECKPOINTS / jid / "O5_final.png"), axis=2))),
            "loss_B": _transition_loss(base_o2, base_o5, reference),
            "loss_C": _transition_loss(base_o2, cand_o5, reference),
            "eatr_B": base_eatr,
            "eatr_C": cand_eatr,
            "hftr_B": base_hftr,
            "hftr_C": cand_hftr,
            "full_h1_energy_B": base_full_h1,
            "full_h1_energy_C": cand_full_h1,
            "texture_B": _roi_metrics(base_o5, reference, texture),
            "texture_C": _roi_metrics(cand_o5, reference, texture),
            "protected_B": _roi_metrics(base_o5, reference, protected),
            "protected_C": _roi_metrics(cand_o5, reference, protected),
            "smooth_B": _roi_metrics(base_o5, reference, smooth),
            "smooth_C": _roi_metrics(cand_o5, reference, smooth),
            "qf_applied": result["quality_finish"].get("applied"),
        }
        by_job[jid]["o5_changed_pixels"] = row["o5_changed_pixels"]
        rows.append(row)

    candidate_record["gate_A"].update(
        {"o5_activated_cells": sum(row["o5_changed_pixels"] > 0 for row in rows), "o5_pending": False}
    )
    candidate_record["gate_A"]["pass"] = (
        candidate_record["gate_A"]["checkpoint_activated_cells"] == 12
        and candidate_record["gate_A"]["o5_activated_cells"] == 12
    )
    mean_c = float(np.mean([row["loss_C"]["loss"] for row in rows]))
    mean_b = float(np.mean([row["loss_B"]["loss"] for row in rows]))
    hard_c = float(np.mean([row["loss_C"]["loss"] for row in rows if row["image"] in HARD_IMAGES]))
    reduction = 1.0 - mean_c / max(mean_b, 1e-9)
    image_directions = {}
    for image in SIX_IMAGES:
        subset = [row for row in rows if row["image"] == image]
        image_directions[image] = {
            "B": float(np.mean([row["full_h1_energy_B"] for row in subset])),
            "C": float(np.mean([row["full_h1_energy_C"] for row in subset])),
        }
    gains_hftr = [(row["texture_C"]["hftr"] - row["texture_B"]["hftr"]) / max(row["texture_B"]["hftr"], 1e-9) for row in rows]
    gains_eatr = [row["eatr_C"] - row["eatr_B"] for row in rows]
    protected_ratios = [row["protected_C"]["eatr"] / max(row["protected_B"]["eatr"], 1e-9) for row in rows]
    luma_rises = [(row["smooth_C"]["luma"] - row["smooth_B"]["luma"]) / max(row["smooth_B"]["luma"], 1e-9) for row in rows]
    chroma_rises = [(row["smooth_C"]["chroma"] - row["smooth_B"]["chroma"]) / max(row["smooth_B"]["chroma"], 1e-9) for row in rows]
    rho_rises = [max(row["smooth_C"]["rho1"] - row["smooth_B"]["rho1"], row["smooth_C"]["rho2"] - row["smooth_B"]["rho2"]) for row in rows]
    gates = {
        "C": {"mean_L_B": mean_b, "mean_L_C": mean_c, "reduction": reduction, "overall_ceiling": 0.07366275,
              "hard_mean_L_C": hard_c, "hard_ceiling": 0.07951875,
              "pass": reduction >= 0.25 and mean_c <= 0.07366275 and hard_c <= 0.07951875},
        "D": {"mean_full_h1_energy_ratio": float(np.mean([r["full_h1_energy_C"] for r in rows])), "floor_model_estimate": 0.420,
              "median_texture_hftr_gain": float(np.median(gains_hftr)), "texture_gain_floor": 0.08,
              "image_means": image_directions, "image_improve_count": sum(v["C"] > v["B"] for v in image_directions.values()),
              "pass": float(np.mean([r["full_h1_energy_C"] for r in rows])) >= 0.420 and float(np.median(gains_hftr)) >= 0.08
                      and sum(v["C"] > v["B"] for v in image_directions.values()) >= 5},
        "E": {"per_cell_eatr_gains": gains_eatr, "median_eatr_gain": float(np.median(gains_eatr)), "floor": 0.04,
              "pass": float(np.median(gains_eatr)) >= 0.04},
        "F": {"protected_eatr_ratios": protected_ratios, "worst_protected_ratio": min(protected_ratios), "floor": 0.98,
              "smooth_luma_rises": luma_rises, "worst_luma_rise": max(luma_rises), "smooth_chroma_rises": chroma_rises,
              "worst_chroma_rise": max(chroma_rises), "rms_rise_ceiling": 0.05, "rho_rises": rho_rises,
              "worst_rho_rise": max(rho_rises), "rho_rise_ceiling": 0.03,
              "pass": min(protected_ratios) >= 0.98 and max(luma_rises) <= 0.05 and max(chroma_rises) <= 0.05 and max(rho_rises) <= 0.03},
    }
    record = {"cells": rows, "gates": gates}
    _json_write(OUT / "downstream-results.json", record)
    _json_write(OUT / "candidate-results.json", candidate_record)
    return record


def _fixed_profile(luma: np.ndarray, edge: dict) -> dict | None:
    cy, cx = int(edge["y"]), int(edge["x"])
    horizontal = edge["orientation"] == "h"
    raw = (luma[cy - HALF_W : cy + HALF_W + 1, cx] if horizontal
           else luma[cy, cx - HALF_W : cx + HALF_W + 1]).astype(np.float64)
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
    oot = float(np.mean(np.maximum(normalized - 1.0, 0.0)[outside]) + np.mean(np.maximum(-normalized, 0.0)[outside]))
    crossings = 0
    for level in (0.1, 0.9):
        crossings += int(np.count_nonzero(np.diff(np.sign(normalized - level))))
    return {"width": width, "overshoot": overshoot, "oot": oot, "crossings": crossings}


def evaluate_edges(b_cells: list[dict]) -> dict:
    support = json.loads(EDGE_ARTIFACT.read_text())
    by_job = {row["job"]: row for row in support["cells"]}
    pairs = []
    for cell in b_cells:
        jid = cell["job"]
        baseline = ca._load(CHECKPOINTS / jid / "O5_final.png")
        candidate = ca._load(OUT / "candidate" / jid / "O5_final.png")
        reference = _resampled_source(cell, baseline.shape)
        triplets = []
        for edge in by_job[jid]["edges"]:
            b = _fixed_profile(ca._luma(baseline), edge)
            c = _fixed_profile(ca._luma(candidate), edge)
            r = _fixed_profile(ca._luma(reference), edge)
            if b and c and r:
                triplets.append((edge, b, c, r))
        protected = [row for row in triplets if row[0]["protected"]]
        width_worsen = [abs(c["width"] - r["width"]) - abs(b["width"] - r["width"]) for _, b, c, r in triplets]
        overshoot_delta = [c["overshoot"] - b["overshoot"] for _, b, c, _ in triplets]
        oot_rel = [(c["oot"] - b["oot"]) / max(b["oot"], 1e-9) for _, b, c, _ in triplets]
        second_peaks = sum(c["crossings"] > max(2, b["crossings"]) for _, b, c, _ in protected)
        pairs.append({
            "job": jid, "image": cell["image"], "seed": cell["seed"], "valid_edges": len(triplets),
            "protected_edges": len(protected), "median_width_gap_worsening_px": float(np.median(width_worsen)) if width_worsen else None,
            "median_overshoot_delta": float(np.median(overshoot_delta)) if overshoot_delta else None,
            "oot_relative_change": float(np.median(oot_rel)) if oot_rel else None, "protected_candidate_created_second_peaks": second_peaks,
        })
    eligible = all(row["valid_edges"] >= 100 and row["protected_edges"] >= 20 for row in pairs)
    width_values = [row["median_width_gap_worsening_px"] for row in pairs if row["median_width_gap_worsening_px"] is not None]
    over_values = [row["median_overshoot_delta"] for row in pairs if row["median_overshoot_delta"] is not None]
    oot_values = [row["oot_relative_change"] for row in pairs if row["oot_relative_change"] is not None]
    gate = {
        "pairs": pairs,
        "support_minimum_pass": eligible,
        "cohort_median_width_worsening": float(np.median(width_values)) if width_values else None,
        "worst_pair_width_worsening": max(width_values) if width_values else None,
        "cohort_median_overshoot_delta": float(np.median(over_values)) if over_values else None,
        "worst_pair_overshoot_delta": max(over_values) if over_values else None,
        "cohort_median_oot_relative_change": float(np.median(oot_values)) if oot_values else None,
        "worst_pair_oot_relative_change": max(oot_values) if oot_values else None,
        "protected_candidate_created_second_peaks": sum(row["protected_candidate_created_second_peaks"] for row in pairs),
    }
    gate["pass"] = bool(
        eligible and gate["cohort_median_width_worsening"] <= 0.25 and gate["worst_pair_width_worsening"] <= 0.50
        and gate["cohort_median_overshoot_delta"] <= 0.02 and gate["worst_pair_overshoot_delta"] <= 0.03
        and gate["cohort_median_oot_relative_change"] <= 0.02 and gate["worst_pair_oot_relative_change"] <= 0.05
        and gate["protected_candidate_created_second_peaks"] == 0
    )
    _json_write(OUT / "edge-results.json", gate)
    return gate


def _artifact_index() -> dict:
    files = []
    for path in sorted(OUT.rglob("*")):
        if path.is_file() and path.name != "artifact-index.json":
            row = {"path": str(path.relative_to(ROOT)), "sha256": _sha(path), "bytes": path.stat().st_size}
            if path.suffix.lower() in {".png", ".jpg", ".jpeg"}:
                row["pixel_sha256"] = pixel_sha256(path)
            files.append(row)
    if REPORT_PATH.is_file():
        files.append({"path": REPORT_PATH.name, "sha256": _sha(REPORT_PATH), "bytes": REPORT_PATH.stat().st_size})
    index = {"self_exclusion": "artifact-index.json cannot hash itself", "files": files}
    _json_write(OUT / "artifact-index.json", index)
    return index


def write_report(status: str, pin_record: list[dict], fidelity: dict | None, candidate: dict | None = None,
                 downstream: dict | None = None, edge: dict | None = None, reason: str | None = None) -> None:
    lines = [
        "# C8 4D-1b Replay Report",
        "",
        f"**Decision: {status}.**",
        "",
        "This is an archived-checkpoint replay only. No live cell, detector grade, vendor call, deployment, Supabase action, or RunPod action was performed.",
        "",
        "## Evidence and runtime",
        "",
        f"- Input/provenance checks: {sum(row.get('pass', False) for row in pin_record)}/{len(pin_record)} passed.",
        f"- Python: `{platform.python_version()}`; Pillow: `{Image.__version__}`; NumPy: `{np.__version__}`.",
    ]
    if reason:
        lines.append(f"- Hard-stop reason: {reason}")
    lines.extend(["", "## Fidelity proof", ""])
    if fidelity is None:
        lines.append("Not run because prerequisite verification stopped the harness.")
    else:
        stage_counts = {
            stage: sum(row["stages"][stage]["exact"] for row in fidelity["cells"])
            for stage in ("O3", "O4", "O5")
        }
        lines.extend([
            f"- Exact cells: **{fidelity['exact_cells']}/12**.",
            f"- Exact decoded stage hashes: **{fidelity['exact_stage_hashes']}/36** (O3/O4/O5).",
            f"- Stage split: O3 **{stage_counts['O3']}/12**, O4 **{stage_counts['O4']}/12**, O5 **{stage_counts['O5']}/12** exact.",
            f"- Binary fidelity gate: **{'PASS' if fidelity['pass'] else 'FAIL'}**.",
            "- Any mismatch has a per-stage signed-delta distribution in `round-4d-1b-replay/fidelity-results.json`; no tolerance was substituted.",
        ])
        if not fidelity["pass"]:
            for stage in ("O4", "O5"):
                deltas = [row["stages"][stage]["delta"] for row in fidelity["cells"]
                          if row["stages"][stage]["delta"] and row["stages"][stage]["delta"].get("shape_match")]
                lines.append(
                    f"- {stage} mismatch envelope: {sum(item['changed_samples'] for item in deltas):,} changed channel samples total; "
                    f"max `{max(item['max_abs_lsb'] for item in deltas)}` LSB; worst RMS "
                    f"`{max(item['rms_lsb'] for item in deltas):.8f}` LSB."
                )
    lines.extend(["", "## Candidate and Gates A–G", ""])
    if candidate is None:
        lines.append("Not evaluated. Fidelity or an earlier prerequisite failed, so no candidate output was produced.")
    else:
        ga, gb = candidate["gate_A"], candidate["gate_B"]
        lines.extend([
            f"- Gate A activation: **{'PASS' if ga['pass'] else 'FAIL'}** — checkpoint {ga['checkpoint_activated_cells']}/12; O5 {ga['o5_activated_cells']}/12.",
            f"- Gate B dose: **{'PASS' if gb['pass'] else 'FAIL'}** — mean `{gb['cohort_mean']}`, minimum `{gb['minimum']}`; floors 0.15 / 0.08.",
            "- Gate B uses `(ΣE_cand−ΣE_O2)/(ΣE_OR−ΣE_O2)` over valid eligible 15×15/stride-3 windows. Per-cell whole-frame recovery, eligible lost-energy mass, and perfect-correlation ceiling are in `candidate-results.json`.",
        ])
        if downstream is None:
            lines.append("- Gates C–G: **NOT EVALUATED** because Gate A or B failed; replay stopped before downstream candidate execution.")
        else:
            for name in ("C", "D", "E", "F"):
                lines.append(f"- Gate {name}: **{'PASS' if downstream['gates'][name]['pass'] else 'FAIL'}**.")
            lines.append(f"- Gate G: **{'PASS' if edge and edge['pass'] else 'FAIL'}**.")
            lines.append("- Gate D's 0.420 delivered H1/source threshold is a **model estimate**, as pre-registered.")
    lines.extend([
        "",
        "## Artifact record",
        "",
        "`round-4d-1b-replay/artifact-index.json` records byte SHA-256 for every produced replay artifact (and decoded-pixel hashes for images), excluding only itself.",
        (
            "The edge-support artifact was not generated: fidelity failed before the candidate boundary, so candidate preparation was prohibited."
            if candidate is None
            else "The edge-support pin was written before candidate generation."
        ),
        "",
        "## Signed declaration",
        "",
        "I declare that this build and report used only the pinned local archive; honored the fidelity-first and fail-closed stop rules; did not alter a frozen input; and performed none of the forbidden external or live actions.",
        "",
        "Signed: **C88 replay builder (Codex)**  ",
        "Date: **2026-08-27 (Australia/Sydney)**",
        "",
    ])
    REPORT_PATH.write_text("\n".join(lines))


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    pin_record: list[dict] = []
    fidelity = candidate = downstream = edge_result = None
    try:
        manifest, settings, b_cells, pin_record = verify_inputs()
        _json_write(OUT / "input-verification.json", {"pass": True, "checks": pin_record})
    except Exception as exc:
        _json_write(OUT / "input-verification.json", {"pass": False, "error": f"{type(exc).__name__}: {exc}", "checks": pin_record})
        write_report("HARD STOP — INPUT VERIFICATION FAILED", pin_record, None, reason=str(exc))
        _artifact_index()
        return 2

    fidelity = run_fidelity(b_cells, settings)
    if not fidelity["pass"]:
        write_report("HARD STOP — DOWNSTREAM FIDELITY NOT PROVEN", pin_record, fidelity,
                     reason="unchanged O2 did not reproduce all 36 archived O3/O4/O5 decoded-pixel hashes")
        _artifact_index()
        return 3

    roi = json.loads(ROI_PATH.read_text())["images"]
    create_edge_support(b_cells, roi)
    candidate = run_candidates(b_cells, settings)
    if not candidate["gate_A"]["checkpoint_activated_cells"] == 12 or not candidate["gate_B"]["pass"]:
        candidate["gate_A"]["pass"] = False
        _json_write(OUT / "candidate-results.json", candidate)
        write_report("HARD STOP — CANDIDATE CHECKPOINT GATE FAILED", pin_record, fidelity, candidate,
                     reason="Gate A checkpoint activation or Gate B effective dose failed")
        _artifact_index()
        return 4

    downstream = run_downstream_candidates(b_cells, settings, candidate, roi)
    edge_result = evaluate_edges(b_cells)
    all_pass = candidate["gate_A"]["pass"] and candidate["gate_B"]["pass"] and all(
        downstream["gates"][name]["pass"] for name in ("C", "D", "E", "F")
    ) and edge_result["pass"]
    status = "REPLAY PASSED — ELIGIBLE FOR MASTER-ENGINEER VERIFICATION" if all_pass else "HARD STOP — ONE OR MORE REPLAY GATES FAILED"
    write_report(status, pin_record, fidelity, candidate, downstream, edge_result,
                 None if all_pass else "At least one pre-registered Gate A–G failed")
    _artifact_index()
    return 0 if all_pass else 5


if __name__ == "__main__":
    raise SystemExit(main())
