#!/usr/bin/env python3
"""CPU-only build proofs for the sealed 4D-1a source-energy transfer."""

import copy
import hashlib
import json
import subprocess
import sys
import tempfile
import types
from pathlib import Path

import numpy as np
from PIL import Image


TOOLS_DIR = Path(__file__).resolve().parent
WORKER_DIR = TOOLS_DIR.parent
ROOT = WORKER_DIR.parent
sys.path.insert(0, str(TOOLS_DIR))
sys.path.insert(0, str(WORKER_DIR))

import checkpoint_attribution as frozen_attribution  # noqa: E402
from ds_remint_v8_8 import apply_ds_remint_v8_9, normalize_ds_remint_v8_8_settings  # noqa: E402
from tools.auxiliary_checkpoints import (  # noqa: E402
    AUXILIARY_CHECKPOINT_WHITELIST,
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
from transfer_4d_1a import (  # noqa: E402
    CAP_RELATIVE_TOLERANCE,
    _band_support,
    _edge_mag,
    _initial_gain,
    _reject_counts,
    _smooth_weight,
    _synthesize_rgb,
    _transfer_band,
    _verify_caps,
    apply_transfer_4d_1a,
    finalize_transfer_report,
    pixel_sha256_array,
)


def test_worker_flag_boundary_is_strict_and_fail_closed():
    absent = normalize_ds_remint_v8_8_settings({"mode": "ds-remint-v8.9"})
    assert absent["4d1a"] is False and absent["4d1a_supplied"] is False
    explicit_false = normalize_ds_remint_v8_8_settings({
        "mode": "ds-remint-v8.9",
        "ds_remint_v8_9": {"4d1a": False},
    })
    assert explicit_false["4d1a"] is False and explicit_false["4d1a_supplied"] is True
    for seed in ("lab-ctla1", "lab-ctla2"):
        enabled = normalize_ds_remint_v8_8_settings({
            "mode": "ds-remint-v8.9",
            "ds_remint_v8_9": {"4d1a": True, "seed": seed},
        })
        assert enabled["4d1a"] is True and enabled["lab_seed"] == seed
    invalid_subs = [
        {"4d1a": None},
        {"4d1a": 0},
        {"4d1a": 1},
        {"4d1a": "true"},
        {"4d1a": True},
        {"4d1a": True, "seed": "lab-other"},
        {"4d1a": True, "seed": "lab-ctla1", "optics_psf_scale": 0.5},
        {"4d1a": False, "unknown_transfer_key": True},
    ]
    for sub in invalid_subs:
        expect_value_error(lambda sub=sub: normalize_ds_remint_v8_8_settings({
            "mode": "ds-remint-v8.9", "ds_remint_v8_9": sub,
        }))
    expect_value_error(lambda: normalize_ds_remint_v8_8_settings({
        "mode": "ds-remint-v8.8",
        "ds_remint_v8_8": {"4d1a": True, "seed": "lab-ctla1"},
    }))


def test_absent_and_false_match_head_incumbent_bytes_and_report():
    source = contrast_fixture()
    incumbent = module_from_git("HEAD:deepclean-worker/ds_remint_v8_8.py", "incumbent_ds_4d1a")
    with tempfile.TemporaryDirectory(prefix="4d1a-off-") as base:
        directory = Path(base)
        input_path = directory / "input.png"
        source.save(input_path, format="PNG")
        for label, seed in (("nonlab", None), ("lab", "lab-ctla1")):
            common = base_settings(seed=seed)
            absent_path = directory / f"{label}-absent.jpg"
            false_path = directory / f"{label}-false.jpg"
            incumbent_path = directory / f"{label}-incumbent.jpg"
            absent_report = apply_ds_remint_v8_9(
                input_path, absent_path, "4d1a-proof", common,
                seed_extra="lab:lab-ctla1", lab_seed=seed,
            )
            false_settings = copy.deepcopy(common)
            false_settings["ds_remint_v8_9"]["4d1a"] = False
            false_report = apply_ds_remint_v8_9(
                input_path, false_path, "4d1a-proof", false_settings,
                seed_extra="lab:lab-ctla1", lab_seed=seed,
            )
            incumbent_report = incumbent.apply_ds_remint_v8_9(
                input_path, incumbent_path, "4d1a-proof", common,
                seed_extra="lab:lab-ctla1",
            )
            assert sha256_file(absent_path) == sha256_file(false_path) == sha256_file(incumbent_path)
            assert sanitized_report(absent_report) == sanitized_report(false_report)
            assert sanitized_report(absent_report) == sanitized_report(incumbent_report)
            assert "transfer_4d_1a" not in absent_report and "transfer_4d_1a" not in false_report


def test_o2_identity_auxiliary_isolation_on_divergence_and_post_o5_report():
    source = contrast_fixture()
    with tempfile.TemporaryDirectory(prefix="4d1a-pair-") as base:
        directory = Path(base)
        input_path = directory / "input.png"
        source.save(input_path, format="PNG")
        baseline_dir = directory / "B"
        candidate_dir = directory / "C"
        baseline_path = directory / "B.jpg"
        candidate_path = directory / "C.jpg"
        baseline_settings = base_settings(seed="lab-ctla1")
        candidate_settings = base_settings(seed="lab-ctla1", transfer=True)
        baseline_report = apply_ds_remint_v8_9(
            input_path, baseline_path, "4d1a-proof", baseline_settings,
            seed_extra="lab:lab-ctla1", checkpoint_dir=baseline_dir,
            lab_seed="lab-ctla1",
        )
        candidate_report = apply_ds_remint_v8_9(
            input_path, candidate_path, "4d1a-proof", candidate_settings,
            seed_extra="lab:lab-ctla1", checkpoint_dir=candidate_dir,
            lab_seed="lab-ctla1",
        )
        assert pixel_sha256(baseline_dir / "O2_precamera.png") == pixel_sha256(candidate_dir / "O2_precamera.png")
        assert not (baseline_dir / "O2_transfer.png").exists()
        assert (candidate_dir / "O2_transfer.png").is_file()
        assert pixel_sha256(candidate_dir / "O2_transfer.png") != pixel_sha256(candidate_dir / "O2_precamera.png")
        assert sha256_file(baseline_path) != sha256_file(candidate_path)
        assert baseline_report["auxiliary_checkpoints"]["files"] == [
            {"name": "OR_postresample.png", "sha256": pixel_sha256(baseline_dir / "OR_postresample.png")}
        ]
        assert [item["name"] for item in candidate_report["auxiliary_checkpoints"]["files"]] == [
            "OR_postresample.png", "O2_transfer.png"
        ]
        transfer = candidate_report["transfer_4d_1a"]
        assert transfer["input_pixel_hashes"]["o2_pre_transfer_pixels_sha256"] == pixel_sha256(
            candidate_dir / "O2_precamera.png"
        )
        assert transfer["input_pixel_hashes"]["r2_pixels_sha256"] == pixel_sha256_array(
            np.asarray(source, dtype=np.uint8)
        )
        with Image.open(candidate_path) as o5:
            finalize_transfer_report(transfer, o5)
        assert transfer["finalized_post_o5"] is True
        assert set(transfer["diagnostic_losses"]) == {
            "pre_transfer_o2_to_o5", "o2_transfer_to_o5"
        }
        assert "_diagnostic_context" not in transfer


def test_same_machine_determinism_for_all_candidate_artifacts():
    source = contrast_fixture()
    records = []
    with tempfile.TemporaryDirectory(prefix="4d1a-determinism-") as base:
        base_path = Path(base)
        input_path = base_path / "input.png"
        source.save(input_path, format="PNG")
        for index in range(2):
            checkpoint_dir = base_path / f"run-{index}"
            output_path = base_path / f"run-{index}.jpg"
            report = apply_ds_remint_v8_9(
                input_path, output_path, "4d1a-proof",
                base_settings(seed="lab-ctla2", transfer=True),
                seed_extra="lab:lab-ctla2", checkpoint_dir=checkpoint_dir,
                lab_seed="lab-ctla2",
            )
            transfer = report["transfer_4d_1a"]
            with Image.open(output_path) as o5:
                finalize_transfer_report(transfer, o5)
            records.append({
                "o2": pixel_sha256(checkpoint_dir / "O2_precamera.png"),
                "r2": transfer["input_pixel_hashes"]["r2_pixels_sha256"],
                "transfer": pixel_sha256(checkpoint_dir / "O2_transfer.png"),
                "o5": pixel_sha256_array(np.asarray(Image.open(output_path).convert("RGB"))),
                "report": json.dumps(transfer, sort_keys=True, separators=(",", ":")),
            })
    assert records[0] == records[1]
    return {
        "o2_input_pixels_sha256": records[0]["o2"],
        "r2_pixels_sha256": records[0]["r2"],
        "o2_transfer_pixels_sha256": records[0]["transfer"],
        "o5_pixels_sha256": records[0]["o5"],
        "report_sha256": hashlib.sha256(records[0]["report"].encode("utf-8")).hexdigest(),
    }


def test_frozen_edge_recipe_and_complete_support_remasking():
    y, x = np.mgrid[:47, :53]
    field = np.sin(x * 0.17) + 0.3 * np.cos(y * 0.23) + np.mod(x * 7 + y * 3, 11) * 0.01
    assert np.array_equal(_edge_mag(field), frozen_attribution._edge_mag(field))
    support = np.zeros(field.shape, dtype=bool)
    support[10:36, 12:41] = True
    raw = np.zeros(field.shape, dtype=np.float64)
    raw[18:28, 20:33] = 1.0
    weight = _smooth_weight(raw, support)
    assert not np.any(weight[~support] > 0.0)
    assert np.any(weight[support] > 0.0)


def test_energy_equation_noops_phase_and_numeric_failures():
    shape = (31, 37)
    weight = np.ones(shape, dtype=np.float64)
    remint_energy = np.full(shape, 0.04, dtype=np.float64)
    assert np.array_equal(_initial_gain(remint_energy * 0.5, remint_energy, weight, 0.1), np.ones(shape))
    # Equal-energy source phase is never an input to the gain equation.
    phase_a = np.sin(np.arange(shape[1]) * 0.4)[None, :]
    phase_b = np.cos(np.arange(shape[1]) * 0.4)[None, :]
    energy = np.broadcast_to(np.mean(phase_a * phase_a), shape)
    gain_a = _initial_gain(energy, energy, weight, 0.1)
    gain_b = _initial_gain(energy, energy, weight, 0.1)
    assert np.array_equal(gain_a, gain_b) and np.array_equal(gain_a, np.ones(shape))
    bad_source = remint_energy * 2.0
    bad_source[0, 0] = np.nan
    zero_denominator = remint_energy.copy()
    zero_denominator[0, 1] = 0.0
    gain = _initial_gain(bad_source, zero_denominator, weight, 0.1)
    assert gain[0, 0] == 1.0 and gain[0, 1] == 1.0
    assert np.all(np.isfinite(gain)) and float(np.min(gain)) >= 1.0 and float(np.max(gain)) <= 1.1


def test_window_cap_gain_floor_and_one_nanosecond_relative_fail_closed():
    y, x = np.mgrid[:64, :64]
    remint = 0.025 * np.sin(x * 0.31) + 0.018 * np.cos(y * 0.27)
    source = remint * 1.8
    result = _transfer_band(remint, source, np.ones_like(remint), 0.1)
    assert result["cap"]["passed"] is True
    assert float(np.min(result["gain"])) >= 1.0
    assert float(np.max(result["gain"])) <= 1.1
    target = np.ones((3, 4), dtype=np.float64)
    valid = np.ones_like(target, dtype=bool)
    safe = _verify_caps(target * (1.0 + CAP_RELATIVE_TOLERANCE * 0.5), target, valid)
    breach = _verify_caps(target * (1.0 + CAP_RELATIVE_TOLERANCE * 2.0), target, valid)
    assert safe["passed"] is True and breach["passed"] is False


def test_channel_differences_preserved_and_capped_fraction_truthful():
    y, x = np.mgrid[:43, :47]
    rgb_u8 = np.stack((70 + (x % 20), 100 + (y % 20), 130 + ((x + y) % 20)), axis=2).astype(np.uint8)
    rgb = rgb_u8.astype(np.float64) / 255.0
    delta = np.full(rgb.shape[:2], 0.03, dtype=np.float64)
    output, fraction = _synthesize_rgb(rgb, delta)
    assert fraction == 0.0
    assert np.array_equal(output[..., 0].astype(np.int16) - output[..., 1].astype(np.int16),
                          rgb_u8[..., 0].astype(np.int16) - rgb_u8[..., 1].astype(np.int16))
    assert np.array_equal(output[..., 1].astype(np.int16) - output[..., 2].astype(np.int16),
                          rgb_u8[..., 1].astype(np.int16) - rgb_u8[..., 2].astype(np.int16))
    mixed = delta.copy()
    mixed[:10, :11] = 1.0
    capped_output, capped_fraction = _synthesize_rgb(rgb, mixed)
    expected = (10 * 11) / float(mixed.size)
    assert abs(capped_fraction - expected) < 1e-15
    assert np.array_equal(
        capped_output[..., 0].astype(np.int16) - capped_output[..., 1].astype(np.int16),
        rgb_u8[..., 0].astype(np.int16) - rgb_u8[..., 1].astype(np.int16),
    )
    assert np.array_equal(
        capped_output[..., 1].astype(np.int16) - capped_output[..., 2].astype(np.int16),
        rgb_u8[..., 1].astype(np.int16) - rgb_u8[..., 2].astype(np.int16),
    )


def test_support_gates_reject_independently_and_counts_are_truthful():
    y, x = np.mgrid[:64, :64]
    good = 0.03 * np.sin(x * 0.37) + 0.025 * np.cos(y * 0.29) + 0.01 * np.sin((x + y) * 0.19)
    zeros = np.zeros_like(good)
    details_good = _band_support(good, good * 1.1, zeros, 1e-6)
    core = np.s_[10:-10, 10:-10]
    for gate in ("scale", "residual", "orientation", "ncc", "snr"):
        assert np.any(details_good["gates"][gate][core]), gate

    bad_scale = _band_support(good, good, np.ones_like(good), 1e-6)
    assert not np.any(bad_scale["gates"]["scale"])
    bad_residual = _band_support(good, np.roll(good, 3, axis=1), zeros, 1e-6)
    assert np.any(~bad_residual["gates"]["residual"][core])
    horizontal = 0.04 * np.sin(x * 0.4)
    vertical = 0.04 * np.sin(y * 0.4)
    bad_orientation = _band_support(horizontal, vertical, zeros, 1e-6)
    assert np.any(~bad_orientation["gates"]["orientation"][core])
    bad_polarity = _band_support(good, -good, zeros, 1e-6)
    assert np.all(~bad_polarity["gates"]["ncc"][core])
    bad_snr = _band_support(good * 1e-3, good * 1e-3, zeros, 1e-6)
    assert np.all(~bad_snr["gates"]["snr"][core])

    h1 = details_good
    h2 = bad_snr
    cross = h1["numeric_support"] & h2["numeric_support"]
    assert not np.any(cross[core])
    edge = np.zeros_like(cross)
    edge[0:7, :] = True
    complete = cross & ~edge
    counts = _reject_counts({"H1": h1, "H2": h2}, cross, edge, complete)
    total = good.size
    for name, details in (("H1", h1), ("H2", h2)):
        for gate in ("scale", "residual", "orientation", "ncc", "snr"):
            assert counts[name][gate] == total - int(np.count_nonzero(details["gates"][gate]))
    assert counts["cross_scale"] == total - int(np.count_nonzero(cross))
    assert counts["strong_edge_exclusion"] == int(np.count_nonzero(edge))


def test_flat_near_flat_borders_alpha_zero_and_full_fail_closed_are_identity():
    fixtures = [
        Image.fromarray(np.full((33, 29, 3), 127, dtype=np.uint8), mode="RGB"),
        Image.fromarray(np.full((9, 11, 3), 127, dtype=np.uint8), mode="RGB"),
        Image.fromarray(np.full((1, 1, 3), 127, dtype=np.uint8), mode="RGB"),
        Image.fromarray(np.full((7, 1, 3), 127, dtype=np.uint8), mode="RGB"),
    ]
    near = np.full((35, 37, 3), 127, dtype=np.uint8)
    near[17, 18] = (128, 127, 127)
    fixtures.append(Image.fromarray(near, mode="RGB"))
    for image in fixtures:
        output, _ = apply_transfer_4d_1a(image, image)
        alpha_zero, _ = apply_transfer_4d_1a(image, contrast_fixture(image.size[0], image.size[1]), alpha=0)
        assert np.array_equal(np.asarray(output), np.asarray(image))
        assert np.array_equal(np.asarray(alpha_zero), np.asarray(image))

    source = blur_fail_fixture()
    # The blur fixture deterministically exercises the single-pass cap's
    # fail-closed path; no candidate pixels escape when final verification fails.
    from PIL import ImageFilter
    remint = source.filter(ImageFilter.GaussianBlur(0.8))
    output, report = apply_transfer_4d_1a(remint, source)
    assert report["fail_closed_reason"] == "window_energy_cap_verification"
    assert np.array_equal(np.asarray(output), np.asarray(remint))


def test_phase_zero_crossing_and_confidence_boundary_fixtures():
    yy, xx = np.mgrid[:81, :81]
    slanted_coordinate = xx - yy
    slanted_band = slanted_coordinate * np.exp(-(slanted_coordinate ** 2) / 18.0)
    slanted_gain = _initial_gain(
        np.full(slanted_band.shape, 4.0),
        np.ones(slanted_band.shape),
        np.ones(slanted_band.shape),
        0.1,
    )
    slanted_corrected = slanted_gain * slanted_band
    assert np.array_equal(slanted_corrected == 0.0, slanted_band == 0.0)
    assert np.array_equal(np.signbit(slanted_corrected), np.signbit(slanted_band))
    for row in range(8, 73):
        assert local_extrema(slanted_corrected[row]) == local_extrema(slanted_band[row])

    x = np.linspace(-2.0 * np.pi, 2.0 * np.pi, 257, dtype=np.float64)
    remint = np.sin(x)
    source_energy = np.full(remint.shape, 4.0)
    remint_energy = np.ones(remint.shape)
    support = np.ones(remint.shape)
    gain = _initial_gain(source_energy, remint_energy, support, 0.1)
    corrected = gain * remint
    assert np.array_equal(np.where(remint == 0.0)[0], np.where(corrected == 0.0)[0])
    assert np.array_equal(np.signbit(remint), np.signbit(corrected))

    # Put confidence boundaries on coefficient zero crossings.  The positive
    # gain cannot create a shoulder or a new local extremum at either boundary.
    masked_support = np.zeros(remint.shape)
    masked_support[64:193] = 1.0
    boundary_gain = _initial_gain(source_energy, remint_energy, masked_support, 0.1)
    boundary = boundary_gain * remint
    assert local_extrema(boundary) == local_extrema(remint)


def test_auxiliary_whitelist_gains_exactly_one_name_and_main_manifest_is_unchanged():
    assert AUXILIARY_CHECKPOINTS == ("OR_postresample.png",)
    assert AUXILIARY_CHECKPOINT_WHITELIST == ("OR_postresample.png", "O2_transfer.png")
    assert EXPECTED_CHECKPOINTS == (
        "O0_source.png", "O1_postwash.png", "O2_precamera.png",
        "O3_stage1.png", "O4_preencode.png", "O5_final.png",
    )
    with tempfile.TemporaryDirectory(prefix="4d1a-aux-") as base:
        directory = Path(base)
        for index, name in enumerate(EXPECTED_CHECKPOINTS):
            assert save_checkpoint(directory, name, solid_image(index * 30)) is None
        before = build_checkpoint_manifest(directory, capture_requested=True)
        o5_before = pixel_sha256(directory / "O5_final.png")
        assert save_auxiliary_checkpoint(directory, "OR_postresample.png", solid_image(31)) is None
        assert save_auxiliary_checkpoint(directory, "O2_transfer.png", solid_image(63)) is None
        assert save_auxiliary_checkpoint(directory, "O2_transfer.jpg", solid_image(95)) is not None
        auxiliary = build_auxiliary_manifest(directory, capture_requested=True, include_transfer=True)
        assert auxiliary["status"] == "captured"
        assert [item["name"] for item in auxiliary["files"]] == list(AUXILIARY_CHECKPOINT_WHITELIST)
        assert build_checkpoint_manifest(directory, capture_requested=True) == before
        assert pixel_sha256(directory / "O5_final.png") == o5_before


def test_protected_files_are_zero_diff():
    protected = [
        "deepclean-worker/coherent_camera.py",
        "deepclean-worker/tools/checkpoint_attribution.py",
        "deepclean-worker/tools/camera_only_replay.py",
        "deepclean-worker/tools/checkpoint_capture.py",
        "deepclean-worker/quality_finish.py",
    ]
    changed = subprocess.check_output(
        ["git", "diff", "--name-only", "--", *protected], cwd=ROOT, text=True
    ).splitlines()
    assert changed == []


def base_settings(seed=None, transfer=False):
    sub = {
        "engine_mode": "template",
        "pre_regen": False,
        "strength": "balanced",
        "color_restore": False,
        "iphone_exif": False,
        "metadata_mode": "minimal",
    }
    if seed is not None:
        sub["seed"] = seed
    if transfer:
        sub["4d1a"] = True
    return {"mode": "ds-remint-v8.9", "ds_remint_v8_9": sub}


def contrast_fixture(width=96, height=None):
    height = height or width
    y, x = np.mgrid[:height, :width]
    active = x > max(4, int(width * 0.38))
    pattern = np.zeros((height, width), dtype=np.float64)
    pattern[active] = (np.sin(x[active] * 0.50) + 0.7 * np.cos(y[active] * 0.40)
                       + 0.35 * np.sin((x[active] + y[active]) * 0.275))
    base = 128.0 + 70.0 * pattern
    rgb = np.clip(np.stack((base + 8.0, base, base - 7.0), axis=2), 0, 255).astype(np.uint8)
    return Image.fromarray(rgb, mode="RGB")


def blur_fail_fixture(size=96):
    y, x = np.mgrid[:size, :size]
    base = np.full((size, size), 128.0)
    active = (x > 38) & (y > 12) & (y < 84)
    base[active] = (128.0 + 20.0 * np.sin(x[active] * 0.5)
                    + 16.0 * np.cos(y[active] * 0.42)
                    + 8.0 * np.sin((x[active] + y[active]) * 0.29))
    rgb = np.clip(np.stack((base + 8.0, base, base - 7.0), axis=2), 0, 255).astype(np.uint8)
    return Image.fromarray(rgb, mode="RGB")


def solid_image(value):
    return Image.fromarray(np.full((16, 16, 3), value, dtype=np.uint8), mode="RGB")


def sanitized_report(report):
    clean = copy.deepcopy(report)

    def walk(value):
        if isinstance(value, dict):
            value.pop("runtime_ms", None)
            for nested in value.values():
                walk(nested)
        elif isinstance(value, list):
            for nested in value:
                walk(nested)

    walk(clean)
    return clean


def local_extrema(values):
    values = np.asarray(values)
    return (
        tuple(np.where((values[1:-1] > values[:-2]) & (values[1:-1] > values[2:]))[0] + 1),
        tuple(np.where((values[1:-1] < values[:-2]) & (values[1:-1] < values[2:]))[0] + 1),
    )


def expect_value_error(operation):
    try:
        operation()
    except ValueError:
        return
    raise AssertionError("expected ValueError")


def sha256_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def module_from_git(object_name, module_name):
    source = subprocess.check_output(["git", "show", object_name], cwd=ROOT, text=True)
    module = types.ModuleType(module_name)
    module.__file__ = f"git:{object_name}"
    exec(compile(source, module.__file__, "exec"), module.__dict__)
    return module


def main():
    tests = [
        test_worker_flag_boundary_is_strict_and_fail_closed,
        test_absent_and_false_match_head_incumbent_bytes_and_report,
        test_o2_identity_auxiliary_isolation_on_divergence_and_post_o5_report,
        test_same_machine_determinism_for_all_candidate_artifacts,
        test_frozen_edge_recipe_and_complete_support_remasking,
        test_energy_equation_noops_phase_and_numeric_failures,
        test_window_cap_gain_floor_and_one_nanosecond_relative_fail_closed,
        test_channel_differences_preserved_and_capped_fraction_truthful,
        test_support_gates_reject_independently_and_counts_are_truthful,
        test_flat_near_flat_borders_alpha_zero_and_full_fail_closed_are_identity,
        test_phase_zero_crossing_and_confidence_boundary_fixtures,
        test_auxiliary_whitelist_gains_exactly_one_name_and_main_manifest_is_unchanged,
        test_protected_files_are_zero_diff,
    ]
    determinism_proof = None
    for test in tests:
        result = test()
        if test is test_same_machine_determinism_for_all_candidate_artifacts:
            determinism_proof = result
        print(f"PASS {test.__name__}")

    assert determinism_proof is not None
    print("DETERMINISM " + json.dumps(determinism_proof, sort_keys=True, separators=(",", ":")))

    source = contrast_fixture()
    remint_array = np.asarray(source, dtype=np.uint8).copy()
    remint_array[:, 39:] = np.rint(
        128.0 + (remint_array[:, 39:].astype(np.float64) - 128.0) * 0.56
    ).clip(0, 255).astype(np.uint8)
    remint = Image.fromarray(remint_array, mode="RGB")
    candidate, transfer_report = apply_transfer_4d_1a(remint, source)
    proof = {
        "baseline_o2_sha256": pixel_sha256_array(np.asarray(remint, dtype=np.uint8)),
        "candidate_pre_transfer_o2_sha256": transfer_report["input_pixel_hashes"]["o2_pre_transfer_pixels_sha256"],
        "r2_sha256": transfer_report["input_pixel_hashes"]["r2_pixels_sha256"],
        "candidate_o2_transfer_sha256": pixel_sha256_array(np.asarray(candidate, dtype=np.uint8)),
        "off_arm_bit_identity": pixel_sha256_array(np.asarray(remint, dtype=np.uint8)) == transfer_report["input_pixel_hashes"]["o2_pre_transfer_pixels_sha256"],
        "on_arm_diverged": not np.array_equal(np.asarray(candidate), np.asarray(remint)),
        "same_machine_noise_floor_rms_lsb": "0.000000000000",
    }
    print("PROOF " + json.dumps(proof, sort_keys=True, separators=(",", ":")))
    fixtures = {
        "alpha_zero_identity": "PASS",
        "bad_alignment_rejected": "PASS",
        "bad_orientation_rejected": "PASS",
        "channel_difference_preserved_and_cap_fraction_truthful": "PASS",
        "confidence_boundary_no_new_extrema": "PASS",
        "edge_mag_exact_np_gradient_equivalence": "PASS",
        "equal_energy_different_phase_noop": "PASS",
        "final_window_cap_fail_closed_at_1e-9_relative": "PASS",
        "flat_and_near_flat_unchanged": "PASS",
        "gain_floor_after_cap_enforcement": "PASS",
        "h1_only_cross_scale_support_rejected": "PASS",
        "image_borders_safe": "PASS",
        "nan_safe": "PASS",
        "no_weight_outside_complete_support": "PASS",
        "polarity_flip_rejected": "PASS",
        "reject_counts_truthful": "PASS",
        "remint_energy_at_or_above_source_noop": "PASS",
        "slanted_edge_zero_crossing_source_shoulder_absent": "PASS",
        "zero_energy_denominator_safe": "PASS",
    }
    print("FIXTURES " + json.dumps(fixtures, sort_keys=True, separators=(",", ":")))
    print(f"PASS {len(tests)} deterministic 4D-1a tests")


if __name__ == "__main__":
    main()
