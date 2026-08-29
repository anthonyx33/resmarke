#!/usr/bin/env python3
"""Deterministic unit tests for the ReMint 1.01 offline validator."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

import round_remint_1_01_validate as validator


class Remint101ValidatorTests(unittest.TestCase):
    def test_delivery_resample_moves_only_the_long_edge(self) -> None:
        source = Image.new("RGB", (2048, 1024), (10, 20, 30))
        output = validator.resample_long_edge(source, 1800)
        self.assertEqual(output.size, (1800, 900))
        self.assertEqual(validator.resample_long_edge(source, 4096).size, source.size)

    def test_camera_identity_requires_replayable_provenance(self) -> None:
        valid = {
            "creator_id": "owner@example.com",
            "executed": {
                "effective_seed": "lab:lab-ctla1",
                "engine_report": {
                    "attempts": [
                        {"rung": 0, "strength": "light"},
                        {"rung": 1, "strength": "balanced", "chosen": True},
                    ]
                },
            },
        }
        replay = validator.camera_replay_identity(valid)
        self.assertEqual(replay.strength, "balanced")
        self.assertEqual(replay.rung_index, 1)
        self.assertEqual(replay.creator_id, "owner@example.com")
        self.assertEqual(replay.seed_extra, "lab:lab-ctla1")

        incomplete = json.loads(validator.ar1.SETTINGS_PATH.read_text(encoding="utf-8"))["jobs"]
        first = next(iter(incomplete.values()))
        with self.assertRaisesRegex(validator.ValidationStop, "engine.attempts"):
            validator.camera_replay_identity(first)

    def test_candidate_tuple_changes_delivery_not_process_cap(self) -> None:
        settings = json.loads(validator.ar1.SETTINGS_PATH.read_text(encoding="utf-8"))["jobs"]
        cfg = validator._candidate_settings(next(iter(settings.values())))
        self.assertEqual(cfg["output_target"], 1800)
        self.assertEqual(cfg["regen_process_cap"], 1536)

    def test_identical_images_produce_identity_metrics(self) -> None:
        y, x = np.mgrid[0:128, 0:128]
        array = np.stack(
            [
                (x * 3 + y * 2) % 256,
                (x * 5 + y * 7) % 256,
                (x * 11 + y * 13) % 256,
            ],
            axis=2,
        ).astype(np.uint8)
        roi = {
            "protected": [[0.1, 0.1, 0.9, 0.9]],
            "texture": [[0.1, 0.1, 0.9, 0.9]],
        }
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source.png"
            output = root / "output.png"
            Image.fromarray(array).save(source)
            Image.fromarray(array).save(output)
            metrics = validator.metric_record(output, source, roi)
        self.assertAlmostEqual(metrics["global"]["h0_energy_ratio"], 1.0, places=12)
        self.assertAlmostEqual(metrics["global"]["h1_energy_ratio"], 1.0, places=12)
        self.assertAlmostEqual(metrics["global"]["h2_energy_ratio"], 1.0, places=12)
        self.assertAlmostEqual(metrics["protected_eatr_absolute_min"], 1.0, places=12)
        self.assertAlmostEqual(metrics["texture_residual"]["luma_rms_255"], 0.0, places=12)

    def test_atomic_writer_refuses_stale_temporary_file(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "record.json"
            target.with_name("record.json.tmp").write_text("occupied", encoding="utf-8")
            with self.assertRaisesRegex(validator.ValidationStop, "temporary output"):
                validator._write_text(target, "new")
            self.assertFalse(target.exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
