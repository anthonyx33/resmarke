#!/usr/bin/env python3
"""Contract tests for the offline-only 4D-S1 ledger harness."""

from __future__ import annotations

import copy
import importlib.util
import json
import math
import sys
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("round_4d_s1_ledger.py")
SPEC = importlib.util.spec_from_file_location("round_4d_s1_ledger", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
s1 = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = s1
SPEC.loader.exec_module(s1)


def raw_response(task_id: str, ai: float, flux: float = 0.10, deepfake: float = 0.05) -> dict:
    return {
        "task_id": task_id,
        "model": s1.MODEL,
        "version": s1.MODEL_VERSION,
        "output": [{
            "classes": [
                {"class": "not_ai_generated", "value": 1.0 - ai},
                {"class": "ai_generated", "value": ai},
                {"class": "other-family", "value": 0.20},
                {"class": "flux-schnell", "value": flux},
                {"class": "none", "value": 0.80 - flux},
                {"class": "deepfake", "value": deepfake},
                {"class": "not_ai_generated_audio", "value": 1.0},
                {"class": "ai_generated_audio", "value": 0.0},
            ],
        }],
    }


def valid_ledger(pins, scores=None) -> dict:
    session_id = "11111111-1111-4111-8111-111111111111"
    values = scores or {
        "O1": [0.40, 0.41, 0.42, 0.43, 0.44, 0.45],
        "OR": [0.41, 0.42, 0.43, 0.44, 0.45, 0.46],
        "O2": [0.39, 0.40, 0.41, 0.42, 0.43, 0.44],
        "O5": [0.38, 0.39, 0.40, 0.41, 0.42, 0.43],
    }
    image_index = {image: index for index, image in enumerate(s1.IMAGES)}
    calls = []
    for call_index, pin in enumerate(pins):
        ai = values[pin.stage][image_index[pin.image]]
        task_id = "task-{:02d}".format(call_index + 1)
        raw = raw_response(task_id, ai)
        calls.append({
            "logical_id": pin.logical_id,
            "image": pin.image,
            "job": pin.job,
            "seed": pin.seed,
            "stage": pin.stage,
            "file": s1.asdict(pin),
            "attempt_number": 1,
            "grade_session_id": session_id,
            "submitted_sha256": pin.sha256,
            "task_id": task_id,
            "response": {
                "grade_id": "grade-{:02d}".format(call_index + 1),
                "image_sha256": pin.sha256,
                "vendor": s1.VENDOR,
                "mode": "real",
                "ai_probability": round(ai, 6),
                "deepfake_probability": 0.05,
                "sources": {"other-family": 0.20, "flux-schnell": 0.10},
                "raw": raw,
                "mock": False,
                "cache_hit": False,
                "provider_calls": 1,
                "requested_mode": "real",
                "session_usage": {"vendor_calls": call_index + 1, "cap": s1.CALL_CAP},
            },
        })
    return {
        "schema_version": s1.SCHEMA_VERSION,
        "round": s1.ROUND_ID,
        "vendor": s1.VENDOR,
        "model": s1.MODEL,
        "version": s1.MODEL_VERSION,
        "seed": s1.SEED,
        "grade_session_id": session_id,
        "call_cap": s1.CALL_CAP,
        "logical_call_budget": s1.LOGICAL_CALL_BUDGET,
        "reserve_calls": s1.RESERVE_CALLS,
        "file_pins": s1.file_pin_records(pins),
        "calls": calls,
    }


class S1PinTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pins, cls.checks = s1.expected_file_pins()

    def test_exact_frozen_cohort_has_24_files_in_stage_order(self):
        self.assertEqual(len(self.pins), 24)
        self.assertEqual([pin.image for pin in self.pins[::4]], list(s1.IMAGES))
        for offset in range(0, 24, 4):
            self.assertEqual([pin.stage for pin in self.pins[offset:offset + 4]], list(s1.STAGES))

    def test_real_data_pin_preflight_passes(self):
        self.assertTrue(self.checks)
        self.assertTrue(all(row["pass"] for row in self.checks))

    def test_three_o1_or_pairs_are_byte_identical_but_logically_distinct(self):
        by_id = {pin.logical_id: pin for pin in self.pins}
        for image in ("IMG-6", "IMG-7", "IMG-8"):
            self.assertEqual(by_id[image + ":O1"].sha256, by_id[image + ":OR"].sha256)
            self.assertNotEqual(by_id[image + ":O1"].logical_id, by_id[image + ":OR"].logical_id)

    def test_contract_declares_no_grading_and_exact_budget(self):
        contract = s1.ledger_contract(self.pins)
        self.assertEqual(contract["logical_call_budget"], 24)
        self.assertEqual(contract["reserve_calls"], 16)
        self.assertEqual(contract["response_required_fresh_fields"]["provider_calls"], 1)
        self.assertFalse(contract["response_required_fresh_fields"]["cache_hit"])

    def test_source_has_no_network_or_write_primitive(self):
        source = MODULE_PATH.read_text(encoding="utf-8")
        for forbidden in (
            "import requests", "import httpx", "import urllib", "import socket",
            "urlopen(", "fetch(", "write_text(", "write_bytes(", "subprocess",
        ):
            self.assertNotIn(forbidden, source)


class HiveRawTests(unittest.TestCase):
    def test_valid_raw_response_uses_unrounded_scores(self):
        raw = raw_response("task", 0.4500004, flux=0.2999999, deepfake=0.1)
        result = s1.parse_hive_raw(raw)
        self.assertTrue(result["valid"])
        self.assertEqual(result["ai"], 0.4500004)
        self.assertEqual(result["flux_family"], 0.2999999)

    def test_wrong_model_fails(self):
        raw = raw_response("task", 0.2)
        raw["model"] = "wrong"
        self.assertIn("raw model mismatch", s1.parse_hive_raw(raw)["errors"])

    def test_wrong_version_fails(self):
        raw = raw_response("task", 0.2)
        raw["version"] = "2"
        self.assertIn("raw version mismatch", s1.parse_hive_raw(raw)["errors"])

    def test_missing_flux_key_fails_closed(self):
        raw = raw_response("task", 0.2)
        raw["output"][0]["classes"][3]["class"] = "sdxl"
        result = s1.parse_hive_raw(raw)
        self.assertFalse(result["valid"])
        self.assertTrue(any("no Flux/AuraFlow" in error for error in result["errors"]))

    def test_auraflow_key_satisfies_flux_family_requirement(self):
        raw = raw_response("task", 0.2, flux=0.27)
        raw["output"][0]["classes"][3]["class"] = "AuraFlow-v1"
        result = s1.parse_hive_raw(raw)
        self.assertTrue(result["valid"])
        self.assertEqual(result["flux_family"], 0.27)

    def test_ai_head_sum_mismatch_fails(self):
        raw = raw_response("task", 0.2)
        raw["output"][0]["classes"][0]["value"] = 0.7
        self.assertTrue(any("ai_generated + not_ai_generated" in error for error in s1.parse_hive_raw(raw)["errors"]))

    def test_source_sum_mismatch_fails(self):
        raw = raw_response("task", 0.2)
        raw["output"][0]["classes"][4]["value"] = 0.5
        self.assertTrue(any("source-family scores" in error for error in s1.parse_hive_raw(raw)["errors"]))

    def test_duplicate_class_fails(self):
        raw = raw_response("task", 0.2)
        raw["output"][0]["classes"].append({"class": "flux-schnell", "value": 0.0})
        self.assertTrue(any("duplicated" in error for error in s1.parse_hive_raw(raw)["errors"]))

    def test_nonfinite_class_fails(self):
        raw = raw_response("task", 0.2)
        raw["output"][0]["classes"][1]["value"] = math.nan
        self.assertFalse(s1.parse_hive_raw(raw)["valid"])

    def test_trained_algorithmic_media_is_reported_and_denied(self):
        raw = raw_response("task", 0.2)
        raw["output"][0]["algorithmic_tags"] = {
            "c2pa": {"actions_digital_source_type": "trainedAlgorithmicMedia"}
        }
        result = s1.parse_hive_raw(raw)
        self.assertTrue(result["valid"])
        self.assertEqual(result["c2pa"]["denylist_matches"], ["trainedAlgorithmicMedia"])

    def test_claim_generator_alone_is_reported_not_denied(self):
        raw = raw_response("task", 0.2)
        raw["output"][0]["algorithmic_tags"] = {
            "c2pa": {"claim_generator": "ordinary-editor", "created": "2026-08-30"}
        }
        result = s1.parse_hive_raw(raw)
        self.assertTrue(result["valid"])
        self.assertTrue(result["c2pa"]["present"])
        self.assertEqual(result["c2pa"]["denylist_matches"], [])

    def test_malformed_c2pa_fails(self):
        raw = raw_response("task", 0.2)
        raw["output"][0]["algorithmic_tags"] = {"c2pa": "bad"}
        self.assertFalse(s1.parse_hive_raw(raw)["valid"])


class LedgerValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pins, _ = s1.expected_file_pins()

    def test_valid_24_call_ledger_passes(self):
        result = s1.validate_ledger(valid_ledger(self.pins), self.pins)
        self.assertTrue(result["all_valid"])
        self.assertEqual(result["valid_file_count"], 24)

    def test_cache_hit_fails_closed(self):
        ledger = valid_ledger(self.pins)
        ledger["calls"][0]["response"]["cache_hit"] = True
        result = s1.validate_ledger(ledger, self.pins)
        self.assertFalse(result["all_valid"])
        self.assertIn("response.cache_hit mismatch", result["files"][0]["errors"])

    def test_zero_provider_calls_fails_closed(self):
        ledger = valid_ledger(self.pins)
        ledger["calls"][0]["response"]["provider_calls"] = 0
        result = s1.validate_ledger(ledger, self.pins)
        self.assertFalse(result["all_valid"])

    def test_retry_two_provider_calls_fails_one_call_rule(self):
        ledger = valid_ledger(self.pins)
        ledger["calls"][0]["response"]["provider_calls"] = 2
        result = s1.validate_ledger(ledger, self.pins)
        self.assertFalse(result["all_valid"])

    def test_reused_task_id_fails_closed(self):
        ledger = valid_ledger(self.pins)
        duplicate = ledger["calls"][0]["task_id"]
        ledger["calls"][1]["task_id"] = duplicate
        ledger["calls"][1]["response"]["raw"]["task_id"] = duplicate
        result = s1.validate_ledger(ledger, self.pins)
        self.assertFalse(result["all_valid"])
        self.assertTrue(any("reused raw task_id" in error for error in result["global_errors"]))

    def test_reused_grade_id_fails_closed(self):
        ledger = valid_ledger(self.pins)
        ledger["calls"][1]["response"]["grade_id"] = ledger["calls"][0]["response"]["grade_id"]
        result = s1.validate_ledger(ledger, self.pins)
        self.assertFalse(result["all_valid"])

    def test_missing_flux_fails_file(self):
        ledger = valid_ledger(self.pins)
        ledger["calls"][0]["response"]["raw"]["output"][0]["classes"][3]["class"] = "sdxl"
        result = s1.validate_ledger(ledger, self.pins)
        self.assertFalse(result["files"][0]["valid"])

    def test_session_usage_must_cover_exactly_1_through_24(self):
        ledger = valid_ledger(self.pins)
        ledger["calls"][-1]["response"]["session_usage"]["vendor_calls"] = 25
        result = s1.validate_ledger(ledger, self.pins)
        self.assertFalse(result["all_valid"])
        self.assertTrue(any("exactly 1..24" in error for error in result["global_errors"]))

    def test_changed_submitted_hash_is_tamper_violation(self):
        ledger = valid_ledger(self.pins)
        ledger["calls"][0]["submitted_sha256"] = "0" * 64
        with self.assertRaises(s1.FreezeViolation):
            s1.validate_ledger(ledger, self.pins)

    def test_changed_file_pin_is_tamper_violation(self):
        ledger = valid_ledger(self.pins)
        ledger["file_pins"][0]["bytes"] += 1
        with self.assertRaises(s1.FreezeViolation):
            s1.validate_ledger(ledger, self.pins)

    def test_missing_call_is_tamper_violation(self):
        ledger = valid_ledger(self.pins)
        ledger["calls"].pop()
        with self.assertRaises(s1.FreezeViolation):
            s1.validate_ledger(ledger, self.pins)

    def test_malformed_response_is_recorded_fail_closed(self):
        ledger = valid_ledger(self.pins)
        ledger["calls"][0]["response"] = {"error": "provider error"}
        result = s1.validate_and_interpret(ledger, self.pins)
        self.assertFalse(result["validation"]["all_valid"])
        self.assertEqual(result["interpretation"]["status"], "FAIL_CLOSED")
        self.assertIsNone(result["interpretation"]["metrics"])

    def test_c2pa_deny_value_fails_eligibility_not_response_integrity(self):
        ledger = valid_ledger(self.pins)
        ledger["calls"][0]["response"]["raw"]["output"][0]["algorithmic_tags"] = {
            "c2pa": {"actions_digital_source_type": "trainedAlgorithmicMedia"}
        }
        result = s1.validate_ledger(ledger, self.pins)
        self.assertTrue(result["files"][0]["valid"])
        self.assertFalse(result["files"][0]["eligible"])
        self.assertFalse(result["files"][0]["threshold_pass"]["c2pa"])


class InterpretationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pins, _ = s1.expected_file_pins()

    def _interpret(self, scores):
        ledger = valid_ledger(self.pins, scores=scores)
        return s1.validate_and_interpret(ledger, self.pins)["interpretation"]

    def test_frozen_six_value_median_is_mean_of_third_and_fourth(self):
        self.assertEqual(s1.frozen_median([6, 1, 4, 3, 5, 2]), 3.5)

    def test_rule_one_and_dead_weight(self):
        result = self._interpret({
            "O1": [0.40] * 6,
            "OR": [0.41] * 6,
            "O2": [0.42] * 6,
            "O5": [0.43] * 6,
        })
        self.assertEqual(result["decisions"]["primary_direction"], "ladder_removal_or_decomposition")
        self.assertEqual(result["decisions"]["resample_action"], "dead_weight")
        self.assertEqual(result["decisions"]["delivered_action"], "none")

    def test_rule_two_decomposes_when_o2_clears(self):
        result = self._interpret({
            "O1": [0.60] * 6,
            "OR": [0.60] * 6,
            "O2": [0.40] * 6,
            "O5": [0.40] * 6,
        })
        self.assertEqual(
            result["decisions"]["primary_direction"],
            "decompose_to_detection_essential_minimum",
        )

    def test_rule_three_pivots_to_wash_and_triggers_abstention(self):
        result = self._interpret({
            "O1": [0.60] * 6,
            "OR": [0.60] * 6,
            "O2": [0.55] * 6,
            "O5": [0.50] * 6,
        })
        self.assertEqual(result["decisions"]["primary_direction"], "pivot_to_wash_policy")
        self.assertEqual(result["decisions"]["delivered_action"], "abstention_review")

    def test_resample_exact_boundary_is_retained(self):
        result = self._interpret({
            "O1": [0.30] * 6,
            "OR": [0.35] * 6,
            "O2": [0.35] * 6,
            "O5": [0.35] * 6,
        })
        self.assertEqual(result["decisions"]["resample_action"], "retain")

    def test_no_candidate_or_production_admission_is_created(self):
        result = self._interpret({stage: [0.2] * 6 for stage in s1.STAGES})
        self.assertFalse(result["decisions"]["candidate_selected"])
        self.assertFalse(result["decisions"]["production_admission"])
        self.assertTrue(result["decisions"]["ar3_holdout_unchanged"])


if __name__ == "__main__":
    unittest.main()
