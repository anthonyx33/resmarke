"""Outer worker quality gate and private geometry-reference handoff."""

from __future__ import annotations

from typing import Any

import numpy as np
from PIL import Image


MIN_OUTPUT_DIMENSION = 256
MIN_OUTPUT_VARIANCE = 12.0
MIN_PSNR_DB = 18.0

LEGACY_REFERENCE_MODE = "legacy_unwarped_source_resized"
GEOMETRY_REFERENCE_MODE = "geometry_matched_pre_camera"
PRIVATE_GEOMETRY_REFERENCE_KEY = "_quality_reference_image"


def pop_quality_reference(engine_report: Any) -> tuple[Any, bool]:
    """Remove the private reference and report whether geometry requires it.

    Geometry requirement is derived independently from the public engine
    settings.  A missing private field therefore reaches ``quality_check`` as
    a required-but-missing reference and fails closed instead of silently
    reverting to the legacy unwarped source.
    """
    if not isinstance(engine_report, dict):
        return None, False

    matched_reference = engine_report.pop(PRIVATE_GEOMETRY_REFERENCE_KEY, None)
    settings = engine_report.get("settings")
    geometry_required = (
        isinstance(settings, dict) and isinstance(settings.get("geometry"), dict)
    )
    return matched_reference, geometry_required


def _result(reference_mode: str, psnr: Any, variance: Any, **values: Any) -> dict[str, Any]:
    return {
        **values,
        "reference_mode": reference_mode,
        "psnr": psnr,
        "variance": variance,
        "min_psnr_db": MIN_PSNR_DB,
    }


def quality_check(
    input_path: Any,
    output_path: Any,
    *,
    matched_reference: Any = None,
    geometry_reference_required: bool = False,
) -> dict[str, Any]:
    """Apply the frozen dimension, variance and 18 dB outer quality gates.

    Non-geometry callers retain the incumbent source-resized comparison.
    Geometry callers must provide the exact post-resize/post-affine,
    pre-camera PIL image captured by the engine; it is never reconstructed or
    geometrically resampled here.
    """
    reference_mode = (
        GEOMETRY_REFERENCE_MODE
        if geometry_reference_required
        else LEGACY_REFERENCE_MODE
    )

    with Image.open(output_path) as opened_output:
        output = opened_output.convert("RGB")
    output_arr = np.asarray(output).astype(np.float32)
    variance = float(np.var(output_arr))

    if output.width < MIN_OUTPUT_DIMENSION or output.height < MIN_OUTPUT_DIMENSION:
        return _result(
            reference_mode,
            None,
            variance,
            ok=False,
            reason="Output image is too small.",
        )

    if geometry_reference_required:
        if not isinstance(matched_reference, Image.Image):
            return _result(
                reference_mode,
                None,
                variance,
                ok=False,
                reason="Geometry-matched quality reference is missing or malformed.",
            )
        if matched_reference.size != output.size:
            return _result(
                reference_mode,
                None,
                variance,
                ok=False,
                reason="Geometry-matched quality reference dimensions do not match output.",
            )
        reference = (
            matched_reference
            if matched_reference.mode == "RGB"
            else matched_reference.convert("RGB")
        )
    else:
        with Image.open(input_path) as opened_source:
            source = opened_source.convert("RGB")
        reference = source.resize(output.size, Image.Resampling.LANCZOS)

    reference_arr = np.asarray(reference).astype(np.float32)
    mse = float(np.mean((reference_arr - output_arr) ** 2))
    psnr = 99.0 if mse == 0 else float(20 * np.log10(255.0 / np.sqrt(mse)))

    if variance < MIN_OUTPUT_VARIANCE:
        return _result(
            reference_mode,
            psnr,
            variance,
            ok=False,
            reason="Output appears blank.",
        )
    if psnr < MIN_PSNR_DB:
        return _result(
            reference_mode,
            psnr,
            variance,
            ok=False,
            reason="Output drift exceeded quality gate.",
        )
    return _result(reference_mode, psnr, variance, ok=True)
