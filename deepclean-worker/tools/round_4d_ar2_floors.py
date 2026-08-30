#!/usr/bin/env python3
"""Offline-only 4D-AR2 metric-domain reanalysis.

Implements C8_MASTER_PROMPT_4D_AR2_METRIC_DOMAIN_REANALYSIS.md sections 3-4.
The harness reads the frozen AR1 record and existing A0-A6 deliveries. It does
not render an arm, run a panel, call a detector/vendor, grade, deploy, or use a
network client. The only default-run writes are the frozen AR2 floor artifacts.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np
import PIL
from PIL import Image


TOOLS_DIR = Path(__file__).resolve().parent
WORKER_DIR = TOOLS_DIR.parent
ROOT = WORKER_DIR.parent
AR1 = ROOT / "round-4d-ar1"
AR1_INDEX = AR1 / "artifact-index.json"
AR1_M2 = AR1 / "m2-results.json"
CHECKPOINTS = ROOT / "round-4d-1a" / "checkpoints"
MANIFEST_PATH = ROOT / "round-4d-1a" / "expected-manifest.json"
ROI_PATH = ROOT / "round-4d-cam-1" / "roi-manifest.json"
FREEZE_PATH = ROOT / "C8_MASTER_PROMPT_4D_AR2_METRIC_DOMAIN_REANALYSIS.md"

OUT = ROOT / "round-4d-ar2"
WORK_OUT = ROOT / "round-4d-ar2.in-progress"
REPORT_PATH = ROOT / "C8_4D_AR2_SHORTLIST.md"
WORK_REPORT_PATH = ROOT / "C8_4D_AR2_SHORTLIST.md.in-progress"

PYTHON_VERSION = "3.9.6"
NUMPY_VERSION = "2.0.2"
PILLOW_VERSION = "11.3.0"
AR1_INDEX_EXPECTED_SHA256 = "01a51382bea68634b957479d8b98179ae5f09ee5a65da2af89ddd21afd9d4c20"
AR1_INDEX_ENTRY_COUNT = 349

FROZEN_FILE_PINS = {
    "C8_MASTER_PROMPT_4D_AR2_METRIC_DOMAIN_REANALYSIS.md":
        "b615303e31aff2676c01097ecc686d7e9efeef80b4d0819297ec0c5d9cfe12c2",
    "deepclean-worker/tools/round_4d_ar1_metrics.py":
        "68da60b71bade404a11f157662648a53b0737c9e04e6ac4edb6521432aac5755",
    "deepclean-worker/tools/checkpoint_attribution.py":
        "335d8967560a60f32c5732fde63258d9919520fd7006d8d74c1ffa46eef53a44",
    "deepclean-worker/tools/edge_spread_audit.py":
        "3175409ef6c815df25ffb9027c7184667d7c1c04cf2d86d99128480f327f3cc4",
    "round-4d-1a/expected-manifest.json":
        "6d1c730c629fda80b04b742bc75423f2f4710802a6cabc330910aaff7739c76a",
    "round-4d-cam-1/roi-manifest.json":
        "5b0d73779e2855e5deafff5534d01aca647342e2b21370bf8664f9571ad3d329",
}

ARMS = ("A0", "A1", "A2", "A3", "A4", "A5", "A6")
CHALLENGERS = ("A1", "A2", "A3", "A4", "A5", "A6")
SIX_IMAGES = ("IMG-5", "IMG-6", "IMG-7", "IMG-8", "IMG-9", "IMG-11")
SEEDS = ("lab-ctla1", "lab-ctla2")

PROTECTED_EATR_FLOOR = 0.98
LUMA_RISE_CEILING = 0.05
CHROMA_RISE_CEILING = 0.05
H3_STEP_MIN = 0.08
H3_WIDTH_MIN = 2.0
H3_WIDTH_MAX = 12.0
H3_PEAK_AMPLITUDE_MIN = 0.05
H3_ENDPOINT_SEPARATION_MIN = 2.0
PROFILE_HALF_WIDTH = 21
PROFILE_OUTER_START = 8


class FreezeViolation(RuntimeError):
    """A frozen input, metric, or output contract did not hold."""


@dataclass(frozen=True)
class FrozenRecipes:
    load: Callable[[Path], np.ndarray]
    luma: Callable[[np.ndarray], np.ndarray]
    resample_to: Callable[[np.ndarray, Tuple[int, ...]], np.ndarray]
    edge_support: Callable[[np.ndarray, np.ndarray, List[list]], List[dict]]
    isotonic: Callable[[np.ndarray], np.ndarray]


@dataclass(frozen=True)
class InputBundle:
    cells: List[dict]
    roi: dict
    m2: dict
    checks: List[dict]
    ar1_index_sha256: str


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _record_check(checks: List[dict], name: str, actual: Any, expected: Any) -> None:
    passed = actual == expected
    checks.append({"check": name, "actual": actual, "expected": expected, "pass": passed})
    if not passed:
        raise FreezeViolation("{}: expected {!r}, got {!r}".format(name, expected, actual))


def _json_ready(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_ready(item) for item in value]
    if isinstance(value, (set, frozenset)):
        return [_json_ready(item) for item in sorted(value)]
    if isinstance(value, np.ndarray):
        return _json_ready(value.tolist())
    if isinstance(value, np.generic):
        return _json_ready(value.item())
    if isinstance(value, float) and not math.isfinite(value):
        raise FreezeViolation("non-finite metric: {!r}".format(value))
    return value


def _write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(_json_ready(value), indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def _walk_numbers(value: Any, path: str = "root") -> Iterable[Tuple[str, float]]:
    if isinstance(value, dict):
        for key, item in value.items():
            yield from _walk_numbers(item, path + "." + str(key))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from _walk_numbers(item, "{}[{}]".format(path, index))
    elif isinstance(value, (float, np.floating)):
        yield path, float(value)


def _require_finite(value: Any) -> None:
    for path, number in _walk_numbers(value):
        if not math.isfinite(number):
            raise FreezeViolation("non-finite metric at {}: {!r}".format(path, number))


def verify_environment() -> dict:
    temp_root = os.environ.get("TMPDIR")
    if not temp_root:
        raise FreezeViolation("TMPDIR is missing; cannot resolve frozen verify3 environment")
    expected_prefix = (Path(temp_root) / "verify3").resolve()
    actual_prefix = Path(sys.prefix).resolve()
    checks = {
        "environment_prefix": {
            "actual": str(actual_prefix),
            "expected": str(expected_prefix),
            "pass": actual_prefix == expected_prefix,
        },
        "python": {
            "actual": platform.python_version(),
            "expected": PYTHON_VERSION,
            "pass": platform.python_version() == PYTHON_VERSION,
        },
        "numpy": {
            "actual": np.__version__,
            "expected": NUMPY_VERSION,
            "pass": np.__version__ == NUMPY_VERSION,
        },
        "pillow": {
            "actual": PIL.__version__,
            "expected": PILLOW_VERSION,
            "pass": PIL.__version__ == PILLOW_VERSION,
        },
    }
    failed = [name for name, row in checks.items() if not row["pass"]]
    if failed:
        raise FreezeViolation("frozen environment mismatch: " + ", ".join(failed))
    return {"pass": True, "checks": checks}


def _safe_index_path(relative: Any) -> Optional[Path]:
    if not isinstance(relative, str):
        return None
    candidate = Path(relative)
    if candidate.is_absolute() or ".." in candidate.parts:
        return None
    return candidate


def _verify_ar1_index(checks: List[dict]) -> Tuple[dict, str]:
    index_sha = _sha256(AR1_INDEX) if AR1_INDEX.is_file() else None
    _record_check(checks, "AR1 artifact-index pin", index_sha, AR1_INDEX_EXPECTED_SHA256)
    index = json.loads(AR1_INDEX.read_text(encoding="utf-8"))
    rows = index.get("files")
    _record_check(checks, "AR1 artifact-index entry count", len(rows) if isinstance(rows, list) else None,
                  AR1_INDEX_ENTRY_COUNT)
    seen = set()
    for row in rows:
        relative = _safe_index_path(row.get("path") if isinstance(row, dict) else None)
        if relative is None:
            raise FreezeViolation("unsafe or malformed AR1 artifact-index path")
        logical = relative.as_posix()
        if logical in seen:
            raise FreezeViolation("duplicate AR1 artifact-index path: " + logical)
        seen.add(logical)
        path = ROOT / relative
        actual_bytes = path.stat().st_size if path.is_file() else None
        actual_sha = _sha256(path) if path.is_file() else None
        _record_check(checks, logical + " byte count", actual_bytes, row.get("bytes"))
        _record_check(checks, logical + " sha256", actual_sha, row.get("sha256"))
    _record_check(checks, "AR1 artifact-index self exclusion", "round-4d-ar1/artifact-index.json" in seen, False)
    return index, str(index_sha)


def _validate_m2(m2: dict, cells: List[dict], checks: List[dict]) -> None:
    arm_cells = m2.get("arm_cells")
    _record_check(checks, "M2 arm set", sorted(arm_cells) if isinstance(arm_cells, dict) else None,
                  sorted(ARMS))
    expected_jobs = {cell["job"] for cell in cells}
    for arm in ARMS:
        rows = arm_cells.get(arm) if isinstance(arm_cells, dict) else None
        _record_check(checks, arm + " M2 cell count", len(rows) if isinstance(rows, list) else None, 12)
        jobs = {row.get("job") for row in rows} if isinstance(rows, list) else set()
        _record_check(checks, arm + " M2 job set", sorted(jobs), sorted(expected_jobs))
        for row in rows:
            for key in ("smooth_luma_rise", "smooth_chroma_rise", "smooth_rho1_rise",
                        "smooth_rho2_rise", "protected_eatr_ratio_min", "upstream_identity_pass"):
                if key not in row.get("vs_A0", {}):
                    raise FreezeViolation("{} {} missing M2 metric {}".format(arm, row.get("job"), key))
    _require_finite(m2)


def verify_inputs() -> InputBundle:
    checks: List[dict] = []
    _, index_sha = _verify_ar1_index(checks)
    for relative, expected in FROZEN_FILE_PINS.items():
        path = ROOT / relative
        actual = _sha256(path) if path.is_file() else None
        _record_check(checks, "frozen pin " + relative, actual, expected)

    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    roi = json.loads(ROI_PATH.read_text(encoding="utf-8"))
    m2 = json.loads(AR1_M2.read_text(encoding="utf-8"))
    b_cells = [cell for cell in manifest.get("cells", []) if cell.get("arm") == "B"]
    cells = sorted(b_cells, key=lambda cell: (cell["seed"], int(cell["image"].split("-")[1])))
    _record_check(checks, "B-cell count", len(cells), 12)
    _record_check(
        checks,
        "B-cell cohort",
        sorted((cell["image"], cell["seed"]) for cell in cells),
        sorted((image, seed) for seed in SEEDS for image in SIX_IMAGES),
    )
    images = roi.get("images")
    if not isinstance(images, dict):
        raise FreezeViolation("ROI manifest images block is missing")
    for image in SIX_IMAGES:
        boxes = images.get(image, {}).get("protected")
        if not isinstance(boxes, list) or not boxes:
            raise FreezeViolation("missing protected ROI boxes for " + image)

    expected_o5 = {
        "round-4d-ar1/arms/{}/{}/O5_final.jpg".format(arm, cell["job"])
        for arm in ARMS for cell in cells
    }
    index = json.loads(AR1_INDEX.read_text(encoding="utf-8"))
    indexed_paths = {row["path"] for row in index["files"]}
    _record_check(checks, "84 delivered O5 files indexed", expected_o5.issubset(indexed_paths), True)
    input_verification = json.loads((AR1 / "input-verification.json").read_text(encoding="utf-8"))
    input_checks = input_verification.get("checks")
    _record_check(checks, "AR1 input verification pass", input_verification.get("pass"), True)
    _record_check(checks, "AR1 input verification check count",
                  len(input_checks) if isinstance(input_checks, list) else None, 291)
    _record_check(checks, "AR1 all input verification checks pass",
                  all(row.get("pass") for row in input_checks) if isinstance(input_checks, list) else False, True)
    _validate_m2(m2, cells, checks)
    return InputBundle(cells=cells, roi=images, m2=m2, checks=checks,
                       ar1_index_sha256=index_sha)


def load_frozen_recipes() -> FrozenRecipes:
    if str(TOOLS_DIR) not in sys.path:
        sys.path.insert(0, str(TOOLS_DIR))
    if str(WORKER_DIR) not in sys.path:
        sys.path.insert(0, str(WORKER_DIR))
    import checkpoint_attribution as ca  # noqa: E402
    import round_4d_ar1_metrics as ar1_metrics  # noqa: E402
    from edge_spread_audit import isotonic  # noqa: E402

    return FrozenRecipes(
        load=ca._load,
        luma=ca._luma,
        resample_to=ca._resample_to,
        edge_support=ar1_metrics._edge_support,
        isotonic=isotonic,
    )


def _transition_endpoints(mono: np.ndarray, xs: np.ndarray) -> Tuple[float, float]:
    x10 = float(np.interp(0.1, mono, xs))
    x90 = float(np.interp(0.9, mono, xs))
    return min(x10, x90), max(x10, x90)


def _is_local_extremum(values: np.ndarray, index: int) -> bool:
    value = values[index]
    left = values[index - 1]
    right = values[index + 1]
    maximum = value >= left and value >= right and (value > left or value > right)
    minimum = value <= left and value <= right and (value < left or value < right)
    return bool(maximum or minimum)


def analyze_raw_profile(raw: np.ndarray, isotonic_fn: Callable[[np.ndarray], np.ndarray]) -> dict:
    """Apply frozen normalization, then the AR2 H3 stable-domain/peak rule."""
    values = np.asarray(raw, dtype=np.float64)
    expected_length = 2 * PROFILE_HALF_WIDTH + 1
    if values.ndim != 1 or len(values) != expected_length:
        raise FreezeViolation("profile must contain exactly {} samples".format(expected_length))
    if not np.isfinite(values).all():
        raise FreezeViolation("non-finite raw edge profile")
    xs = np.arange(-PROFILE_HALF_WIDTH, PROFILE_HALF_WIDTH + 1, dtype=np.float64)
    outer = np.abs(xs) >= PROFILE_OUTER_START
    lo = float(np.percentile(values[outer], 5))
    hi = float(np.percentile(values[outer], 95))
    step = hi - lo
    reasons: List[str] = []
    if step < H3_STEP_MIN:
        reasons.append("plateau_step_below_0.08")
    if step <= 1e-12:
        return {
            "step": step,
            "width_10_90": None,
            "overshoot": None,
            "oot": None,
            "frozen_esf_profile_valid": False,
            "eligible": False,
            "exclusion_reasons": reasons,
            "transition": None,
            "plateaus": None,
            "second_peaks": [],
        }

    normalized = (values - lo) / step
    if normalized[PROFILE_HALF_WIDTH - 3] > normalized[PROFILE_HALF_WIDTH + 3]:
        normalized = normalized[::-1]
    mono = np.asarray(isotonic_fn(normalized), dtype=np.float64)
    if mono.shape != normalized.shape or not np.isfinite(mono).all():
        raise FreezeViolation("frozen isotonic recipe returned an invalid profile")
    x10, x90 = _transition_endpoints(mono, xs)
    width = x90 - x10
    if width < H3_WIDTH_MIN or width > H3_WIDTH_MAX:
        reasons.append("width_outside_[2,12]")

    left_plateau = float(np.median(normalized[xs <= -PROFILE_OUTER_START]))
    right_plateau = float(np.median(normalized[xs >= PROFILE_OUTER_START]))
    peaks = []
    for index in range(1, len(normalized) - 1):
        x = float(xs[index])
        side = None
        plateau = None
        endpoint_distance = None
        if x <= x10 - H3_ENDPOINT_SEPARATION_MIN:
            side = "left"
            plateau = left_plateau
            endpoint_distance = x10 - x
        elif x >= x90 + H3_ENDPOINT_SEPARATION_MIN:
            side = "right"
            plateau = right_plateau
            endpoint_distance = x - x90
        if side is None or not _is_local_extremum(normalized, index):
            continue
        deviation = abs(float(normalized[index]) - float(plateau))
        if deviation > H3_PEAK_AMPLITUDE_MIN:
            peaks.append({
                "x": x,
                "side": side,
                "normalized_value": float(normalized[index]),
                "adjacent_plateau": float(plateau),
                "deviation_step_fraction": deviation,
                "endpoint_distance_px": float(endpoint_distance),
            })

    overshoot = max(0.0, float(normalized.max() - 1.0), float(-normalized.min()))
    outside = np.abs(xs) > 0.75 * width
    oot = 0.0
    if outside.any():
        oot = float(
            np.mean(np.maximum(normalized - 1.0, 0.0)[outside])
            + np.mean(np.maximum(-normalized, 0.0)[outside])
        )
    return {
        "step": step,
        "width_10_90": width,
        "overshoot": overshoot,
        "oot": oot,
        "frozen_esf_profile_valid": step >= 0.04 and 0.2 <= width <= 2 * PROFILE_HALF_WIDTH - 2,
        "eligible": not reasons,
        "exclusion_reasons": reasons,
        "transition": {"x10": x10, "x90": x90},
        "plateaus": {"left": left_plateau, "right": right_plateau},
        "second_peaks": peaks,
    }


def extract_profile(luma: np.ndarray, edge: dict,
                    isotonic_fn: Callable[[np.ndarray], np.ndarray]) -> dict:
    cy, cx = int(edge["y"]), int(edge["x"])
    horizontal = edge["orientation"] == "h"
    if horizontal:
        raw = luma[cy - PROFILE_HALF_WIDTH:cy + PROFILE_HALF_WIDTH + 1, cx]
    else:
        raw = luma[cy, cx - PROFILE_HALF_WIDTH:cx + PROFILE_HALF_WIDTH + 1]
    return analyze_raw_profile(raw, isotonic_fn)


def _profile_exclusion_reasons(a0_profile: dict, arm_profile: dict) -> List[str]:
    reasons = []
    for prefix, profile in (("a0", a0_profile), ("arm", arm_profile)):
        for reason in profile["exclusion_reasons"]:
            reasons.append(prefix + "_" + reason)
    return reasons


def _median_or_none(values: Sequence[float]) -> Optional[float]:
    return float(np.median(values)) if values else None


def evaluate_h3_cell(
    cell: dict,
    arm: str,
    arm_luma: np.ndarray,
    a0_luma: np.ndarray,
    source_luma: np.ndarray,
    edges: List[dict],
    isotonic_fn: Callable[[np.ndarray], np.ndarray],
) -> dict:
    h3_exclusions = []
    esf_reporting_exclusions = []
    peak_edges = []
    overshoot_deltas: List[float] = []
    width_worsenings: List[float] = []
    oot_deltas: List[float] = []
    eligible_count = 0
    width_reportable_count = 0

    for edge in edges:
        if not edge.get("protected"):
            continue
        a0_profile = extract_profile(a0_luma, edge, isotonic_fn)
        arm_profile = extract_profile(arm_luma, edge, isotonic_fn)
        reasons = _profile_exclusion_reasons(a0_profile, arm_profile)
        base = {
            "y": int(edge["y"]),
            "x": int(edge["x"]),
            "orientation": edge["orientation"],
            "a0_step": a0_profile["step"],
            "a0_width_10_90": a0_profile["width_10_90"],
            "arm_step": arm_profile["step"],
            "arm_width_10_90": arm_profile["width_10_90"],
        }
        if reasons:
            h3_exclusions.append({**base, "reasons": reasons})
            continue

        eligible_count += 1
        if arm_profile["second_peaks"]:
            peak_edges.append({**base, "second_peaks": arm_profile["second_peaks"]})

        # H3 eligibility alone controls overshoot/OOT reporting. Width-gap
        # reporting additionally needs a source profile valid under the frozen
        # ESF recipe because the gap is defined relative to that source width.
        overshoot_deltas.append(float(arm_profile["overshoot"] - a0_profile["overshoot"]))
        oot_deltas.append(float(arm_profile["oot"] - a0_profile["oot"]))
        source_profile = extract_profile(source_luma, edge, isotonic_fn)
        if not source_profile["frozen_esf_profile_valid"]:
            esf_reporting_exclusions.append({
                **base,
                "reasons": ["source_profile_unusable_for_width_gap_reporting"],
                "h3_eligible": True,
            })
            continue
        width_reportable_count += 1
        width_worsenings.append(float(
            abs(arm_profile["width_10_90"] - source_profile["width_10_90"])
            - abs(a0_profile["width_10_90"] - source_profile["width_10_90"])
        ))

    second_peak_count = sum(len(row["second_peaks"]) for row in peak_edges)
    return {
        "job": cell["job"],
        "image": cell["image"],
        "seed": cell["seed"],
        "protected_edge_count": sum(bool(edge.get("protected")) for edge in edges),
        "eligible_edge_count": eligible_count,
        "overshoot_oot_reportable_edge_count": eligible_count,
        "width_gap_reportable_edge_count": width_reportable_count,
        "excluded_edge_count": len(h3_exclusions),
        "esf_reporting_excluded_edge_count": len(esf_reporting_exclusions),
        "second_peak_edge_count": len(peak_edges),
        "second_peak_count": second_peak_count,
        "pass": second_peak_count == 0,
        "exclusion_table": h3_exclusions,
        "esf_reporting_exclusion_table": esf_reporting_exclusions,
        "peak_edges": peak_edges,
        "esf": {
            "median_overshoot_delta": _median_or_none(overshoot_deltas),
            "worst_pair_overshoot_delta": max(overshoot_deltas) if overshoot_deltas else None,
            "median_width_gap_worsening_px": _median_or_none(width_worsenings),
            "worst_pair_width_gap_worsening_px": max(width_worsenings) if width_worsenings else None,
            "median_oot_delta": _median_or_none(oot_deltas),
            "worst_pair_oot_delta": max(oot_deltas) if oot_deltas else None,
        },
    }


def _aggregate_h3(rows: List[dict]) -> dict:
    def values(key: str) -> List[float]:
        return [row["esf"][key] for row in rows if row["esf"][key] is not None]

    med_over = values("median_overshoot_delta")
    worst_over = values("worst_pair_overshoot_delta")
    med_width = values("median_width_gap_worsening_px")
    worst_width = values("worst_pair_width_gap_worsening_px")
    med_oot = values("median_oot_delta")
    worst_oot = values("worst_pair_oot_delta")
    return {
        "all_cells_pass": all(row["pass"] for row in rows),
        "cell_count": len(rows),
        "protected_edge_count": sum(row["protected_edge_count"] for row in rows),
        "eligible_edge_count": sum(row["eligible_edge_count"] for row in rows),
        "overshoot_oot_reportable_edge_count": sum(
            row["overshoot_oot_reportable_edge_count"] for row in rows
        ),
        "width_gap_reportable_edge_count": sum(
            row["width_gap_reportable_edge_count"] for row in rows
        ),
        "excluded_edge_count": sum(row["excluded_edge_count"] for row in rows),
        "esf_reporting_excluded_edge_count": sum(
            row["esf_reporting_excluded_edge_count"] for row in rows
        ),
        "second_peak_edge_count": sum(row["second_peak_edge_count"] for row in rows),
        "second_peak_count": sum(row["second_peak_count"] for row in rows),
        "esf_reported": {
            "cohort_median_overshoot_delta": _median_or_none(med_over),
            "worst_pair_overshoot_delta": max(worst_over) if worst_over else None,
            "cohort_median_width_gap_worsening_px": _median_or_none(med_width),
            "worst_pair_width_gap_worsening_px": max(worst_width) if worst_width else None,
            "cohort_median_oot_delta": _median_or_none(med_oot),
            "worst_pair_oot_delta": max(worst_oot) if worst_oot else None,
        },
    }


def _rows_by_job(m2: dict, arm: str) -> Dict[str, dict]:
    return {row["job"]: row for row in m2["arm_cells"][arm]}


def evaluate_automatic_gate(
    arm: str,
    cells: List[dict],
    m2_rows: Dict[str, dict],
    geometry: Dict[str, bool],
    h3_rows: List[dict],
) -> dict:
    h1_cells = []
    for cell in cells:
        job = cell["job"]
        vs = m2_rows[job]["vs_A0"]
        row = {
            "job": job,
            "image": cell["image"],
            "seed": cell["seed"],
            "geometry_pass": bool(geometry[job]),
            "upstream_identity_pass": bool(vs["upstream_identity_pass"]),
            "protected_eatr_ratio_min": float(vs["protected_eatr_ratio_min"]),
            "protected_eatr_pass": float(vs["protected_eatr_ratio_min"]) >= PROTECTED_EATR_FLOOR,
        }
        row["pass"] = row["geometry_pass"] and row["upstream_identity_pass"] and row["protected_eatr_pass"]
        h1_cells.append(row)

    luma_max = max(float(m2_rows[cell["job"]]["vs_A0"]["smooth_luma_rise"]) for cell in cells)
    chroma_max = max(float(m2_rows[cell["job"]]["vs_A0"]["smooth_chroma_rise"]) for cell in cells)
    h1_pass = all(row["pass"] for row in h1_cells)
    h2_pass = luma_max <= LUMA_RISE_CEILING and chroma_max <= CHROMA_RISE_CEILING
    h3_pass = all(row["pass"] for row in h3_rows)
    h4_pass = arm != "A4"
    return {
        "H1_integrity": {"pass": h1_pass, "cells": h1_cells, "protected_eatr_floor": PROTECTED_EATR_FLOOR},
        "H2_amplitude": {
            "pass": h2_pass,
            "smooth_luma_rise_cohort_max": luma_max,
            "smooth_luma_ceiling": LUMA_RISE_CEILING,
            "smooth_chroma_rise_cohort_max": chroma_max,
            "smooth_chroma_ceiling": CHROMA_RISE_CEILING,
        },
        "H3_robust_second_peaks": {"pass": h3_pass, **_aggregate_h3(h3_rows), "cells": h3_rows},
        "H4_no_op_exclusion": {"pass": h4_pass, "excluded_arm": "A4"},
        "automatic_pass": h1_pass and h2_pass and h3_pass and h4_pass,
    }


def _reported_metrics(m2: dict, arm: str, h3_gate: dict) -> dict:
    summary = m2["cohort_summary"][arm]
    return {
        "smooth_rho1_rise_max": summary["smooth_rho1_rise_max"],
        "smooth_rho2_rise_max": summary["smooth_rho2_rise_max"],
        "smooth_rho_rise_max": summary["smooth_rho_rise_max"],
        "esf_eligible_edges": h3_gate["eligible_edge_count"],
        **h3_gate["esf_reported"],
        "panel_checklist_required": ["visible edge ringing", "coarse grain in smooth areas"],
        "gating_role": "reported_not_gated_panel_judged",
    }


def evaluate(bundle: InputBundle, recipes: FrozenRecipes) -> dict:
    h3_by_arm: Dict[str, List[dict]] = {arm: [] for arm in CHALLENGERS}
    geometry_by_arm: Dict[str, Dict[str, bool]] = {arm: {} for arm in CHALLENGERS}

    for cell_index, cell in enumerate(bundle.cells, 1):
        job = cell["job"]
        print("H3 cell {:02d}/12 {}/{}".format(cell_index, cell["image"], cell["seed"]), flush=True)
        a0_path = AR1 / "arms" / "A0" / job / "O5_final.jpg"
        a0_rgb = recipes.load(a0_path)
        source = recipes.load(CHECKPOINTS / job / "O0_source.png")
        reference = recipes.resample_to(source, a0_rgb.shape)
        a0_luma = recipes.luma(a0_rgb)
        source_luma = recipes.luma(reference)
        edges = recipes.edge_support(a0_luma, source_luma, bundle.roi[cell["image"]]["protected"])

        with Image.open(a0_path) as image:
            a0_geometry = image.size
        for arm in CHALLENGERS:
            arm_path = AR1 / "arms" / arm / job / "O5_final.jpg"
            with Image.open(arm_path) as image:
                geometry_by_arm[arm][job] = image.size == a0_geometry
            arm_luma = recipes.luma(recipes.load(arm_path))
            h3_by_arm[arm].append(evaluate_h3_cell(
                cell, arm, arm_luma, a0_luma, source_luma, edges, recipes.isotonic
            ))

    gates = {}
    shortlist = []
    for arm in CHALLENGERS:
        gates[arm] = evaluate_automatic_gate(
            arm, bundle.cells, _rows_by_job(bundle.m2, arm), geometry_by_arm[arm], h3_by_arm[arm]
        )
        if arm in ("A2", "A5") and gates[arm]["H2_amplitude"]["pass"]:
            raise FreezeViolation(arm + " unexpectedly passed its frozen measured H2 amplitudes")
        if gates[arm]["automatic_pass"]:
            shortlist.append(arm)

    reported = {
        arm: _reported_metrics(bundle.m2, arm, gates[arm]["H3_robust_second_peaks"])
        for arm in shortlist
    }
    status = "SHORTLIST_READY_PANEL_NOT_RUN" if shortlist else "EMPTY_SHORTLIST_STOP_NO_PANEL_NO_HIVE"
    result = {
        "commission": "4D-AR2",
        "status": status,
        "post_hoc_reanalysis": True,
        "production_admission": False,
        "new_arm_compute": False,
        "external_actions": [],
        "panel": {"authorized": bool(shortlist), "run": False},
        "hive": {"authorized": False, "calls": 0},
        "ar3_holdout_required_before_production": True,
        "input_pins": {
            "ar1_artifact_index_sha256": bundle.ar1_index_sha256,
            "frozen_files": FROZEN_FILE_PINS,
        },
        "thresholds": {
            "H1_protected_eatr_floor": PROTECTED_EATR_FLOOR,
            "H2_luma_rise_ceiling": LUMA_RISE_CEILING,
            "H2_chroma_rise_ceiling": CHROMA_RISE_CEILING,
            "H3_plateau_step_min": H3_STEP_MIN,
            "H3_width_10_90_inclusive": [H3_WIDTH_MIN, H3_WIDTH_MAX],
            "H3_second_peak_amplitude_strictly_greater_than_step_fraction": H3_PEAK_AMPLITUDE_MIN,
            "H3_endpoint_separation_min_px": H3_ENDPOINT_SEPARATION_MIN,
            "H3_required_second_peaks_per_cell": 0,
        },
        "automatic_gates": gates,
        "shortlist": shortlist,
        "reported_panel_judged_metrics": reported,
        "input_verification": {"pass": True, "check_count": len(bundle.checks), "checks": bundle.checks},
    }
    _require_finite(result)
    return result


def _format(value: Optional[float], digits: int = 4) -> str:
    return "n/a" if value is None else format(value, ".{}f".format(digits))


def _write_report(path: Path, result: dict) -> None:
    shortlist = result["shortlist"]
    status = "SHORTLIST READY — PANEL AUTHORIZED" if shortlist else "EMPTY SHORTLIST — STOP BEFORE PANEL/HIVE"
    lines = [
        "# C8 4D-AR2 Shortlist",
        "",
        "**Status: {}.**".format(status),
        "",
        "Post-hoc AR1 metric-domain reanalysis only. No arm was rendered, no panel was run, no winner was selected, and no Hive/vendor call was made by this harness.",
        "",
        "## Automatic gates",
        "",
        "| Arm | H1 integrity | H2 amplitude | H3 robust peaks | H4 no-op | Shortlist |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for arm in CHALLENGERS:
        gate = result["automatic_gates"][arm]
        lines.append("| {} | {} | {} | {} | {} | {} |".format(
            arm,
            "PASS" if gate["H1_integrity"]["pass"] else "FAIL",
            "PASS" if gate["H2_amplitude"]["pass"] else "FAIL",
            "PASS" if gate["H3_robust_second_peaks"]["pass"] else "FAIL",
            "PASS" if gate["H4_no_op_exclusion"]["pass"] else "FAIL",
            "YES" if gate["automatic_pass"] else "NO",
        ))
    lines.extend(["", "Shortlist: **{}**.".format(", ".join(shortlist) if shortlist else "empty")])
    lines.extend([
        "",
        "## H3 profile-domain accounting",
        "",
        "| Arm | Protected edges | Eligible | Excluded | Second-peak edges | Second peaks |",
        "|---|---:|---:|---:|---:|---:|",
    ])
    for arm in CHALLENGERS:
        h3 = result["automatic_gates"][arm]["H3_robust_second_peaks"]
        lines.append("| {} | {} | {} | {} | {} | {} |".format(
            arm,
            h3["protected_edge_count"],
            h3["eligible_edge_count"],
            h3["excluded_edge_count"],
            h3["second_peak_edge_count"],
            h3["second_peak_count"],
        ))

    if shortlist:
        lines.extend([
            "",
            "## Reported, panel-judged metrics",
            "",
            "| Arm | rho1 rise | rho2 rise | eligible edges | median/worst overshoot | median/worst width gap |",
            "|---|---:|---:|---:|---:|---:|",
        ])
        for arm in shortlist:
            row = result["reported_panel_judged_metrics"][arm]
            lines.append("| {} | {} | {} | {} | {} / {} | {} / {} |".format(
                arm,
                _format(row["smooth_rho1_rise_max"]),
                _format(row["smooth_rho2_rise_max"]),
                row["esf_eligible_edges"],
                _format(row["cohort_median_overshoot_delta"]),
                _format(row["worst_pair_overshoot_delta"]),
                _format(row["cohort_median_width_gap_worsening_px"]),
                _format(row["worst_pair_width_gap_worsening_px"]),
            ))
        lines.extend([
            "",
            "Panel checklist additions: **visible edge ringing** and **coarse grain in smooth areas**, per image and viewing scale.",
            "",
            "Panel results remain unobserved. A single winner must be frozen by exact hashes and settings before any Hive call.",
        ])
    else:
        lines.extend(["", "Fail-closed disposition: no panel, candidate freeze, or Hive call is authorized."])
    lines.extend([
        "",
        "## Builder declaration",
        "",
        "This evaluator consumed only the pinned AR1 record and frozen local recipes. It performed no new arm computation and no external action.",
        "",
        "Signed: **C88 builder (Codex)**  ",
        "Commission date: **2026-08-29 (Australia/Sydney)**",
        "",
    ])
    path.write_text("\n".join(lines), encoding="utf-8")


def _artifact_index(directory: Path, report_path: Path) -> dict:
    files = []
    for path in sorted(directory.rglob("*")):
        if not path.is_file() or path.name == "artifact-index.json":
            continue
        files.append({
            "path": "round-4d-ar2/" + path.relative_to(directory).as_posix(),
            "sha256": _sha256(path),
            "bytes": path.stat().st_size,
        })
    extras = [
        (report_path, REPORT_PATH.name),
        (FREEZE_PATH, FREEZE_PATH.name),
        (Path(__file__), Path(__file__).relative_to(ROOT).as_posix()),
        (TOOLS_DIR / "test_round_4d_ar2_floors.py", "deepclean-worker/tools/test_round_4d_ar2_floors.py"),
    ]
    for path, logical in extras:
        if not path.is_file():
            raise FreezeViolation("artifact-index input missing: " + str(path))
        files.append({"path": logical, "sha256": _sha256(path), "bytes": path.stat().st_size})
    files.sort(key=lambda row: row["path"])
    index = {
        "scope": "4D-AR2 floor reanalysis, shortlist report, authority, evaluator, and tests",
        "self_exclusion": "artifact-index.json cannot hash itself",
        "files": files,
    }
    _write_json(directory / "artifact-index.json", index)
    return index


def _ensure_clean_output_targets() -> None:
    occupied = [path for path in (OUT, WORK_OUT, REPORT_PATH, WORK_REPORT_PATH) if path.exists()]
    if occupied:
        raise FreezeViolation("refusing to overwrite existing output target(s): " + ", ".join(map(str, occupied)))


def write_outputs(result: dict) -> None:
    _ensure_clean_output_targets()
    WORK_OUT.mkdir(parents=False, exist_ok=False)
    _write_json(WORK_OUT / "floors.json", result)
    _write_report(WORK_REPORT_PATH, result)
    _artifact_index(WORK_OUT, WORK_REPORT_PATH)
    WORK_OUT.rename(OUT)
    WORK_REPORT_PATH.rename(REPORT_PATH)


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="verify frozen environment and AR1 pins without computing H3 or writing artifacts",
    )
    args = parser.parse_args(argv)
    try:
        environment = verify_environment()
        bundle = verify_inputs()
        if args.verify_only:
            print("PASS: frozen environment and {} AR2 input checks; no artifacts written".format(
                len(bundle.checks)
            ))
            return 0
        _ensure_clean_output_targets()
        recipes = load_frozen_recipes()
        result = evaluate(bundle, recipes)
        result["environment_verification"] = environment
        write_outputs(result)
        print("PASS: AR2 automatic gates complete; shortlist={}".format(
            ",".join(result["shortlist"]) if result["shortlist"] else "empty"
        ))
        return 0
    except Exception as exc:
        print("HARD STOP: {}: {}".format(type(exc).__name__, exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
