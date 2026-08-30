#!/usr/bin/env python3
"""Replay-contract tests that do not create experiment artifacts."""

import sys
import unittest
from pathlib import Path

import numpy as np

TOOLS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS_DIR))
sys.path.insert(0, str(TOOLS_DIR.parent))

import round_4d_1b_replay as replay


class ReplayContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest, cls.settings, cls.cells, cls.checks = replay.verify_inputs()

    def test_all_literal_and_pixel_provenance_checks_pass(self):
        self.assertEqual(len(self.manifest["cells"]), 24)
        self.assertEqual(len(self.cells), 12)
        self.assertEqual(len(self.checks), 191)
        self.assertTrue(all(row["pass"] for row in self.checks))

    def test_executed_finish_wins_over_requested_adaptive_label(self):
        for cell in self.cells:
            block = self.settings["jobs"][cell["job"]]
            normalized = replay._finish_settings(block)["quality_finish"]
            self.assertEqual(normalized["preset"], "strong")
            self.assertEqual(normalized["scale"], 1)
            self.assertEqual(normalized["overrides"], {"dither": 1, "sharpen": 1, "smoothness": 1.25})
            self.assertEqual(normalized["finish_mode"], "fixed-executed-replay")

    def test_fixed_profile_rejects_flat_input(self):
        flat = np.full((80, 80), 0.5, dtype=np.float64)
        self.assertIsNone(replay._fixed_profile(flat, {"y": 40, "x": 40, "orientation": "h"}))

    def test_six_image_cohort_is_exact(self):
        self.assertEqual(set(replay.SIX_IMAGES), {"IMG-5", "IMG-6", "IMG-7", "IMG-8", "IMG-9", "IMG-11"})

    def test_numpy_report_scalars_normalize_to_strict_json_types(self):
        value = replay._json_ready({"f": np.float32(0.25), "i": np.int64(7), "a": np.array([1, 2])})
        self.assertEqual(value, {"f": 0.25, "i": 7, "a": [1, 2]})
        with self.assertRaises(ValueError):
            replay._json_ready(np.float64(np.nan))


if __name__ == "__main__":
    unittest.main()
