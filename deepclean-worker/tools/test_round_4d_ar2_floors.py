#!/usr/bin/env python3
"""4D-AR2 floor-evaluator contracts; no real AR2 evaluation is run."""

from __future__ import annotations

import ast
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np
from PIL import Image

TOOLS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS_DIR))

import round_4d_ar2_floors as ar2


class FrozenInputTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.environment = ar2.verify_environment()
        cls.bundle = ar2.verify_inputs()

    def test_frozen_environment_and_all_ar1_pins_pass(self):
        self.assertTrue(self.environment["pass"])
        self.assertTrue(all(row["pass"] for row in self.bundle.checks))
        self.assertEqual(self.bundle.ar1_index_sha256, ar2.AR1_INDEX_EXPECTED_SHA256)

    def test_exact_cohort_and_arm_contract(self):
        self.assertEqual(len(self.bundle.cells), 12)
        self.assertEqual(
            {(cell["image"], cell["seed"]) for cell in self.bundle.cells},
            {(image, seed) for image in ar2.SIX_IMAGES for seed in ar2.SEEDS},
        )
        self.assertEqual(ar2.ARMS, ("A0", "A1", "A2", "A3", "A4", "A5", "A6"))
        self.assertEqual(ar2.CHALLENGERS, ("A1", "A2", "A3", "A4", "A5", "A6"))

    def test_thresholds_are_literal_freeze_values(self):
        self.assertEqual(ar2.PROTECTED_EATR_FLOOR, 0.98)
        self.assertEqual(ar2.LUMA_RISE_CEILING, 0.05)
        self.assertEqual(ar2.CHROMA_RISE_CEILING, 0.05)
        self.assertEqual(ar2.H3_STEP_MIN, 0.08)
        self.assertEqual((ar2.H3_WIDTH_MIN, ar2.H3_WIDTH_MAX), (2.0, 12.0))
        self.assertEqual(ar2.H3_PEAK_AMPLITUDE_MIN, 0.05)
        self.assertEqual(ar2.H3_ENDPOINT_SEPARATION_MIN, 2.0)

    def test_harness_imports_no_network_or_rng_modules(self):
        source = Path(ar2.__file__).read_text(encoding="utf-8")
        tree = ast.parse(source)
        imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.add(node.module.split(".")[0])
        self.assertTrue(imports.isdisjoint({"requests", "urllib", "httpx", "socket", "supabase"}))
        self.assertNotIn("np.random", source)
        self.assertNotIn("import random", source)


class ProfileRuleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.isotonic = staticmethod(ar2.load_frozen_recipes().isotonic)
        cls.xs = np.arange(-ar2.PROFILE_HALF_WIDTH, ar2.PROFILE_HALF_WIDTH + 1, dtype=np.float64)

    def ramp(self, step=0.20, width=4.0, low=0.30):
        normalized = np.clip((self.xs + width / 2.0) / width, 0.0, 1.0)
        return low + step * normalized

    def test_stable_profile_is_eligible_without_a_second_peak(self):
        profile = ar2.analyze_raw_profile(self.ramp(), self.isotonic)
        self.assertTrue(profile["eligible"])
        self.assertTrue(profile["frozen_esf_profile_valid"])
        self.assertGreaterEqual(profile["step"], 0.08)
        self.assertGreaterEqual(profile["width_10_90"], 2.0)
        self.assertLessEqual(profile["width_10_90"], 12.0)
        self.assertEqual(profile["second_peaks"], [])

    def test_peak_requires_strictly_more_than_five_percent_of_step(self):
        below = self.ramp()
        below[np.where(self.xs == 15)[0][0]] += 0.049 * 0.20
        above = self.ramp()
        above[np.where(self.xs == 15)[0][0]] += 0.051 * 0.20
        self.assertEqual(ar2.analyze_raw_profile(below, self.isotonic)["second_peaks"], [])
        peaks = ar2.analyze_raw_profile(above, self.isotonic)["second_peaks"]
        self.assertEqual(len(peaks), 1)
        self.assertEqual(peaks[0]["side"], "right")
        self.assertGreater(peaks[0]["deviation_step_fraction"], 0.05)

    def test_extremum_inside_two_pixels_of_transition_is_not_a_second_peak(self):
        raw = self.ramp()
        base = ar2.analyze_raw_profile(raw, self.isotonic)
        near_x = int(math_floor(base["transition"]["x90"] + 1.0))
        raw[np.where(self.xs == near_x)[0][0]] += 0.10 * 0.20
        self.assertEqual(ar2.analyze_raw_profile(raw, self.isotonic)["second_peaks"], [])

    def test_low_step_and_wide_transition_are_excluded(self):
        low = ar2.analyze_raw_profile(self.ramp(step=0.079), self.isotonic)
        wide = ar2.analyze_raw_profile(self.ramp(step=0.20, width=16.0), self.isotonic)
        self.assertFalse(low["eligible"])
        self.assertIn("plateau_step_below_0.08", low["exclusion_reasons"])
        self.assertFalse(wide["eligible"])
        self.assertIn("width_outside_[2,12]", wide["exclusion_reasons"])

    def test_either_a0_or_arm_domain_failure_excludes_the_edge(self):
        good = ar2.analyze_raw_profile(self.ramp(), self.isotonic)
        bad = ar2.analyze_raw_profile(self.ramp(step=0.05), self.isotonic)
        self.assertEqual(ar2._profile_exclusion_reasons(bad, good), ["a0_plateau_step_below_0.08"])
        self.assertEqual(ar2._profile_exclusion_reasons(good, bad), ["arm_plateau_step_below_0.08"])

    def test_cell_rule_counts_only_protected_eligible_peaks(self):
        size = 64
        ys = np.arange(size, dtype=np.float64) - 32.0
        line = 0.30 + 0.20 * np.clip((ys + 2.0) / 4.0, 0.0, 1.0)
        a0 = np.repeat(line[:, None], size, axis=1)
        arm = a0.copy()
        arm[47, 32] += 0.02
        edges = [
            {"y": 32, "x": 32, "orientation": "h", "protected": True},
            {"y": 32, "x": 40, "orientation": "h", "protected": False},
        ]
        cell = {"job": "j", "image": "IMG-5", "seed": "lab-ctla1"}
        row = ar2.evaluate_h3_cell(cell, "A1", arm, a0, a0, edges, self.isotonic)
        self.assertEqual(row["protected_edge_count"], 1)
        self.assertEqual(row["eligible_edge_count"], 1)
        self.assertEqual(row["overshoot_oot_reportable_edge_count"], 1)
        self.assertEqual(row["width_gap_reportable_edge_count"], 1)
        self.assertEqual(row["excluded_edge_count"], 0)
        self.assertEqual(row["second_peak_edge_count"], 1)
        self.assertGreaterEqual(row["second_peak_count"], 1)
        self.assertFalse(row["pass"])

    def test_source_width_failure_does_not_remove_h3_eligible_overshoot_reporting(self):
        size = 64
        ys = np.arange(size, dtype=np.float64) - 32.0
        line = 0.30 + 0.20 * np.clip((ys + 2.0) / 4.0, 0.0, 1.0)
        a0 = np.repeat(line[:, None], size, axis=1)
        flat_source = np.full_like(a0, 0.4)
        edge = {"y": 32, "x": 32, "orientation": "h", "protected": True}
        cell = {"job": "j", "image": "IMG-5", "seed": "lab-ctla1"}
        row = ar2.evaluate_h3_cell(cell, "A1", a0, a0, flat_source, [edge], self.isotonic)
        self.assertEqual(row["eligible_edge_count"], 1)
        self.assertEqual(row["overshoot_oot_reportable_edge_count"], 1)
        self.assertEqual(row["width_gap_reportable_edge_count"], 0)
        self.assertIsNotNone(row["esf"]["median_overshoot_delta"])
        self.assertIsNone(row["esf"]["median_width_gap_worsening_px"])
        self.assertEqual(row["esf_reporting_excluded_edge_count"], 1)


def math_floor(value):
    return int(np.floor(value))


def h3_row(passed=True):
    return {
        "job": "j",
        "image": "IMG-5",
        "seed": "lab-ctla1",
        "protected_edge_count": 1,
        "eligible_edge_count": 1,
        "overshoot_oot_reportable_edge_count": 1,
        "width_gap_reportable_edge_count": 1,
        "excluded_edge_count": 0,
        "esf_reporting_excluded_edge_count": 0,
        "second_peak_edge_count": 0 if passed else 1,
        "second_peak_count": 0 if passed else 1,
        "pass": passed,
        "exclusion_table": [],
        "esf_reporting_exclusion_table": [],
        "peak_edges": [],
        "esf": {
            "median_overshoot_delta": 0.01,
            "worst_pair_overshoot_delta": 0.02,
            "median_width_gap_worsening_px": 0.1,
            "worst_pair_width_gap_worsening_px": 0.2,
            "median_oot_delta": 0.01,
            "worst_pair_oot_delta": 0.02,
        },
    }


def m2_row(luma=0.0, chroma=0.0, protected=1.0, upstream=True):
    return {
        "job": "j",
        "vs_A0": {
            "smooth_luma_rise": luma,
            "smooth_chroma_rise": chroma,
            "smooth_rho1_rise": 0.0,
            "smooth_rho2_rise": 0.0,
            "protected_eatr_ratio_min": protected,
            "upstream_identity_pass": upstream,
        },
    }


class AutomaticGateTests(unittest.TestCase):
    def setUp(self):
        self.cells = [{"job": "j", "image": "IMG-5", "seed": "lab-ctla1"}]

    def gate(self, arm="A1", row=None, h3=None, geometry=True):
        return ar2.evaluate_automatic_gate(
            arm,
            self.cells,
            {"j": row or m2_row()},
            {"j": geometry},
            [h3 or h3_row()],
        )

    def test_all_four_hard_gates_are_conjunctive(self):
        self.assertTrue(self.gate()["automatic_pass"])
        self.assertFalse(self.gate(row=m2_row(protected=0.979))["automatic_pass"])
        self.assertFalse(self.gate(row=m2_row(luma=0.051))["automatic_pass"])
        self.assertFalse(self.gate(h3=h3_row(False))["automatic_pass"])
        self.assertFalse(self.gate(geometry=False)["automatic_pass"])

    def test_amplitude_boundary_is_inclusive(self):
        gate = self.gate(row=m2_row(luma=0.05, chroma=0.05))
        self.assertTrue(gate["H2_amplitude"]["pass"])

    def test_a4_is_excluded_even_when_h1_h2_h3_pass(self):
        gate = self.gate(arm="A4")
        self.assertTrue(gate["H1_integrity"]["pass"])
        self.assertTrue(gate["H2_amplitude"]["pass"])
        self.assertTrue(gate["H3_robust_second_peaks"]["pass"])
        self.assertFalse(gate["H4_no_op_exclusion"]["pass"])
        self.assertFalse(gate["automatic_pass"])


class EvaluationStateTests(unittest.TestCase):
    def _run_synthetic(self, a1_pass):
        with tempfile.TemporaryDirectory(prefix="ar2-evaluate-") as temp_dir:
            base = Path(temp_dir)
            ar1_dir = base / "round-4d-ar1"
            checkpoints = base / "checkpoints"
            job = "j"
            size = 64
            ys = np.arange(size, dtype=np.float64) - 32.0
            line = 0.30 + 0.20 * np.clip((ys + 2.0) / 4.0, 0.0, 1.0)
            rgb = np.repeat(np.rint(line[:, None] * 255).astype(np.uint8), size, axis=1)
            rgb = np.repeat(rgb[..., None], 3, axis=2)
            (checkpoints / job).mkdir(parents=True)
            Image.fromarray(rgb).save(checkpoints / job / "O0_source.png", format="PNG")
            for arm in ar2.ARMS:
                target = ar1_dir / "arms" / arm / job
                target.mkdir(parents=True)
                Image.fromarray(rgb).save(target / "O5_final.jpg", format="JPEG", quality=97, subsampling=0)

            cells = [{"job": job, "image": "IMG-5", "seed": "lab-ctla1"}]
            arm_cells = {}
            for arm in ar2.ARMS:
                amplitude = 0.0 if arm == "A1" and a1_pass else 0.06
                if arm in ("A0", "A4"):
                    amplitude = 0.0
                arm_cells[arm] = [m2_row(luma=amplitude, chroma=amplitude)]
            m2 = {
                "arm_cells": arm_cells,
                "cohort_summary": {
                    "A1": {
                        "smooth_rho1_rise_max": 0.01,
                        "smooth_rho2_rise_max": 0.02,
                        "smooth_rho_rise_max": 0.02,
                    }
                },
            }
            bundle = ar2.InputBundle(
                cells=cells,
                roi={"IMG-5": {"protected": [[0.0, 0.0, 1.0, 1.0]]}},
                m2=m2,
                checks=[],
                ar1_index_sha256="frozen",
            )
            frozen = ar2.load_frozen_recipes()
            recipes = ar2.FrozenRecipes(
                load=frozen.load,
                luma=frozen.luma,
                resample_to=frozen.resample_to,
                edge_support=lambda *_: [
                    {"y": 32, "x": 32, "orientation": "h", "protected": True}
                ],
                isotonic=frozen.isotonic,
            )
            with mock.patch.multiple(ar2, AR1=ar1_dir, CHECKPOINTS=checkpoints):
                return ar2.evaluate(bundle, recipes)

    def test_empty_shortlist_fails_closed_before_panel_and_hive(self):
        result = self._run_synthetic(a1_pass=False)
        self.assertEqual(result["shortlist"], [])
        self.assertEqual(result["status"], "EMPTY_SHORTLIST_STOP_NO_PANEL_NO_HIVE")
        self.assertFalse(result["panel"]["authorized"])
        self.assertFalse(result["panel"]["run"])
        self.assertFalse(result["hive"]["authorized"])
        self.assertEqual(result["hive"]["calls"], 0)
        json.dumps(ar2._json_ready(result), allow_nan=False)
        with tempfile.TemporaryDirectory(prefix="ar2-report-") as temp_dir:
            report = Path(temp_dir) / "shortlist.md"
            ar2._write_report(report, result)
            self.assertIn("EMPTY SHORTLIST", report.read_text(encoding="utf-8"))

    def test_nonempty_shortlist_only_authorizes_panel(self):
        result = self._run_synthetic(a1_pass=True)
        self.assertEqual(result["shortlist"], ["A1"])
        self.assertEqual(result["status"], "SHORTLIST_READY_PANEL_NOT_RUN")
        self.assertTrue(result["panel"]["authorized"])
        self.assertFalse(result["panel"]["run"])
        self.assertFalse(result["hive"]["authorized"])
        self.assertEqual(set(result["reported_panel_judged_metrics"]), {"A1"})
        with tempfile.TemporaryDirectory(prefix="ar2-report-") as temp_dir:
            report = Path(temp_dir) / "shortlist.md"
            ar2._write_report(report, result)
            text = report.read_text(encoding="utf-8")
            self.assertIn("SHORTLIST READY", text)
            self.assertIn("visible edge ringing", text)
            self.assertIn("coarse grain in smooth areas", text)


class StopAndArtifactTests(unittest.TestCase):
    def test_non_finite_metric_fails_closed(self):
        with self.assertRaises(ar2.FreezeViolation):
            ar2._json_ready({"metric": np.float64(np.nan)})
        with self.assertRaises(ar2.FreezeViolation):
            ar2._require_finite({"metric": float("inf")})

    def test_index_hashes_outputs_report_authority_and_new_files(self):
        with tempfile.TemporaryDirectory(prefix="ar2-index-") as temp_dir:
            directory = Path(temp_dir)
            (directory / "floors.json").write_text("{}\n", encoding="utf-8")
            report = directory / "report.md"
            report.write_text("report\n", encoding="utf-8")
            index = ar2._artifact_index(directory, report)
            paths = {row["path"] for row in index["files"]}
            self.assertNotIn("round-4d-ar2/artifact-index.json", paths)
            self.assertIn("round-4d-ar2/floors.json", paths)
            self.assertIn(ar2.FREEZE_PATH.name, paths)
            self.assertIn("deepclean-worker/tools/round_4d_ar2_floors.py", paths)
            self.assertIn("deepclean-worker/tools/test_round_4d_ar2_floors.py", paths)

    def test_existing_output_is_never_overwritten(self):
        with tempfile.TemporaryDirectory(prefix="ar2-collision-") as temp_dir:
            base = Path(temp_dir)
            occupied = base / "round-4d-ar2"
            occupied.mkdir()
            with mock.patch.multiple(
                ar2,
                OUT=occupied,
                WORK_OUT=base / "work",
                REPORT_PATH=base / "report.md",
                WORK_REPORT_PATH=base / "report.md.in-progress",
            ):
                with self.assertRaises(ar2.FreezeViolation):
                    ar2._ensure_clean_output_targets()


if __name__ == "__main__":
    unittest.main()
