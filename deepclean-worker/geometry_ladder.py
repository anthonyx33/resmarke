"""Frozen C8 v4.4 geometry-ladder contract.

Conservative shift-aware overscan margin (§5 of the v4.4 master brief)
and the aspect-safe 0.90 retained-area floor.  The Phase-A allow-list is
deliberately closed.  A future Phase-B build may extend the tuple table,
but it must reuse the transform construction here.
"""

from __future__ import annotations

import math
from typing import Any

import cv2
import numpy as np
from PIL import Image


LANCZOS4_SUPPORT = 4.0
SAFETY_FACTOR = 1.0 + 1e-4
SQUASH_X = 0.988
SHIFT = (0.5, 0.3)

GEOMETRY_PRESETS: dict[str, dict[str, Any]] = {
    "geom-r0": {"resample_mode": "bypass", "resize_target": 1250, "tilt_degrees": 0.0, "micro_warp": "none"},
    "geom-x0": {"resample_mode": "affine", "resize_target": 1250, "tilt_degrees": 0.0, "micro_warp": "none"},
    "geom-r1": {"resample_mode": "affine", "resize_target": 1000, "tilt_degrees": 0.0, "micro_warp": "none"},
    "geom-r2": {"resample_mode": "affine", "resize_target": 800, "tilt_degrees": 0.0, "micro_warp": "none"},
    "geom-r3": {"resample_mode": "affine", "resize_target": 1250, "tilt_degrees": 0.6, "micro_warp": "none"},
    "geom-r4": {"resample_mode": "affine", "resize_target": 1250, "tilt_degrees": 1.2, "micro_warp": "none"},
    "geom-r5": {"resample_mode": "affine", "resize_target": 1250, "tilt_degrees": 0.0, "micro_warp": "shift"},
    "geom-r6": {"resample_mode": "affine", "resize_target": 1250, "tilt_degrees": 0.0, "micro_warp": "shift_squash"},
}

_GEOMETRY_KEYS = frozenset(("resample_mode", "resize_target", "tilt_degrees", "micro_warp"))


def _numeric(value: Any) -> bool:
    return not isinstance(value, (bool, np.bool_)) and isinstance(
        value, (int, float, np.integer, np.floating)
    ) and math.isfinite(float(value))


def _tuple_key(geometry: dict[str, Any]) -> tuple[str, int, float, str]:
    return (
        str(geometry["resample_mode"]),
        int(geometry["resize_target"]),
        float(geometry["tilt_degrees"]),
        str(geometry["micro_warp"]),
    )


_ALLOWED_TUPLES = frozenset(_tuple_key(value) for value in GEOMETRY_PRESETS.values())


def normalize_geometry_settings(
    value: Any,
    supplied: bool,
    output_target: Any = None,
) -> dict[str, Any] | None:
    """Validate a complete wire-format block against the eight Phase-A cells."""
    if not supplied:
        return None
    if not isinstance(value, dict):
        raise ValueError("geometry must be an object when supplied")
    keys = set(value)
    if keys != _GEOMETRY_KEYS:
        unknown = sorted(keys - _GEOMETRY_KEYS)
        missing = sorted(_GEOMETRY_KEYS - keys)
        raise ValueError(
            "geometry must contain exactly resample_mode, resize_target, "
            f"tilt_degrees, micro_warp; unknown={unknown or 'none'}; missing={missing or 'none'}"
        )
    if not isinstance(value["resample_mode"], str) or not isinstance(value["micro_warp"], str):
        raise ValueError("geometry modes must be strings")
    if not _numeric(value["resize_target"]) or not _numeric(value["tilt_degrees"]):
        raise ValueError("geometry resize_target and tilt_degrees must be finite numbers")
    if float(value["resize_target"]) not in (800.0, 1000.0, 1250.0):
        raise ValueError("geometry resize_target must be 1250, 1000, or 800")

    normalized = {
        "resample_mode": value["resample_mode"],
        "resize_target": int(value["resize_target"]),
        "tilt_degrees": float(value["tilt_degrees"]),
        "micro_warp": value["micro_warp"],
    }
    if _tuple_key(normalized) not in _ALLOWED_TUPLES:
        raise ValueError("geometry must exactly match one registered Phase-A preset")

    if output_target is not None:
        if not _numeric(output_target) or float(output_target) != float(normalized["resize_target"]):
            raise ValueError("output_target and geometry.resize_target must agree when both are supplied")
    return normalized


def geometry_preset_id(geometry: dict[str, Any]) -> str:
    key = _tuple_key(geometry)
    for preset_id, frozen in GEOMETRY_PRESETS.items():
        if _tuple_key(frozen) == key:
            return preset_id
    raise ValueError("geometry tuple is not a registered Phase-A preset")


def _transform_components(geometry: dict[str, Any]) -> tuple[float, float, float, float]:
    theta = math.radians(float(geometry["tilt_degrees"]))
    squash = SQUASH_X if geometry["micro_warp"] == "shift_squash" else 1.0
    shift_x, shift_y = SHIFT if geometry["micro_warp"] in ("shift", "shift_squash") else (0.0, 0.0)
    return theta, squash, shift_x, shift_y


def overscan_scale(width: int, height: int, geometry: dict[str, Any]) -> float:
    """Return the v4.4 conservative shift-aware margin scale (tilt regime).

    Frozen §5 v4.4 construction: B = Rᵀ·diag(1/a,1), t = (0.5,0.3) iff
    shift/shift_squash, den = half − L − |t| per axis, and
    s = max(1, |v_k.x|/den_x, |v_k.y|/den_y) over the four corners,
    times the frozen 1+1e-4 safety factor.  The source-space shift t is
    NOT divided by s in the executed inverse, so the v4.3 form
    |B·p_k + t|/(half − L) under-scaled when t ≠ 0 (measured margins
    3.9891–3.9974 px below L on 800/1000-cap portrait joints).  The
    v4.4 form guarantees the Lanczos4 support margin BY CONSTRUCTION for
    every permitted tuple including the Phase-B joints.  For the
    pure-tilt Phase-A arms (t = 0) it reduces exactly to the registered
    formula, so the pinned matrices are unchanged.
    """
    theta, squash, shift_x, shift_y = _transform_components(geometry)
    if theta == 0.0:
        return 1.0
    half_x = (width - 1.0) / 2.0
    half_y = (height - 1.0) / 2.0
    denominator_x = half_x - LANCZOS4_SUPPORT - abs(shift_x)
    denominator_y = half_y - LANCZOS4_SUPPORT - abs(shift_y)
    if denominator_x <= 0.0 or denominator_y <= 0.0:
        raise ValueError(
            "geometry tilt requires both image axes to exceed the Lanczos4 support margin plus shift"
        )
    cosine = math.cos(theta)
    sine = math.sin(theta)
    # B = Rᵀ · diag(1/a, 1); a = SQUASH_X iff shift_squash else 1.
    b00 = cosine / squash
    b01 = sine
    b10 = -sine / squash
    b11 = cosine
    scale = 1.0
    for corner_x in (-half_x, half_x):
        for corner_y in (-half_y, half_y):
            vx = b00 * corner_x + b01 * corner_y
            vy = b10 * corner_x + b11 * corner_y
            scale = max(scale, abs(vx) / denominator_x)
            scale = max(scale, abs(vy) / denominator_y)
    return scale * SAFETY_FACTOR


def build_affine_matrices(
    width: int,
    height: int,
    geometry: dict[str, Any],
) -> tuple[np.ndarray, np.ndarray, float, int]:
    """Build float64 forward/inverse matrices; the inverse is executed by OpenCV."""
    if width <= 0 or height <= 0:
        raise ValueError("geometry image dimensions must be positive")
    theta, squash, shift_x, shift_y = _transform_components(geometry)
    cosine = math.cos(theta)
    sine = math.sin(theta)
    rotation = np.array(((cosine, sine), (-sine, cosine)), dtype=np.float64)
    squash_matrix = np.array(((squash, 0.0), (0.0, 1.0)), dtype=np.float64)
    linear = squash_matrix @ rotation
    scale = overscan_scale(width, height, geometry)
    center = np.array(((width - 1.0) / 2.0, (height - 1.0) / 2.0), dtype=np.float64)
    shift = np.array((shift_x, shift_y), dtype=np.float64)

    forward_linear = scale * linear
    forward_translation = center - forward_linear @ (center + shift)
    forward = np.column_stack((forward_linear, forward_translation)).astype(np.float64)
    inverse = cv2.invertAffineTransform(forward).astype(np.float64)
    border_mode = cv2.BORDER_CONSTANT if theta > 0.0 else cv2.BORDER_REPLICATE
    return forward, inverse, scale, border_mode


def source_coordinate_margin(width: int, height: int, inverse: np.ndarray) -> float:
    """Minimum source-space distance between mapped output corners and an edge."""
    corners = np.array(
        ((0.0, 0.0), (width - 1.0, 0.0), (0.0, height - 1.0), (width - 1.0, height - 1.0)),
        dtype=np.float64,
    )
    mapped = corners @ inverse[:, :2].T + inverse[:, 2]
    return float(min(
        np.min(mapped[:, 0]),
        (width - 1.0) - np.max(mapped[:, 0]),
        np.min(mapped[:, 1]),
        (height - 1.0) - np.max(mapped[:, 1]),
    ))


def retained_source_area_fraction(forward: np.ndarray) -> float:
    """Fraction of unique source area retained by the output window.

    With guaranteed coverage this is the inverse absolute area scale, capped
    at one for squash/replicate arms whose output contains the full source.
    """
    area_scale = abs(float(np.linalg.det(forward[:, :2])))
    if area_scale <= 0.0 or not math.isfinite(area_scale):
        raise ValueError("geometry forward transform must have a finite positive area scale")
    return min(1.0, 1.0 / area_scale)


def diagnostic_mask(width: int, height: int, inverse: np.ndarray) -> np.ndarray:
    """Warp an all-255 mask with the exact matrix and a zero diagnostic border."""
    mask = np.full((height, width), 255, dtype=np.uint8)
    return cv2.warpAffine(
        mask,
        inverse,
        (width, height),
        flags=cv2.INTER_LANCZOS4 | cv2.WARP_INVERSE_MAP,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=0,
    )


def _edge_run(line: np.ndarray, reverse: bool = False) -> int:
    values = line[::-1] if reverse else line
    count = 0
    for value in values:
        if int(value) == 255:
            break
        count += 1
    return count


def kernel_affected_strips(mask: np.ndarray) -> dict[str, int]:
    """Measure edge-normal runs, excluding scanlines hit by an orthogonal edge.

    This removes corner overlap while still taking the maximum eligible run for
    each edge, which makes the v4.4 replicated-strip diagnostic reproducible.
    """
    height, width = mask.shape[:2]
    center_x = width // 2
    center_y = height // 2
    horizontal_rows = [row for row in range(height) if int(mask[row, center_x]) == 255]
    vertical_columns = [column for column in range(width) if int(mask[center_y, column]) == 255]
    return {
        "left": max((_edge_run(mask[row, :]) for row in horizontal_rows), default=width),
        "right": max((_edge_run(mask[row, :], True) for row in horizontal_rows), default=width),
        "top": max((_edge_run(mask[:, column]) for column in vertical_columns), default=height),
        "bottom": max((_edge_run(mask[:, column], True) for column in vertical_columns), default=height),
    }


def apply_geometry(image: Image.Image, geometry: dict[str, Any]) -> tuple[Image.Image, dict[str, Any]]:
    """Apply zero or one geometry call after the existing Pillow resize."""
    preset_id = geometry_preset_id(geometry)
    if geometry["resample_mode"] == "bypass":
        return image, {
            "applied": False,
            "preset_id": preset_id,
            "resample_mode": "bypass",
            "warp_affine_calls": 0,
            "output_size": [image.width, image.height],
        }

    forward, inverse, scale, border_mode = build_affine_matrices(image.width, image.height, geometry)
    source = np.asarray(image.convert("RGB"), dtype=np.uint8)
    output = cv2.warpAffine(
        source,
        inverse,
        (image.width, image.height),
        flags=cv2.INTER_LANCZOS4 | cv2.WARP_INVERSE_MAP,
        borderMode=border_mode,
        borderValue=(0, 0, 0),
    )
    report = {
        "applied": True,
        "preset_id": preset_id,
        "resample_mode": "affine",
        "warp_affine_calls": 1,
        "interpolation": "INTER_LANCZOS4",
        "border_mode": "BORDER_CONSTANT" if border_mode == cv2.BORDER_CONSTANT else "BORDER_REPLICATE",
        "scale": scale,
        "forward_matrix": forward.tolist(),
        "inverse_matrix": inverse.tolist(),
        "source_margin": source_coordinate_margin(image.width, image.height, inverse),
        "output_size": [image.width, image.height],
    }
    return Image.fromarray(output), report


def transform_normalized_box(
    box: tuple[float, float, float, float],
    width: int,
    height: int,
    forward: np.ndarray,
) -> tuple[tuple[float, float, float, float], float]:
    """Map four normalized ROI corners, clip, and return its AABB/inflation."""
    x0, y0, x1, y1 = box
    corners = np.array(
        (
            (x0 * (width - 1.0), y0 * (height - 1.0)),
            (x1 * (width - 1.0), y0 * (height - 1.0)),
            (x0 * (width - 1.0), y1 * (height - 1.0)),
            (x1 * (width - 1.0), y1 * (height - 1.0)),
        ),
        dtype=np.float64,
    )
    mapped = corners @ forward[:, :2].T + forward[:, 2]
    mapped[:, 0] /= max(width - 1.0, 1.0)
    mapped[:, 1] /= max(height - 1.0, 1.0)
    mapped = np.clip(mapped, 0.0, 1.0)
    result = (
        float(np.min(mapped[:, 0])),
        float(np.min(mapped[:, 1])),
        float(np.max(mapped[:, 0])),
        float(np.max(mapped[:, 1])),
    )
    source_area = max((x1 - x0) * (y1 - y0), 0.0)
    result_area = max((result[2] - result[0]) * (result[3] - result[1]), 0.0)
    inflation = result_area / source_area if source_area > 0.0 else math.inf
    return result, float(inflation)


def analyze_normalized_box(
    box: tuple[float, float, float, float],
    width: int,
    height: int,
    forward: np.ndarray,
) -> dict[str, Any]:
    """Return the GL-Q plain box plus validity, clipping, and inflation."""
    x0, y0, x1, y1 = box
    corners = np.array(
        (
            (x0 * (width - 1.0), y0 * (height - 1.0)),
            (x1 * (width - 1.0), y0 * (height - 1.0)),
            (x0 * (width - 1.0), y1 * (height - 1.0)),
            (x1 * (width - 1.0), y1 * (height - 1.0)),
        ),
        dtype=np.float64,
    )
    mapped = corners @ forward[:, :2].T + forward[:, 2]
    mapped[:, 0] /= max(width - 1.0, 1.0)
    mapped[:, 1] /= max(height - 1.0, 1.0)
    clipped = bool(np.any((mapped < 0.0) | (mapped > 1.0)))
    transformed_box, inflation = transform_normalized_box(box, width, height, forward)
    valid = transformed_box[2] > transformed_box[0] and transformed_box[3] > transformed_box[1]
    return {
        "box": list(transformed_box),
        "valid": bool(valid),
        "clipped": clipped,
        "area_ratio": inflation,
    }
