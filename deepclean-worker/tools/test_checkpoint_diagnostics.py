#!/usr/bin/env python3
"""Deterministic, CPU-only contract tests for diagnostics and checkpoints."""

import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image

TOOLS_DIR = Path(__file__).resolve().parent
WORKER_DIR = TOOLS_DIR.parent
sys.path.insert(0, str(TOOLS_DIR))
sys.path.insert(0, str(WORKER_DIR))

from checkpoint_attribution import _metrics_for, _spatial_correlations  # noqa: E402
from tools.checkpoint_capture import (  # noqa: E402
    EXPECTED_CHECKPOINTS,
    build_checkpoint_manifest,
    compare_o2_determinism,
    lab_checkpoint_dir,
    save_checkpoint,
)


def test_directional_spatial_correlation():
    size = 96
    axis = np.arange(size, dtype=np.float64)
    smooth_sequence = np.sin(axis * 0.11) + 0.35 * np.sin(axis * 0.037 + 0.4)
    row_offsets = np.sin(np.arange(size, dtype=np.float64) * 2.31)[:, None] * 0.03
    horizontal = np.tile(smooth_sequence, (size, 1)) + row_offsets
    vertical = horizontal.T
    mask = np.ones((size, size), dtype=bool)

    horizontal_metrics = _spatial_correlations(horizontal, mask)
    vertical_metrics = _spatial_correlations(vertical, mask)
    assert horizontal_metrics["rho1_h"] > 0.95
    assert horizontal_metrics["rho1_h"] > horizontal_metrics["rho2_h"]
    assert vertical_metrics["rho1_v"] > 0.95
    assert vertical_metrics["rho1_v"] > vertical_metrics["rho2_v"]


def test_iid_like_field_is_near_zero():
    indices = np.arange(128 * 128, dtype=np.float64).reshape(128, 128)
    # Fixed hash-like field: deterministic and independent-looking, no RNG.
    iid = np.mod(np.sin(indices * 12.9898 + 78.233) * 43758.5453, 1.0)
    metrics = _spatial_correlations(iid, np.ones_like(iid, dtype=bool))
    for key in ("rho1_h", "rho1_v", "rho2_h", "rho2_v"):
        assert abs(metrics[key]) < 0.05, (key, metrics[key])


def test_delta_e76_key_migration():
    height = width = 64
    x = np.linspace(0.1, 0.9, width, dtype=np.float64)
    reference = np.repeat(np.tile(x, (height, 1))[..., None], 3, axis=2)
    output = np.clip(reference + np.array([0.01, -0.005, 0.0]), 0.0, 1.0)
    metrics = _metrics_for(output, reference)
    assert "delta_e76" in metrics
    assert "delta_e00" not in metrics
    assert metrics["delta_e76"] > 0.0


def test_per_job_checkpoint_isolation():
    with tempfile.TemporaryDirectory(prefix="checkpoint-isolation-") as base:
        first = lab_checkpoint_dir(base, "job-a", "lab-pair1")
        second = lab_checkpoint_dir(base, "job-b", "lab-pair1")
        save_checkpoint(first, "O0_source.png", solid_image(10))
        save_checkpoint(second, "O0_source.png", solid_image(240))
        assert first != second
        assert (first / "O0_source.png").is_file()
        assert (second / "O0_source.png").is_file()
        first_pixel = np.asarray(Image.open(first / "O0_source.png"))[0, 0, 0]
        second_pixel = np.asarray(Image.open(second / "O0_source.png"))[0, 0, 0]
        assert int(first_pixel) == 10 and int(second_pixel) == 240


def test_manifest_completeness_requires_o5():
    with tempfile.TemporaryDirectory(prefix="checkpoint-manifest-") as base:
        directory = lab_checkpoint_dir(base, "job-manifest", "lab-pair2")
        for index, name in enumerate(EXPECTED_CHECKPOINTS[:-1]):
            assert save_checkpoint(directory, name, solid_image(index * 20)) is None
        missing = build_checkpoint_manifest(directory, capture_requested=True)
        assert missing["status"] == "error"
        assert any("missing checkpoint: O5_final.png" in error for error in missing["errors"])
        assert save_checkpoint(directory, "O5_final.png", solid_image(120)) is None
        complete = build_checkpoint_manifest(directory, capture_requested=True)
        assert complete["status"] == "captured"
        assert [item["name"] for item in complete["files"]] == list(EXPECTED_CHECKPOINTS)


def test_capture_gate_without_lab_seed_writes_nothing():
    with tempfile.TemporaryDirectory(prefix="checkpoint-gate-") as base:
        directory = lab_checkpoint_dir(base, "customer-job", None)
        assert directory is None
        assert save_checkpoint(directory, "O0_source.png", solid_image(1)) is None
        assert list(Path(base).iterdir()) == []
        assert build_checkpoint_manifest(directory, capture_requested=False) == {
            "status": "off",
            "files": [],
            "errors": [],
        }


def test_o2_exact_and_same_hardware_tolerance_rules():
    with tempfile.TemporaryDirectory(prefix="checkpoint-o2-") as base:
        first = Path(base) / "first.png"
        exact = Path(base) / "exact.png"
        tolerated = Path(base) / "tolerated.png"
        failed = Path(base) / "failed.png"
        pixels = np.full((16, 16, 3), 120, dtype=np.uint8)
        Image.fromarray(pixels).save(first)
        Image.fromarray(pixels.copy()).save(exact)
        close = pixels.copy()
        close[0, 0, 0] += 1
        Image.fromarray(close).save(tolerated)
        far = pixels.copy()
        far[:, :, 0] += 1
        Image.fromarray(far).save(failed)
        assert compare_o2_determinism(first, exact)["kind"] == "exact"
        assert compare_o2_determinism(first, tolerated)["kind"] == "tolerated"
        assert compare_o2_determinism(first, failed)["kind"] == "failed"
        assert compare_o2_determinism(first, tolerated, same_hardware=False)["kind"] == "failed"


def solid_image(value):
    return Image.fromarray(np.full((12, 12, 3), value, dtype=np.uint8))


def main():
    tests = [
        test_directional_spatial_correlation,
        test_iid_like_field_is_near_zero,
        test_delta_e76_key_migration,
        test_per_job_checkpoint_isolation,
        test_manifest_completeness_requires_o5,
        test_capture_gate_without_lab_seed_writes_nothing,
        test_o2_exact_and_same_hardware_tolerance_rules,
    ]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
    print(f"PASS {len(tests)} deterministic diagnostic/checkpoint tests")


if __name__ == "__main__":
    main()
