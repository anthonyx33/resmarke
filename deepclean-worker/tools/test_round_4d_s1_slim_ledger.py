#!/usr/bin/env python3
"""Tests for the offline-only 4D S1-slim stage-ledger builder."""

from __future__ import annotations

import copy
import importlib.util
import json
import sys
import tempfile
import unittest
from dataclasses import asdict
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("round_4d_s1_slim_ledger.py")
SPEC = importlib.util.spec_from_file_location("round_4d_s1_slim_ledger", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
s1 = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = s1
SPEC.loader.exec_module(s1)


def valid_rows(pins, scores=None):
    values = scores or {
        "O1": [0.40] * 6,
        "OR": [0.40] * 6,
        "O2": [0.40] * 6,
    }
    image_index = {image: index for index, image in enumerate(s1.IMAGES)}
    rows = []
    seen_sha = {}
    first_by_sha = {}
    fresh_counter = 0
    for index, pin in enumerate(pins):
        score = values[pin.stage][image_index[pin.image]]
        first_index = seen_sha.get(pin.sha256)
        is_fresh = first_index is None
        if is_fresh:
            fresh_counter += 1
            vendor_calls = fresh_counter
            task_id = "task-{:02d}".format(fresh_counter)
        else:
            first = first_by_sha[pin.sha256]
            vendor_calls = first["session_usage"]["vendor_calls"]
            task_id = first["task_id"]
        row = {
            "logical_id": pin.logical_id,
            "image": pin.image,
            "job": pin.job,
            "seed": pin.seed,
            "source": {"path": pin.source_path, "sha256": pin.source_sha256},
            "stage": pin.stage,
            "file": asdict(pin),
            "attempt_number": 1,
            "submitted_sha256": pin.sha256,
            "ai_probability": score,
            "deepfake_probability": 0.02,
            "verdict": "CLEAR" if score <= s1.AI_THRESHOLD else "FAIL",
            "sources": {"flux-schnell": 0.10, "other-family": 0.90},
            "flux_family": 0.10,
            "top_source": "other-family",
            "task_id": task_id,
            "model": s1.MODEL,
            "version": s1.MODEL_VERSION,
            "vendor": s1.VENDOR,
            "mode": "real",
            "mock": False,
            "cache_hit": not is_fresh,
            "provider_calls": 0 if not is_fresh else 1,
            "session_usage": {"vendor_calls": vendor_calls, "cap": 40},
            "vendor_error": None,
            "c2pa": "absent (no algorithmic_tags.c2pa in response)",
        }
        if is_fresh:
            seen_sha[pin.sha256] = index
            first_by_sha[pin.sha256] = row
        rows.append(row)
    return rows


def verified_reuse(o5_scores=None, passing_images=None):
    values = o5_scores or {image: 0.40 for image in s1.IMAGES}
    pass_set = set(s1.IMAGES if passing_images is None else passing_images)
    result = []
    for image in s1.IMAGES:
        flux = 0.10 if image in pass_set else 0.60
        result.append({
            "image": image,
            "status": "hash_verified_reuse",
            "o5_equivalent": "matrix_config_a_delivered_grade",
            "reused_grade": {
                "ai_probability": values[image],
                "flux_family": flux,
                "deepfake_probability": 0.02,
            },
        })
    return result


class PinTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pins, cls.checks, cls.reuse = s1.preflight()

    def test_exact_18_pins_in_frozen_cell_stage_order(self):
        self.assertEqual(len(self.pins), 18)
        self.assertEqual([pin.image for pin in self.pins[::3]], list(s1.IMAGES))
        for offset in range(0, 18, 3):
            self.assertEqual([pin.stage for pin in self.pins[offset:offset + 3]], list(s1.STAGES))

    def test_real_stage_pin_preflight_is_green(self):
        self.assertTrue(self.checks)
        self.assertTrue(all(row["pass"] for row in self.checks))

    def test_pins_include_hash_dimensions_stage_cell_seed_and_source(self):
        for pin in self.pins:
            self.assertEqual(len(pin.sha256), 64)
            self.assertGreater(pin.width, 0)
            self.assertGreater(pin.height, 0)
            self.assertIn(pin.stage, s1.STAGES)
            self.assertIn(pin.image, s1.IMAGES)
            self.assertEqual(pin.seed, s1.SEED)
            self.assertEqual(len(pin.source_sha256), 64)

    def test_existing_o5_bytes_use_matrix_equivalent_on_hash_mismatch(self):
        self.assertEqual([row["status"] for row in self.reuse], ["o5_hash_mismatch"] * 6)
        self.assertTrue(all(row["o5_equivalent"] == "matrix_config_a_delivered_grade" for row in self.reuse))
        self.assertTrue(all(
            isinstance(row["reused_grade"], dict)
            and "ai_probability" in row["reused_grade"]
            and "flux_family" in row["reused_grade"]
            and "deepfake_probability" in row["reused_grade"]
            for row in self.reuse
        ))

    def test_contract_declares_exact_budget_and_no_retry(self):
        value = s1.contract(self.pins, self.reuse)
        self.assertEqual(value["logical_call_budget"], 18)
        self.assertEqual(value["vendor_call_budget"], 15)
        self.assertEqual(value["freshness"]["attempt_number"], 1)
        self.assertIn("unique byte stream", value["freshness"]["provider_calls"])

    def test_source_has_no_grader_network_or_rng_primitive(self):
        source = MODULE_PATH.read_text(encoding="utf-8")
        for forbidden in (
            "import requests", "import httpx", "import urllib", "import socket",
            "urlopen(", "subprocess", "import random", "import uuid", "grade_image(",
        ):
            self.assertNotIn(forbidden, source)


class GradeValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pins = s1.expected_stage_pins()

    def test_valid_18_real_rows_pass(self):
        result = s1.validate_grade_rows(valid_rows(self.pins), self.pins)
        self.assertEqual(len(result), 18)
        self.assertTrue(all(row["full_v3_pass"] for row in result))

    def test_wrong_order_fails(self):
        rows = valid_rows(self.pins)
        rows[0], rows[1] = rows[1], rows[0]
        with self.assertRaises(s1.FreezeViolation):
            s1.validate_grade_rows(rows, self.pins)

    def test_changed_pin_fails(self):
        rows = valid_rows(self.pins)
        rows[0]["submitted_sha256"] = "0" * 64
        with self.assertRaises(s1.FreezeViolation):
            s1.validate_grade_rows(rows, self.pins)

    def test_mock_cache_and_retry_each_fail(self):
        for field, value in (("mock", True), ("cache_hit", True), ("provider_calls", 2)):
            rows = valid_rows(self.pins)
            rows[0][field] = value
            with self.assertRaises(s1.FreezeViolation, msg=field):
                s1.validate_grade_rows(rows, self.pins)

    def test_missing_flux_source_fails_closed(self):
        rows = valid_rows(self.pins)
        rows[0]["sources"] = {"other-family": 1.0}
        with self.assertRaises(s1.FreezeViolation):
            s1.validate_grade_rows(rows, self.pins)

    def test_flux_max_mismatch_fails_closed(self):
        rows = valid_rows(self.pins)
        rows[0]["flux_family"] = 0.20
        with self.assertRaises(s1.FreezeViolation):
            s1.validate_grade_rows(rows, self.pins)

    def test_c2pa_deny_match_stops_leg(self):
        rows = valid_rows(self.pins)
        rows[0]["c2pa"] = {"actions_digital_source_type": "trainedAlgorithmicMedia"}
        with self.assertRaisesRegex(s1.FreezeViolation, "C2PA deny-list"):
            s1.validate_grade_rows(rows, self.pins)

    def test_ordinary_c2pa_provenance_is_reported_but_not_denied(self):
        rows = valid_rows(self.pins)
        rows[0]["c2pa"] = {"claim_generator": "ordinary-editor", "created": "2026-08-31"}
        result = s1.validate_grade_rows(rows, self.pins)
        self.assertEqual(len(result), 18)

    def test_duplicate_task_id_fails(self):
        rows = valid_rows(self.pins)
        rows[1]["task_id"] = rows[0]["task_id"]
        with self.assertRaises(s1.FreezeViolation):
            s1.validate_grade_rows(rows, self.pins)

    def test_byte_identical_pair_must_copy_verbatim(self):
        rows = valid_rows(self.pins)
        duplicate = next(row for row in rows if row["cache_hit"])
        duplicate["ai_probability"] = round(duplicate["ai_probability"] + 0.001, 6)
        with self.assertRaisesRegex(s1.FreezeViolation, "verbatim"):
            s1.validate_grade_rows(rows, self.pins)

    def test_vendor_call_budget_counts_unique_byte_streams(self):
        value = s1.contract(s1.expected_stage_pins(), [])
        self.assertEqual(value["vendor_call_budget"], 15)
        self.assertEqual(value["logical_call_budget"], 18)

    def test_nonconsecutive_session_usage_fails(self):
        rows = valid_rows(self.pins)
        rows[5]["session_usage"]["vendor_calls"] += 1
        with self.assertRaises(s1.FreezeViolation):
            s1.validate_grade_rows(rows, self.pins)

    def test_vendor_error_fails(self):
        rows = valid_rows(self.pins)
        rows[0]["vendor_error"] = "provider failed"
        with self.assertRaises(s1.FreezeViolation):
            s1.validate_grade_rows(rows, self.pins)

    def test_missing_vendor_error_field_fails_closed(self):
        rows = valid_rows(self.pins)
        del rows[0]["vendor_error"]
        with self.assertRaises(s1.FreezeViolation):
            s1.validate_grade_rows(rows, self.pins)

    def test_malformed_jsonl_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "grades.jsonl"
            path.write_text("not-json\n" * 18, encoding="utf-8")
            with self.assertRaises(s1.FreezeViolation):
                s1.read_grade_jsonl(path)


class ComputationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pins = s1.expected_stage_pins()

    def test_even_six_value_median_is_mean_of_middle_pair(self):
        self.assertEqual(s1.frozen_median([6, 1, 4, 3, 5, 2]), 3.5)

    def test_materiality_includes_exact_point_zero_five_boundary(self):
        gains = [(image, 0.05) for image in s1.IMAGES]
        result = s1.materiality(gains, set())
        self.assertTrue(result["magnitude_material"])
        self.assertTrue(result["material"])

    def test_four_of_six_directional_consistency_passes(self):
        values = [0.10, 0.10, 0.10, 0.10, -0.10, -0.10]
        result = s1.materiality(list(zip(s1.IMAGES, values)), set())
        self.assertEqual(result["non_negative_count"], 4)
        self.assertTrue(result["material"])

    def test_three_of_six_is_mixed_and_not_material(self):
        values = [0.40, 0.40, 0.40, -0.20, -0.20, -0.20]
        result = s1.materiality(list(zip(s1.IMAGES, values)), set())
        self.assertTrue(result["magnitude_material"])
        self.assertFalse(result["material"])
        self.assertTrue(result["mixed_signs"])

    def test_passing_cell_negative_gain_vetoes_materiality(self):
        values = [-0.01, 0.10, 0.10, 0.10, 0.10, 0.10]
        result = s1.materiality(list(zip(s1.IMAGES, values)), {s1.IMAGES[0]})
        self.assertFalse(result["material"])
        self.assertTrue(result["mixed_signs"])
        self.assertEqual(result["passing_cell_veto"], [s1.IMAGES[0]])

    def test_o5_hash_mismatch_proceeds_with_matrix_equivalent_grades(self):
        validated = s1.validate_grade_rows(valid_rows(self.pins), self.pins)
        mismatch = [{
            "image": image,
            "status": "o5_hash_mismatch",
            "o5_equivalent": "matrix_config_a_delivered_grade",
            "reused_grade": {"ai_probability": 0.40, "flux_family": 0.10, "deepfake_probability": 0.02},
        } for image in s1.IMAGES]
        metrics = s1.compute_stage_deltas(validated, mismatch)
        self.assertEqual(sorted(metrics["o5_hash_mismatch_images"]), sorted(s1.IMAGES))
        self.assertEqual(len(metrics["per_cell"]), 6)
        self.assertTrue(metrics["delivered_clear"])

    def _metrics(self, scores, o5_scores=None, passing_images=None):
        validated = s1.validate_grade_rows(valid_rows(self.pins, scores=scores), self.pins)
        return s1.compute_stage_deltas(
            validated,
            verified_reuse(o5_scores=o5_scores, passing_images=passing_images),
        )

    def test_decision_branch_camera_removal(self):
        metrics = self._metrics({stage: [0.40] * 6 for stage in s1.STAGES})
        result = s1.decide(metrics)
        self.assertEqual(result["decision_row_count"], 1)
        self.assertEqual(result["decision"]["primary_condition"], "wash_clear_camera_not_material")

    def test_decision_branch_camera_retain(self):
        metrics = self._metrics({"O1": [0.40] * 6, "OR": [0.40] * 6, "O2": [0.20] * 6})
        result = s1.decide(metrics)
        self.assertEqual(result["decision"]["primary_condition"], "wash_clear_camera_material")

    def test_decision_branch_camera_neutral(self):
        metrics = self._metrics({
            "O1": [0.80, 0.40, 0.40, 0.40, 0.80, 0.80],
            "OR": [0.80, 0.40, 0.40, 0.40, 0.80, 0.80],
            "O2": [0.42] * 6,
        })
        result = s1.decide(metrics)
        self.assertEqual(
            result["decision"]["primary_condition"],
            "wash_not_clear_o2_clear_camera_not_material",
        )

    def test_decision_branch_camera_decomposition(self):
        metrics = self._metrics({"O1": [0.80] * 6, "OR": [0.80] * 6, "O2": [0.30] * 6})
        result = s1.decide(metrics)
        self.assertEqual(
            result["decision"]["primary_condition"],
            "wash_not_clear_o2_clear_camera_material",
        )

    def test_decision_branch_stop_camera(self):
        metrics = self._metrics({"O1": [0.80] * 6, "OR": [0.80] * 6, "O2": [0.70] * 6})
        result = s1.decide(metrics)
        self.assertEqual(result["decision"]["primary_condition"], "wash_not_clear_o2_not_clear")

    def test_resample_material_and_not_material_branches(self):
        material = self._metrics({
            "O1": [0.80] * 6,
            "OR": [0.60, 0.80, 0.80, 0.80, 0.60, 0.60],
            "O2": [0.55] * 6,
        })
        dead = self._metrics({"O1": [0.80] * 6, "OR": [0.80] * 6, "O2": [0.70] * 6})
        self.assertEqual(s1.decide(material)["decision"]["resample_condition"], "resample_gain_material")
        self.assertEqual(s1.decide(dead)["decision"]["resample_condition"], "resample_not_material")

    def test_mixed_sign_branch_prohibits_universal_change(self):
        metrics = {
            "wash_clear": False,
            "o2_clear": False,
            "camera_gain": {"material": False, "mixed_signs": True},
            "resample_gain": {"material": False, "mixed_signs": False},
        }
        result = s1.decide(metrics)
        self.assertEqual(result["decision"]["universal_change_decision"], s1.DECISION_TEXT["mixed"])


class OutputTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pins = s1.expected_stage_pins()

    def test_atomic_publish_emits_exact_three_files(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "round-4d-s1-slim"
            payload = {
                "ledger-raw.json": {"a": 1},
                "stage-deltas.json": {"b": 2},
                "decision.json": {"c": 3},
            }
            s1.atomic_publish(output, payload)
            self.assertEqual({path.name for path in output.iterdir()}, set(payload))

    def test_atomic_publish_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "round-4d-s1-slim"
            output.mkdir()
            payload = {
                "ledger-raw.json": {},
                "stage-deltas.json": {},
                "decision.json": {},
            }
            with self.assertRaisesRegex(s1.FreezeViolation, "overwrite refused"):
                s1.atomic_publish(output, payload)

    def test_end_to_end_artifact_build_has_exact_names_and_one_decision_row(self):
        rows = valid_rows(self.pins)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "grades.jsonl"
            path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
            artifacts = s1.build_artifacts(path, self.pins, verified_reuse())
        self.assertEqual(
            set(artifacts),
            {"ledger-raw.json", "stage-deltas.json", "decision.json"},
        )
        self.assertEqual(artifacts["decision.json"]["decision_row_count"], 1)
        self.assertEqual(len(artifacts["ledger-raw.json"]["rows"]), 18)


if __name__ == "__main__":
    unittest.main()
