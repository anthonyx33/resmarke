#!/usr/bin/env python3
"""Frozen 4D-1b OR->O2 H1 preservation candidate.

Replay-only implementation commissioned by
``C8_MASTER_PROMPT_4D_1B_REPLAY_BUILD_BRIEF_V21.md``.  The synthesis boundary
is deliberately narrow: only OR_postresample and O2_precamera pixels enter
this module.  Downstream O0 tone matching belongs to the replay harness.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from PIL import Image

import checkpoint_attribution as ca


WINDOW = 15
RADIUS = WINDOW // 2
STRIDE = 3
DOSE = 0.25
NCC_MIN = 0.90
ORIENTATION_MAX_RAD = math.radians(10.0)
SNR_MIN = 4.0
EPS = 1e-9
CAP_REL_TOL = 1e-9


@dataclass(frozen=True)
class CandidateResult:
    rgb: np.ndarray
    support: np.ndarray
    report: dict


def _as_rgb_u8(value: np.ndarray | Image.Image) -> np.ndarray:
    if isinstance(value, Image.Image):
        arr = np.asarray(value.convert("RGB"), dtype=np.uint8)
    else:
        arr = np.asarray(value)
        if arr.ndim != 3 or arr.shape[2] < 3:
            raise ValueError("candidate inputs must be HxWx3 RGB images")
        arr = arr[..., :3]
        if arr.dtype != np.uint8:
            if np.issubdtype(arr.dtype, np.floating):
                arr = np.rint(np.clip(arr, 0.0, 1.0) * 255.0).astype(np.uint8)
            else:
                arr = np.clip(arr, 0, 255).astype(np.uint8)
    return np.ascontiguousarray(arr)


def _box_sum_reflect(a: np.ndarray, size: int = WINDOW) -> np.ndarray:
    """Centered box sum with NumPy reflect borders, returned at input size."""
    r = size // 2
    padded = np.pad(np.asarray(a, dtype=np.float64), ((r, r), (r, r)), mode="reflect")
    integral = np.pad(padded, ((1, 0), (1, 0)), mode="constant")
    integral = np.cumsum(np.cumsum(integral, axis=0), axis=1)
    return (
        integral[size:, size:]
        - integral[:-size, size:]
        - integral[size:, :-size]
        + integral[:-size, :-size]
    )


def _box_mean(a: np.ndarray, size: int = WINDOW) -> np.ndarray:
    return _box_sum_reflect(a, size) / float(size * size)


def _window_sums(a: np.ndarray, size: int = WINDOW, stride: int = STRIDE) -> np.ndarray:
    """In-bounds grid-window sums, top-left origins 0,size... at stride 3."""
    arr = np.asarray(a, dtype=np.float64)
    integral = np.pad(arr, ((1, 0), (1, 0)), mode="constant")
    integral = np.cumsum(np.cumsum(integral, axis=0), axis=1)
    sums = (
        integral[size:, size:]
        - integral[:-size, size:]
        - integral[size:, :-size]
        + integral[:-size, :-size]
    )
    return sums[::stride, ::stride]


def _grid_centers(shape: tuple[int, int]) -> tuple[np.ndarray, np.ndarray]:
    h, w = shape
    return np.arange(RADIUS, h - RADIUS, STRIDE), np.arange(RADIUS, w - RADIUS, STRIDE)


def _euclidean_dilate_2(mask: np.ndarray) -> np.ndarray:
    padded = np.pad(mask.astype(bool), 2, mode="constant")
    out = np.zeros_like(mask, dtype=bool)
    h, w = mask.shape
    for dy in range(-2, 3):
        for dx in range(-2, 3):
            if dx * dx + dy * dy <= 4:
                out |= padded[2 + dy : 2 + dy + h, 2 + dx : 2 + dx + w]
    return out


def _noise_energy(or_h1: np.ndarray, or_edge: np.ndarray) -> tuple[float, int]:
    tiles: list[tuple[float, int, int, int, int]] = []
    h, w = or_h1.shape
    for y0 in range(0, h, 32):
        for x0 in range(0, w, 32):
            y1, x1 = min(y0 + 32, h), min(x0 + 32, w)
            tiles.append((float(np.mean(or_edge[y0:y1, x0:x1] ** 2)), y0, y1, x0, x1))
    tiles.sort(key=lambda item: (item[0], item[1], item[3]))
    count = max(1, int(math.ceil(0.20 * len(tiles))))
    samples = np.concatenate(
        [or_h1[y0:y1, x0:x1].ravel() for _, y0, y1, x0, x1 in tiles[:count]]
    )
    median = float(np.median(samples))
    mad = float(np.median(np.abs(samples - median)))
    return max((1.4826 * mad) ** 2, 1e-6), count


def _local_agreement(or_h1: np.ndarray, o2_h1: np.ndarray, noise: float) -> dict[str, np.ndarray]:
    mean_or = _box_mean(or_h1)
    mean_o2 = _box_mean(o2_h1)
    var_or = np.maximum(_box_mean(or_h1 * or_h1) - mean_or * mean_or, 0.0)
    var_o2 = np.maximum(_box_mean(o2_h1 * o2_h1) - mean_o2 * mean_o2, 0.0)
    denominator = np.sqrt(var_or) * np.sqrt(var_o2)
    covariance = _box_mean(or_h1 * o2_h1) - mean_or * mean_o2
    ncc = np.zeros_like(covariance)
    ncc_valid = denominator > EPS
    ncc[ncc_valid] = covariance[ncc_valid] / denominator[ncc_valid]

    def orientation(field: np.ndarray) -> np.ndarray:
        gy, gx = np.gradient(field)
        jxx = _box_sum_reflect(gx * gx)
        jyy = _box_sum_reflect(gy * gy)
        jxy = _box_sum_reflect(gx * gy)
        return np.mod(0.5 * np.arctan2(2.0 * jxy, jxx - jyy), math.pi)

    angle_or = orientation(or_h1)
    angle_o2 = orientation(o2_h1)
    angle_delta = np.abs(angle_or - angle_o2)
    angle_delta = np.minimum(angle_delta, math.pi - angle_delta)
    snr = _box_mean(or_h1 * or_h1) / noise
    return {
        "ncc": ncc,
        "ncc_valid": ncc_valid,
        "orientation_delta": angle_delta,
        "snr": snr,
    }


def _synthesize(o2_rgb: np.ndarray, delta: np.ndarray) -> tuple[np.ndarray, float]:
    base = o2_rgb.astype(np.float64) / 255.0
    lower = -np.min(base, axis=2)
    upper = 1.0 - np.max(base, axis=2)
    safe = np.clip(delta, lower, upper)
    capped = int(np.count_nonzero(np.abs(safe - delta) > 0.0))
    out = np.clip(base + safe[..., None], 0.0, 1.0)
    # One explicit quantization operation. np.rint is deterministic ties-to-even.
    out_u8 = np.rint(out * 255.0).astype(np.uint8)
    return out_u8, capped / float(delta.size)


def _h1(rgb_u8: np.ndarray) -> np.ndarray:
    rgb = rgb_u8.astype(np.float64) / 255.0
    y = ca._luma(rgb)
    return ca._gauss(y, 0.7) - ca._gauss(y, 1.4)


def _cap_state(
    or_h1: np.ndarray,
    o2_h1: np.ndarray,
    candidate_h1: np.ndarray,
    support: np.ndarray,
    ncc_valid: np.ndarray,
) -> dict:
    e_or = _window_sums(or_h1 * or_h1)
    e_o2 = _window_sums(o2_h1 * o2_h1)
    e_candidate = _window_sums(candidate_h1 * candidate_h1)
    support_hits = _window_sums(support.astype(np.float64)) > 0.0
    ys, xs = _grid_centers(or_h1.shape)
    valid_ncc = ncc_valid[np.ix_(ys, xs)]
    finite = np.isfinite(e_or) & np.isfinite(e_o2) & np.isfinite(e_candidate)
    positive_loss = (e_or - e_o2) > 0.0
    valid = finite & valid_ncc & positive_loss & support_hits
    lower_tol = CAP_REL_TOL * np.maximum(e_o2, EPS)
    upper_tol = CAP_REL_TOL * np.maximum(e_or, EPS)
    lower_bad = valid & (e_candidate < e_o2 - lower_tol)
    upper_bad = valid & (e_candidate > e_or + upper_tol)
    return {
        "e_or": e_or,
        "e_o2": e_o2,
        "e_candidate": e_candidate,
        "valid": valid,
        "lower_bad": lower_bad,
        "upper_bad": upper_bad,
    }


def _recovery_report(state: dict, or_h1: np.ndarray, o2_h1: np.ndarray) -> dict:
    e_or, e_o2, e_c = state["e_or"], state["e_o2"], state["e_candidate"]
    valid = state["valid"]
    eligible_den = float(np.sum((e_or - e_o2)[valid]))
    eligible_num = float(np.sum((e_c - e_o2)[valid]))
    positive = (e_or - e_o2) > 0.0
    whole_den = float(np.sum((e_or - e_o2)[positive]))
    whole_num = float(np.sum((e_c - e_o2)[positive]))
    global_r = float(np.sum(o2_h1 * o2_h1) / max(np.sum(or_h1 * or_h1), EPS))
    ceiling_r = (0.75 * math.sqrt(max(global_r, 0.0)) + 0.25) ** 2
    ceiling = (ceiling_r - global_r) / max(1.0 - global_r, EPS)
    return {
        "valid_window_count": int(np.count_nonzero(valid)),
        "eligible_recovery": eligible_num / eligible_den if eligible_den > 0.0 else None,
        "eligible_numerator": eligible_num,
        "eligible_denominator": eligible_den,
        "whole_frame_recovery": whole_num / whole_den if whole_den > 0.0 else None,
        "whole_frame_numerator": whole_num,
        "whole_frame_denominator": whole_den,
        "eligible_lost_energy_mass": eligible_den / whole_den if whole_den > 0.0 else None,
        "global_o2_or_energy_ratio": global_r,
        "perfect_correlation_ceiling": ceiling,
    }


def build_candidate(or_rgb: np.ndarray | Image.Image, o2_rgb: np.ndarray | Image.Image) -> CandidateResult:
    """Build one deterministic candidate or return O2 unchanged on cap failure."""
    or_u8, o2_u8 = _as_rgb_u8(or_rgb), _as_rgb_u8(o2_rgb)
    if or_u8.shape != o2_u8.shape:
        raise ValueError(f"OR/O2 geometry mismatch: {or_u8.shape} vs {o2_u8.shape}")
    if min(or_u8.shape[:2]) < WINDOW:
        raise ValueError("candidate inputs must be at least 15x15")

    or_float = or_u8.astype(np.float64) / 255.0
    o2_float = o2_u8.astype(np.float64) / 255.0
    or_luma, o2_luma = ca._luma(or_float), ca._luma(o2_float)
    or_h1 = ca._gauss(or_luma, 0.7) - ca._gauss(or_luma, 1.4)
    o2_h1 = ca._gauss(o2_luma, 0.7) - ca._gauss(o2_luma, 1.4)
    or_edge, o2_edge = ca._edge_mag(or_luma), ca._edge_mag(o2_luma)
    noise, low_tile_count = _noise_energy(or_h1, or_edge)
    agreement = _local_agreement(or_h1, o2_h1, noise)

    same_sign = np.signbit(or_h1) == np.signbit(o2_h1)
    magnitude_order = np.abs(or_h1) >= np.abs(o2_h1)
    flat_threshold = float(np.percentile(or_edge, 30.0))
    not_flat = or_edge >= flat_threshold
    saturated = np.any((or_u8 >= 250) | (or_u8 <= 5) | (o2_u8 >= 250) | (o2_u8 <= 5), axis=2)
    saturation_window = _box_sum_reflect(saturated.astype(np.float64)) > 0.0
    strong = (or_edge >= np.percentile(or_edge, 92.0)) | (o2_edge >= np.percentile(o2_edge, 92.0))
    strong_exclusion = _euclidean_dilate_2(strong)

    finite = np.isfinite(or_h1) & np.isfinite(o2_h1)
    support = (
        finite
        & agreement["ncc_valid"]
        & (agreement["ncc"] >= NCC_MIN)
        & (agreement["orientation_delta"] <= ORIENTATION_MAX_RAD)
        & (agreement["snr"] >= SNR_MIN)
        & same_sign
        & magnitude_order
        & not_flat
        & ~saturation_window
        & ~strong_exclusion
    )
    requested_delta = DOSE * (or_h1 - o2_h1) * support
    first_u8, first_capped_fraction = _synthesize(o2_u8, requested_delta)
    first_state = _cap_state(or_h1, o2_h1, _h1(first_u8), support, agreement["ncc_valid"])

    rescale_applied = bool(np.any(first_state["upper_bad"]))
    final_u8 = first_u8
    final_capped_fraction = first_capped_fraction
    if rescale_applied:
        factors = np.ones_like(first_state["e_candidate"], dtype=np.float64)
        bad = first_state["upper_bad"]
        numerator = np.maximum(first_state["e_or"] - first_state["e_o2"], 0.0)
        denominator = np.maximum(first_state["e_candidate"] - first_state["e_o2"], EPS)
        factors[bad] = np.clip(np.sqrt(numerator[bad] / denominator[bad]), 0.0, 1.0)
        factor_image = Image.fromarray(factors.astype(np.float32), mode="F").resize(
            (o2_u8.shape[1], o2_u8.shape[0]), Image.Resampling.BILINEAR
        )
        factor_map = np.asarray(factor_image, dtype=np.float64)
        final_u8, final_capped_fraction = _synthesize(o2_u8, requested_delta * factor_map)

    final_state = _cap_state(or_h1, o2_h1, _h1(final_u8), support, agreement["ncc_valid"])
    remaining_lower = int(np.count_nonzero(final_state["lower_bad"]))
    remaining_upper = int(np.count_nonzero(final_state["upper_bad"]))
    empty_support = int(np.count_nonzero(support)) == 0
    fail_closed = empty_support or remaining_lower > 0 or remaining_upper > 0
    stop_reason = None
    if empty_support:
        stop_reason = "empty_support"
    elif remaining_lower or remaining_upper:
        stop_reason = "post_quantization_energy_cap_violation"

    if fail_closed:
        final_u8 = o2_u8.copy()
        # Gate-B numbers remain measurements of the attempted, capped candidate.
    recovery = _recovery_report(final_state, or_h1, o2_h1)
    changed = np.any(final_u8 != o2_u8, axis=2)
    report = {
        "candidate": "O2_H1 + 0.25*(OR_H1-O2_H1)",
        "data_boundary": ["OR_postresample", "O2_precamera"],
        "shape": [int(v) for v in o2_u8.shape],
        "noise_energy": noise,
        "low_noise_tile_count": low_tile_count,
        "flat_edge_p30": flat_threshold,
        "or_edge_p92": float(np.percentile(or_edge, 92.0)),
        "o2_edge_p92": float(np.percentile(o2_edge, 92.0)),
        "support_pixels": int(np.count_nonzero(support)),
        "support_fraction": float(np.mean(support)),
        "requested_nonzero_pixels": int(np.count_nonzero(requested_delta)),
        "quantized_changed_pixels": int(np.count_nonzero(changed)),
        "quantized_changed_fraction": float(np.mean(changed)),
        "safe_clip_pixel_fraction": final_capped_fraction,
        "rescale_applied": rescale_applied,
        "first_upper_violations": int(np.count_nonzero(first_state["upper_bad"])),
        "first_lower_violations": int(np.count_nonzero(first_state["lower_bad"])),
        "remaining_upper_violations": remaining_upper,
        "remaining_lower_violations": remaining_lower,
        "fail_closed": fail_closed,
        "stop_reason": stop_reason,
        "recovery": recovery,
        "eligibility_counts": {
            "ncc": int(np.count_nonzero(agreement["ncc_valid"] & (agreement["ncc"] >= NCC_MIN))),
            "orientation": int(np.count_nonzero(agreement["orientation_delta"] <= ORIENTATION_MAX_RAD)),
            "snr": int(np.count_nonzero(agreement["snr"] >= SNR_MIN)),
            "same_sign": int(np.count_nonzero(same_sign)),
            "magnitude_order": int(np.count_nonzero(magnitude_order)),
            "not_flat": int(np.count_nonzero(not_flat)),
            "not_saturated_window": int(np.count_nonzero(~saturation_window)),
            "not_strong_edge": int(np.count_nonzero(~strong_exclusion)),
        },
    }
    return CandidateResult(rgb=final_u8, support=support, report=report)

