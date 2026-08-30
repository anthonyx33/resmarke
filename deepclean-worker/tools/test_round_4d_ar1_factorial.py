#!/usr/bin/env python3
"""4D-AR1 factorial contracts; only temporary synthetic images are written."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import numpy as np
from PIL import Image

TOOLS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS_DIR))

import round_4d_ar1_factorial as ar1


class FrozenPreflightTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.environment, _ = ar1.verify_environment(capture_freeze=False)
        cls.manifest, cls.settings, cls.roi, cls.cells, cls.checks = ar1.verify_inputs()

    def test_exact_environment_is_active(self):
        self.assertTrue(self.environment["environment_prefix_pass"])
        self.assertTrue(self.environment["python_pass"])
        self.assertTrue(self.environment["numpy_pass"])
        self.assertTrue(self.environment["pillow_pass"])

    def test_environment_freeze_comes_from_verify3(self):
        _, freeze = ar1.verify_environment(capture_freeze=True)
        self.assertEqual(
            set(freeze.splitlines()),
            {"numpy==2.0.2", "piexif==1.1.3", "pillow==11.3.0"},
        )

    def test_all_frozen_input_checks_pass(self):
        self.assertEqual(len(self.manifest["cells"]), 24)
        self.assertEqual(len(self.cells), 12)
        self.assertEqual(len(self.checks), 291)
        self.assertTrue(all(row["pass"] for row in self.checks))

    def test_two_seed_six_image_cohort_is_exact(self):
        actual = {(cell["image"], cell["seed"]) for cell in self.cells}
        expected = {(image, seed) for image in ar1.SIX_IMAGES for seed in ar1.SEEDS}
        self.assertEqual(actual, expected)

    def test_every_cell_has_the_frozen_executed_contract(self):
        for cell in self.cells:
            block = self.settings["jobs"][cell["job"]]
            executed = block["executed"]
            self.assertEqual(executed["effective_seed"], f"lab:{cell['seed']}")
            self.assertEqual(executed["output_mode"], "stripped")
            self.assertEqual(executed["finish_preset_selected"], "strong")
            self.assertEqual(executed["finish"]["scale"], 1)
            self.assertEqual(
                executed["finish"]["overrides"],
                {"dither": 1, "sharpen": 1, "smoothness": 1.25},
            )


class ArmTableTests(unittest.TestCase):
    def test_exactly_A0_through_A6_are_commissioned(self):
        self.assertEqual([arm.name for arm in ar1.ARMS], [f"A{index}" for index in range(7)])
        self.assertNotIn("A7", {arm.name for arm in ar1.ARMS})

    def test_frozen_factor_matrix(self):
        actual = {
            arm.name: (arm.camera, arm.intermediate_jpeg, arm.quality_finish, arm.preservation)
            for arm in ar1.ARMS
        }
        self.assertEqual(
            actual,
            {
                "A0": (True, True, True, False),
                "A1": (False, True, True, False),
                "A2": (True, False, True, False),
                "A3": (False, False, True, False),
                "A4": (True, True, True, True),
                "A5": (True, True, False, False),
                "A6": (False, True, False, False),
            },
        )

    def test_frozen_scalar_and_encode_constants(self):
        self.assertEqual(ar1.TONE_LOCK_STRENGTH, 0.8)
        self.assertEqual((ar1.STAGE1_QUALITY, ar1.STAGE1_SUBSAMPLING), (92, "4:2:0"))
        self.assertEqual((ar1.FINAL_QUALITY, ar1.FINAL_SUBSAMPLING), (97, "4:4:4"))
        self.assertEqual(ar1._qf_settings()["quality_finish"], {
            "preset": "strong",
            "scale": 1,
            "overrides": {"dither": 1, "sharpen": 1, "smoothness": 1.25},
            "material_clean": True,
            "finish_mode": "fixed-executed-replay",
        })

    def test_harness_defines_no_rng_path(self):
        source = Path(ar1.__file__).read_text(encoding="utf-8")
        self.assertNotIn("np.random", source)
        self.assertNotIn("import random", source)


class SyntheticArmExecutionTests(unittest.TestCase):
    def setUp(self):
        height, width = 40, 48
        yy, xx = np.mgrid[:height, :width]
        self.or_rgb = np.stack(
            [
                (xx * 5 + yy * 2) % 256,
                (xx * 3 + 40) % 256,
                (yy * 6 + 20) % 256,
            ],
            axis=-1,
        ).astype(np.uint8)
        self.o2_rgb = np.clip(self.or_rgb.astype(np.int16) - 7, 0, 255).astype(np.uint8)
        self.cell = {"job": "synthetic-job", "image": "IMG-5", "seed": "lab-ctla1"}
        self.block = {
            "executed": {
                "effective_seed": "lab:lab-ctla1",
                "finish": {"width": width, "height": height},
            }
        }
        self.tone_calls = []
        self.qf_calls = []
        self.candidate_calls = []

    def _histogram_match(self, source, reference, strength):
        self.tone_calls.append(
            {"source": np.asarray(source).copy(), "reference_size": reference.size, "strength": strength}
        )
        return source.copy()

    def _quality_finish(self, **kwargs):
        self.qf_calls.append(kwargs.copy())
        if "image" in kwargs:
            rgb = np.asarray(kwargs["image"], dtype=np.uint8)
            standalone = False
        else:
            with Image.open(kwargs["input_path"]) as image:
                rgb = np.asarray(image.convert("RGB"), dtype=np.uint8)
            standalone = True
        checkpoint_dir = Path(kwargs["checkpoint_dir"])
        Image.fromarray(rgb).save(checkpoint_dir / "O4_preencode.png", format="PNG")
        ar1._save_final(rgb, Path(kwargs["output_path"]))
        return {
            "applied": True,
            "standalone_jpeg": standalone,
            "checkpoint_errors": [],
            "encode": {"quality": 97, "subsampling": "4:4:4", "single_encode": True},
        }

    def _build_candidate(self, or_rgb, o2_rgb):
        self.candidate_calls.append((or_rgb.copy(), o2_rgb.copy()))
        candidate = np.clip(o2_rgb.astype(np.int16) + 1, 0, 255).astype(np.uint8)
        return SimpleNamespace(
            rgb=candidate,
            support=np.ones(candidate.shape[:2], dtype=bool),
            report={
                "fail_closed": False,
                "recovery": {
                    "eligible_numerator": 3.0,
                    "eligible_lost_energy_mass": 0.25,
                    "whole_frame_numerator": 4.0,
                },
            },
        )

    def test_every_arm_uses_the_exact_input_and_handoff(self):
        functions = ar1.FrozenFunctions(
            self._histogram_match,
            self._quality_finish,
            self._build_candidate,
        )
        with tempfile.TemporaryDirectory(prefix="ar1-contract-") as temp_dir:
            temp = Path(temp_dir)
            source_path = temp / "source.png"
            Image.fromarray(self.or_rgb).save(source_path, format="PNG")
            reports = {}
            for arm in ar1.ARMS:
                reports[arm.name] = ar1.run_arm(
                    arm,
                    self.cell,
                    self.block,
                    source_path,
                    self.or_rgb,
                    self.o2_rgb,
                    temp / arm.name,
                    functions,
                )

            self.assertEqual(len(self.tone_calls), 7)
            self.assertEqual(len(self.qf_calls), 5)
            self.assertEqual(len(self.candidate_calls), 1)
            self.assertTrue(np.array_equal(self.tone_calls[0]["source"], self.o2_rgb))
            self.assertTrue(np.array_equal(self.tone_calls[1]["source"], self.or_rgb))
            self.assertTrue(np.array_equal(self.tone_calls[2]["source"], self.o2_rgb))
            self.assertTrue(np.array_equal(self.tone_calls[3]["source"], self.or_rgb))
            self.assertTrue(np.array_equal(self.tone_calls[4]["source"], self.o2_rgb + 1))
            self.assertTrue(np.array_equal(self.tone_calls[5]["source"], self.o2_rgb))
            self.assertTrue(np.array_equal(self.tone_calls[6]["source"], self.or_rgb))
            self.assertTrue(all(call["reference_size"] == (48, 40) for call in self.tone_calls))
            self.assertTrue(all(call["strength"] == 0.8 for call in self.tone_calls))

            by_arm = {Path(call["checkpoint_dir"]).name: call for call in self.qf_calls}
            for name in ("A0", "A1", "A4"):
                self.assertIn("input_path", by_arm[name])
                self.assertNotIn("image", by_arm[name])
            for name in ("A2", "A3"):
                self.assertIn("image", by_arm[name])
                self.assertNotIn("input_path", by_arm[name])
            self.assertTrue(all(call["seed_extra"] == "lab:lab-ctla1" for call in self.qf_calls))
            self.assertTrue(all(call["reference"] == source_path for call in self.qf_calls))

            for arm in ar1.ARMS:
                arm_dir = temp / arm.name
                self.assertEqual((arm_dir / "stage1-q92.jpg").is_file(), arm.intermediate_jpeg)
                self.assertTrue((arm_dir / "O4_preencode.png").is_file())
                final = arm_dir / "O5_final.jpg"
                self.assertTrue(final.is_file())
                self.assertEqual(ar1._jpeg_info(final)["sampling"], "4:4:4")
                self.assertFalse(ar1._has_exif(final))
                self.assertEqual(reports[arm.name]["delivery_contract"]["quality"], 97)
                if arm.intermediate_jpeg:
                    self.assertEqual(ar1._jpeg_info(arm_dir / "stage1-q92.jpg")["sampling"], "4:2:0")

            self.assertEqual(reports["A4"]["A4_recovery_metrics"]["eligible_recovered_energy"], 3.0)
            self.assertEqual(reports["A4"]["A4_recovery_metrics"]["eligible_lost_energy_mass"], 0.25)
            self.assertEqual(reports["A4"]["A4_recovery_metrics"]["whole_frame_recovered_energy"], 4.0)


class StopAndArtifactTests(unittest.TestCase):
    def test_non_finite_values_fail_closed(self):
        with self.assertRaises(ar1.FreezeViolation):
            ar1._json_ready({"metric": np.float64(np.nan)})
        with self.assertRaises(ar1.FreezeViolation):
            ar1._json_ready({"metric": float("inf")})

    def test_artifact_index_hashes_everything_except_itself(self):
        with tempfile.TemporaryDirectory(prefix="ar1-index-") as temp_dir:
            directory = Path(temp_dir)
            (directory / "value.txt").write_text("frozen\n", encoding="utf-8")
            report = directory / "report.md"
            report.write_text("report\n", encoding="utf-8")
            ar1._artifact_index(directory, report)
            index = json.loads((directory / "artifact-index.json").read_text(encoding="utf-8"))
            paths = [row["path"] for row in index["files"]]
            self.assertNotIn("artifact-index.json", paths)
            self.assertIn("value.txt", paths)
            self.assertIn(ar1.REPORT_PATH.name, paths)

    def test_existing_output_is_never_overwritten(self):
        with tempfile.TemporaryDirectory(prefix="ar1-collision-") as temp_dir:
            base = Path(temp_dir)
            occupied = base / "round-4d-ar1"
            occupied.mkdir()
            with mock.patch.multiple(
                ar1,
                OUT=occupied,
                WORK_OUT=base / "work",
                REPORT_PATH=base / "report.md",
                WORK_REPORT_PATH=base / "report.md.in-progress",
            ):
                with self.assertRaises(ar1.FreezeViolation):
                    ar1._ensure_clean_output_targets()


if __name__ == "__main__":
    unittest.main()
