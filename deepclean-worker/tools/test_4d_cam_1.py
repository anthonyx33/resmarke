#!/usr/bin/env python3
"""Deterministic CPU-only build proofs for the sealed 4D-CAM-1 scalar."""

import copy
import json
import math
import subprocess
import sys
import tempfile
import types
from pathlib import Path

import numpy as np
from PIL import Image

TOOLS_DIR = Path(__file__).resolve().parent
WORKER_DIR = TOOLS_DIR.parent
sys.path.insert(0, str(TOOLS_DIR))
sys.path.insert(0, str(WORKER_DIR))

from camera_only_replay import existing_pair, fixed_rung_pair, pixel_sha256_image  # noqa: E402
from coherent_camera import apply_coherent_camera, normalize_coherent_camera_settings  # noqa: E402
from ds_remint_v8_8 import (  # noqa: E402
    _v88_candidate,
    apply_ds_remint_v8_8,
    normalize_ds_remint_v8_8_settings,
)
from tools.auxiliary_checkpoints import (  # noqa: E402
    AUXILIARY_CHECKPOINTS,
    build_auxiliary_manifest,
    save_auxiliary_checkpoint,
)
from tools.checkpoint_capture import (  # noqa: E402
    EXPECTED_CHECKPOINTS,
    build_checkpoint_manifest,
    pixel_sha256,
    save_checkpoint,
)


def test_worker_boundary_is_fail_closed():
    absent = normalize_ds_remint_v8_8_settings({"mode": "ds-remint-v8.9"})
    assert absent["optics_psf_scale"] == 1.0
    for allowed in (0.5, 1.0):
        cfg = normalize_ds_remint_v8_8_settings({
            "mode": "ds-remint-v8.9",
            "ds_remint_v8_9": {"optics_psf_scale": allowed},
        })
        assert cfg["optics_psf_scale"] == allowed
    for invalid in (0.49, 0.6, 0.75, float("nan"), float("inf"), "0.50", None, True):
        rejected = False
        try:
            normalize_ds_remint_v8_8_settings({
                "mode": "ds-remint-v8.9",
                "ds_remint_v8_9": {"optics_psf_scale": invalid},
            })
        except ValueError:
            rejected = True
        assert rejected, f"worker accepted invalid scale {invalid!r}"


def test_coherent_boundary_is_fail_closed():
    for allowed in (0.5, 1.0):
        cfg = normalize_coherent_camera_settings({
            "mode": "coherent-camera",
            "coherent_camera": {"strength": "light", "psf_scale": allowed},
        })
        assert cfg["psf_scale"] == allowed
    for invalid in (0.49, 0.6, 0.75, float("nan"), float("inf"), "0.50", None, False):
        rejected = False
        try:
            normalize_coherent_camera_settings({
                "mode": "coherent-camera",
                "coherent_camera": {"strength": "light", "psf_scale": invalid},
            })
        except ValueError:
            rejected = True
        assert rejected, f"camera accepted invalid scale {invalid!r}"


def test_absent_and_explicit_one_are_pixel_identical_and_half_is_live():
    source = nonconstant_fixture()
    common = {"mode": "coherent-camera", "coherent_camera": {"strength": "light"}}
    explicit = {
        "mode": "coherent-camera",
        "coherent_camera": {"strength": "light", "psf_scale": 1.0},
    }
    candidate = {
        "mode": "coherent-camera",
        "coherent_camera": {"strength": "light", "psf_scale": 0.5},
    }
    absent_image, absent_report = apply_coherent_camera(
        source, common, creator_id="cam-proof", seed_extra="lab:identity"
    )
    one_image, one_report = apply_coherent_camera(
        source, explicit, creator_id="cam-proof", seed_extra="lab:identity"
    )
    half_image, half_report = apply_coherent_camera(
        source, candidate, creator_id="cam-proof", seed_extra="lab:identity"
    )
    assert pixel_sha256_image(absent_image) == pixel_sha256_image(one_image)
    assert pixel_sha256_image(absent_image) != pixel_sha256_image(half_image)
    assert_reports_differ_only_in_scale(absent_report, half_report)
    assert sanitized_report(absent_report) == sanitized_report(one_report)


def test_scene_modulation_precedes_scale():
    source = checkerboard_fixture()
    _, report = apply_coherent_camera(
        source,
        {
            "mode": "coherent-camera",
            "coherent_camera": {"strength": "balanced", "psf_scale": 0.5},
        },
        creator_id="cam-proof",
        seed_extra="lab:scene-order",
    )
    optics = report["layers"]["optics"]
    assert report["layers"]["scene_analysis"]["edge_density"] > 0.08
    assert_close(optics["base_psf_g"], 0.32)
    assert_close(optics["base_psf_rb"], 0.40)
    assert_close(optics["scene_multiplier"], 0.92)
    assert_close(optics["effective_psf_g"], 0.1472)
    assert_close(optics["effective_psf_rb"], 0.1840)


def test_every_rung_and_both_deep_passes_receive_one_scalar():
    source = nonconstant_fixture()
    for rung in ("light", "balanced", "deep"):
        baseline_cfg = normalize_ds_remint_v8_8_settings({
            "mode": "ds-remint-v8.9",
            "ds_remint_v8_9": {"strength": rung},
        })
        candidate_cfg = normalize_ds_remint_v8_8_settings({
            "mode": "ds-remint-v8.9",
            "ds_remint_v8_9": {"strength": rung, "optics_psf_scale": 0.5},
        })
        _, baseline_layers = _v88_candidate(
            source, rung, baseline_cfg, "cam-proof", "lab:rungs", 0
        )
        _, layers = _v88_candidate(
            source, rung, candidate_cfg, "cam-proof", "lab:rungs", 0
        )
        assert sanitized_report(baseline_layers) == sanitized_report(layers)
        if rung == "deep":
            low = layers["deep_branch"]["low_res_clean"]["layers"]["optics"]
            final = layers["deep_branch"]["final_light_pass"]["layers"]["optics"]
            assert low["psf_scale"] == 0.5
            assert final["psf_scale"] == 0.5
            assert_close(low["base_psf_g"], 0.32)
            assert_close(final["base_psf_g"], 0.25)
        else:
            optics = layers["coherent_camera"]["report"]["layers"]["optics"]
            assert optics["psf_scale"] == 0.5


def test_absent_baseline_matches_b71ed99_for_every_rung():
    source = nonconstant_fixture()
    incumbent_camera = module_from_git(
        "b71ed99:deepclean-worker/coherent_camera.py", "incumbent_coherent_camera"
    )
    current_camera = sys.modules.get("coherent_camera")
    sys.modules["coherent_camera"] = incumbent_camera
    try:
        incumbent_ds = module_from_git(
            "b71ed99:deepclean-worker/ds_remint_v8_8.py", "incumbent_ds_remint_v8_8"
        )
    finally:
        if current_camera is None:
            sys.modules.pop("coherent_camera", None)
        else:
            sys.modules["coherent_camera"] = current_camera

    for rung in ("light", "balanced", "deep"):
        incumbent_cfg = incumbent_ds.normalize_ds_remint_v8_8_settings({
            "mode": "ds-remint-v8.9",
            "ds_remint_v8_9": {"strength": rung},
        })
        current_cfg = normalize_ds_remint_v8_8_settings({
            "mode": "ds-remint-v8.9",
            "ds_remint_v8_9": {"strength": rung},
        })
        incumbent, _ = incumbent_ds._v88_candidate(
            source, rung, incumbent_cfg, "cam-proof", "lab:incumbent", 0
        )
        current, _ = _v88_candidate(
            source, rung, current_cfg, "cam-proof", "lab:incumbent", 0
        )
        assert pixel_sha256_image(incumbent) == pixel_sha256_image(current), rung


def test_auxiliary_contract_is_independent_of_main_whitelist():
    assert AUXILIARY_CHECKPOINTS == ("OR_postresample.png",)
    with tempfile.TemporaryDirectory(prefix="cam1-aux-") as base:
        directory = Path(base)
        for index, name in enumerate(EXPECTED_CHECKPOINTS):
            assert save_checkpoint(directory, name, solid_image(index * 20)) is None
        main_before = build_checkpoint_manifest(directory, capture_requested=True)
        assert main_before["status"] == "captured"
        missing_aux = build_auxiliary_manifest(directory, capture_requested=True)
        assert missing_aux["status"] == "error"
        assert build_checkpoint_manifest(directory, capture_requested=True) == main_before
        assert save_auxiliary_checkpoint(directory, "O7_forbidden.png", solid_image(1)) is not None
        assert not (directory / "O7_forbidden.png").exists()
        assert save_auxiliary_checkpoint(directory, "OR_postresample.png", solid_image(77)) is None
        auxiliary = build_auxiliary_manifest(directory, capture_requested=True)
        assert auxiliary["status"] == "captured"
        assert auxiliary["errors"] == []
        assert auxiliary["files"][0]["sha256"] == pixel_sha256(directory / "OR_postresample.png")
        assert build_checkpoint_manifest(directory, capture_requested=True) == main_before


def test_ds_path_captures_or_without_main_checkpoint_errors():
    with tempfile.TemporaryDirectory(prefix="cam1-ds-") as base:
        directory = Path(base)
        input_path = directory / "input.png"
        output_path = directory / "output.jpg"
        source = nonconstant_fixture()
        source.save(input_path, format="PNG")
        report = apply_ds_remint_v8_8(
            input_path=str(input_path),
            output_path=str(output_path),
            creator_id="cam-proof",
            settings={
                "mode": "ds-remint-v8.9",
                "ds_remint_v8_9": {
                    "engine_mode": "template",
                    "pre_regen": False,
                    "strength": "light",
                    "color_restore": False,
                    "iphone_exif": False,
                    "metadata_mode": "minimal",
                    "optics_psf_scale": 0.5,
                },
            },
            seed_extra="lab:or-capture",
            checkpoint_dir=directory,
        )
        assert report["checkpoint_errors"] == []
        assert report["auxiliary_checkpoints"]["status"] == "captured"
        assert (directory / "OR_postresample.png").is_file()
        assert report["auxiliary_checkpoints"]["files"][0]["sha256"] == pixel_sha256(
            directory / "OR_postresample.png"
        )


def test_fixed_rung_replay_produces_proof_hashes_and_metrics():
    result = fixed_rung_pair(
        nonconstant_fixture(), "balanced", "cam-proof", "lab:fixed-replay"
    )
    assert result["baseline"]["sha256"] != result["candidate"]["sha256"]
    assert result["baseline"]["metrics"]["loss"] >= 0.0
    assert result["candidate"]["metrics"]["loss"] >= 0.0
    assert result["baseline"]["layers"]["coherent_camera"]["report"]["layers"]["optics"][
        "psf_scale"
    ] == 1.0
    assert result["candidate"]["layers"]["coherent_camera"]["report"]["layers"]["optics"][
        "psf_scale"
    ] == 0.5
    with tempfile.TemporaryDirectory(prefix="cam1-existing-") as base:
        directory = Path(base)
        or_b = directory / "or-b.png"
        or_c = directory / "or-c.png"
        o2_b = directory / "o2-b.png"
        o2_c = directory / "o2-c.png"
        source = nonconstant_fixture()
        source.save(or_b, format="PNG")
        source.save(or_c, format="PNG")
        result["baseline"]["image"].save(o2_b, format="PNG")
        result["candidate"]["image"].save(o2_c, format="PNG")
        measured = existing_pair(or_b, or_c, o2_b, o2_c)
        assert measured["or_identical"] is True
        changed = np.asarray(source).copy()
        changed[0, 0, 0] ^= 1
        Image.fromarray(changed).save(or_c, format="PNG")
        rejected = False
        try:
            existing_pair(or_b, or_c, o2_b, o2_c)
        except ValueError:
            rejected = True
        assert rejected, "mismatched paired OR buffers were accepted"


def assert_reports_differ_only_in_scale(baseline, candidate):
    assert sanitized_report(baseline) == sanitized_report(candidate)


def sanitized_report(report):
    clean = copy.deepcopy(report)

    def walk(value):
        if isinstance(value, dict):
            value.pop("runtime_ms", None)
            for key in (
                "psf_scale",
                "effective_psf_g",
                "effective_psf_rb",
                "psf_g",
                "psf_rb",
            ):
                value.pop(key, None)
            for nested in value.values():
                walk(nested)
        elif isinstance(value, list):
            for nested in value:
                walk(nested)

    walk(clean)
    return clean


def nonconstant_fixture(size=96):
    y, x = np.mgrid[0:size, 0:size]
    pixels = np.stack(
        (
            np.mod(x * 5 + y * 3, 256),
            np.mod(x * 2 + y * 7, 256),
            np.mod(x * 11 + y, 256),
        ),
        axis=2,
    ).astype(np.uint8)
    pixels[20:76, 45:49] = (245, 245, 245)
    pixels[45:49, 20:76] = (12, 12, 12)
    return Image.fromarray(pixels, mode="RGB")


def checkerboard_fixture(size=96):
    y, x = np.mgrid[0:size, 0:size]
    pattern = ((x // 2 + y // 2) % 2 * 220 + 18).astype(np.uint8)
    return Image.fromarray(np.stack((pattern, np.roll(pattern, 1, 0), pattern), axis=2), mode="RGB")


def solid_image(value):
    return Image.fromarray(np.full((16, 16, 3), value, dtype=np.uint8), mode="RGB")


def assert_close(actual, expected, tolerance=1e-9):
    assert math.isclose(float(actual), float(expected), abs_tol=tolerance), (actual, expected)


def module_from_git(object_name, module_name):
    source = subprocess.check_output(
        ["git", "show", object_name],
        cwd=WORKER_DIR.parent,
        text=True,
    )
    module = types.ModuleType(module_name)
    module.__file__ = f"git:{object_name}"
    exec(compile(source, module.__file__, "exec"), module.__dict__)
    return module


def main():
    tests = [
        test_worker_boundary_is_fail_closed,
        test_coherent_boundary_is_fail_closed,
        test_absent_and_explicit_one_are_pixel_identical_and_half_is_live,
        test_scene_modulation_precedes_scale,
        test_every_rung_and_both_deep_passes_receive_one_scalar,
        test_absent_baseline_matches_b71ed99_for_every_rung,
        test_auxiliary_contract_is_independent_of_main_whitelist,
        test_ds_path_captures_or_without_main_checkpoint_errors,
        test_fixed_rung_replay_produces_proof_hashes_and_metrics,
    ]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
    proof_source = nonconstant_fixture()
    proof = fixed_rung_pair(proof_source, "light", "cam-proof", "lab:report-proof")
    explicit_cfg = normalize_ds_remint_v8_8_settings({
        "mode": "ds-remint-v8.9",
        "ds_remint_v8_9": {"strength": "light", "optics_psf_scale": 1.0},
    })
    explicit_one, _ = _v88_candidate(
        proof_source, "light", explicit_cfg, "cam-proof", "lab:report-proof", 0
    )
    incumbent_camera = module_from_git(
        "b71ed99:deepclean-worker/coherent_camera.py", "proof_incumbent_coherent_camera"
    )
    current_camera = sys.modules.get("coherent_camera")
    sys.modules["coherent_camera"] = incumbent_camera
    try:
        incumbent_ds = module_from_git(
            "b71ed99:deepclean-worker/ds_remint_v8_8.py", "proof_incumbent_ds_remint_v8_8"
        )
    finally:
        if current_camera is None:
            sys.modules.pop("coherent_camera", None)
        else:
            sys.modules["coherent_camera"] = current_camera
    incumbent_cfg = incumbent_ds.normalize_ds_remint_v8_8_settings({
        "mode": "ds-remint-v8.9",
        "ds_remint_v8_9": {"strength": "light"},
    })
    incumbent, _ = incumbent_ds._v88_candidate(
        proof_source, "light", incumbent_cfg, "cam-proof", "lab:report-proof", 0
    )
    print("PROOF " + json.dumps({
        "baseline_or_sha256": proof["or_sha256"],
        "candidate_or_sha256": proof["or_sha256"],
        "incumbent_b71ed99_o2_sha256": pixel_sha256_image(incumbent),
        "absent_scale_o2_sha256": proof["baseline"]["sha256"],
        "explicit_1_o2_sha256": pixel_sha256_image(explicit_one),
        "candidate_o2_sha256": proof["candidate"]["sha256"],
        "baseline_loss": proof["baseline"]["metrics"]["loss"],
        "candidate_loss": proof["candidate"]["metrics"]["loss"],
    }, sort_keys=True))
    print(f"PASS {len(tests)} deterministic 4D-CAM-1 tests")


if __name__ == "__main__":
    main()
