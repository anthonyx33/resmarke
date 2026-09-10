"""Focused C8 v4.5 regression tests for the geometry-matched outer gate."""

from __future__ import annotations

import importlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

import numpy as np
from PIL import Image

WORKER_DIR = Path(__file__).resolve().parents[1]
if str(WORKER_DIR) not in sys.path:
    sys.path.insert(0, str(WORKER_DIR))

from ds_remint_v8_8 import apply_ds_remint_v8_9  # noqa: E402
from geometry_ladder import GEOMETRY_PRESETS, apply_geometry  # noqa: E402
from quality_gate import (  # noqa: E402
    GEOMETRY_REFERENCE_MODE,
    LEGACY_REFERENCE_MODE,
    MIN_OUTPUT_DIMENSION,
    MIN_OUTPUT_VARIANCE,
    MIN_PSNR_DB,
    PRIVATE_GEOMETRY_REFERENCE_KEY,
    pop_quality_reference,
    quality_check,
)


def detailed_image(width: int = 512, height: int = 512) -> Image.Image:
    y, x = np.indices((height, width), dtype=np.uint32)
    checker = ((x // 3 + y // 5) % 2) * 127
    array = np.stack(
        (
            (17 * x + 29 * y + checker) % 256,
            (x * x + 11 * y + 2 * checker) % 256,
            (7 * x + y * y + 3 * checker) % 256,
        ),
        axis=2,
    ).astype(np.uint8)
    return Image.fromarray(array)


def geometry_settings(preset_id: str) -> dict:
    return {
        "mode": "ds-remint-v8.9",
        "ds_remint_v8_9": {
            "engine_mode": "template",
            "pre_regen": False,
            "strength": "light",
            "geometry": dict(GEOMETRY_PRESETS[preset_id]),
            "color_restore": False,
            "iphone_exif": False,
            "metadata_mode": "minimal",
            "min_ssim": 0.0,
        },
    }


def load_worker_without_server_start():
    existing = sys.modules.get("worker")
    if existing is not None:
        return existing
    fake_runpod = types.ModuleType("runpod")
    fake_runpod.serverless = types.SimpleNamespace(start=lambda _config: None)
    fake_requests = types.ModuleType("requests")
    with patch.dict(
        sys.modules, {"runpod": fake_runpod, "requests": fake_requests}
    ), patch.dict(
        os.environ, {"DEEPCLEAN_PRELOAD": "0"}
    ):
        return importlib.import_module("worker")


class GeometryQualityGateTests(unittest.TestCase):
    def test_coordinate_frame_regression_passes_without_lowering_threshold(self):
        source = detailed_image()
        matched, _ = apply_geometry(source, GEOMETRY_PRESETS["geom-r4"])
        with tempfile.TemporaryDirectory() as tmpdir:
            source_path = Path(tmpdir) / "source.png"
            candidate_path = Path(tmpdir) / "candidate.png"
            source.save(source_path, format="PNG")
            matched.save(candidate_path, format="PNG")

            legacy = quality_check(source_path, candidate_path)
            corrected = quality_check(
                source_path,
                candidate_path,
                matched_reference=matched,
                geometry_reference_required=True,
            )

        self.assertLess(legacy["psnr"], MIN_PSNR_DB)
        self.assertFalse(legacy["ok"])
        self.assertEqual(legacy["reason"], "Output drift exceeded quality gate.")
        self.assertGreaterEqual(corrected["psnr"], MIN_PSNR_DB)
        self.assertTrue(corrected["ok"])
        self.assertEqual(corrected["reference_mode"], GEOMETRY_REFERENCE_MODE)
        self.assertEqual(corrected["min_psnr_db"], 18.0)

    def test_real_damage_against_matched_reference_still_fails(self):
        matched = detailed_image()
        damaged = Image.fromarray(255 - np.asarray(matched))
        with tempfile.TemporaryDirectory() as tmpdir:
            source_path = Path(tmpdir) / "source.png"
            candidate_path = Path(tmpdir) / "damaged.png"
            matched.save(source_path, format="PNG")
            damaged.save(candidate_path, format="PNG")
            result = quality_check(
                source_path,
                candidate_path,
                matched_reference=matched,
                geometry_reference_required=True,
            )

        self.assertGreaterEqual(result["variance"], MIN_OUTPUT_VARIANCE)
        self.assertLess(result["psnr"], MIN_PSNR_DB)
        self.assertFalse(result["ok"])
        self.assertEqual(result["reason"], "Output drift exceeded quality gate.")

    def test_blank_and_small_outputs_fail_in_both_reference_modes(self):
        source = detailed_image(300, 300)
        blank = Image.new("RGB", source.size, (0, 0, 0))
        small = detailed_image(128, 300)
        with tempfile.TemporaryDirectory() as tmpdir:
            source_path = Path(tmpdir) / "source.png"
            blank_path = Path(tmpdir) / "blank.png"
            small_path = Path(tmpdir) / "small.png"
            source.save(source_path, format="PNG")
            blank.save(blank_path, format="PNG")
            small.save(small_path, format="PNG")

            for required in (False, True):
                with self.subTest(gate="blank", geometry=required):
                    result = quality_check(
                        source_path,
                        blank_path,
                        matched_reference=source if required else None,
                        geometry_reference_required=required,
                    )
                    self.assertFalse(result["ok"])
                    self.assertEqual(result["reason"], "Output appears blank.")
                with self.subTest(gate="dimensions", geometry=required):
                    result = quality_check(
                        small_path,
                        small_path,
                        matched_reference=small if required else None,
                        geometry_reference_required=required,
                    )
                    self.assertFalse(result["ok"])
                    self.assertEqual(result["reason"], "Output image is too small.")

        self.assertEqual(MIN_OUTPUT_DIMENSION, 256)
        self.assertEqual(MIN_OUTPUT_VARIANCE, 12.0)

    def test_missing_malformed_and_dimension_mismatched_references_fail_closed(self):
        output = detailed_image(300, 300)
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "output.png"
            output.save(path, format="PNG")
            cases = (
                (None, "Geometry-matched quality reference is missing or malformed."),
                (np.asarray(output), "Geometry-matched quality reference is missing or malformed."),
                (
                    detailed_image(301, 300),
                    "Geometry-matched quality reference dimensions do not match output.",
                ),
            )
            for reference, reason in cases:
                with self.subTest(reason=reason):
                    result = quality_check(
                        path,
                        path,
                        matched_reference=reference,
                        geometry_reference_required=True,
                    )
                    self.assertFalse(result["ok"])
                    self.assertEqual(result["reason"], reason)
                    self.assertEqual(result["reference_mode"], GEOMETRY_REFERENCE_MODE)

    def test_pipeline_returns_exact_pre_camera_reference_and_one_transform(self):
        source = detailed_image(320, 288)
        observed_references = []
        geometry_outputs = []

        def camera_passthrough(reference, *_args, **_kwargs):
            observed_references.append(reference)
            return reference.copy(), {"test_passthrough": True}

        def tracked_geometry(image, geometry):
            result = apply_geometry(image, geometry)
            geometry_outputs.append(result[0])
            return result

        with tempfile.TemporaryDirectory() as tmpdir:
            source_path = Path(tmpdir) / "source.png"
            output_path = Path(tmpdir) / "output.jpg"
            source.save(source_path, format="PNG")
            with patch(
                "ds_remint_v8_8._v88_candidate", side_effect=camera_passthrough
            ), patch(
                "ds_remint_v8_8.apply_geometry", side_effect=tracked_geometry
            ) as geometry_call:
                report = apply_ds_remint_v8_9(
                    source_path,
                    output_path,
                    creator_id="v45-reference-identity",
                    settings=geometry_settings("geom-r3"),
                )

        private_reference = report[PRIVATE_GEOMETRY_REFERENCE_KEY]
        self.assertEqual(geometry_call.call_count, 1)
        self.assertEqual(report["layers"]["geometry"]["warp_affine_calls"], 1)
        self.assertIs(private_reference, geometry_outputs[0])
        self.assertIs(private_reference, observed_references[0])

    def test_r0_pipeline_returns_post_resize_reference_with_zero_transforms(self):
        source = detailed_image(320, 288)
        observed_references = []

        def camera_passthrough(reference, *_args, **_kwargs):
            observed_references.append(reference)
            return reference.copy(), {"test_passthrough": True}

        with tempfile.TemporaryDirectory() as tmpdir:
            source_path = Path(tmpdir) / "source.png"
            output_path = Path(tmpdir) / "output.jpg"
            source.save(source_path, format="PNG")
            with patch(
                "ds_remint_v8_8._v88_candidate", side_effect=camera_passthrough
            ), patch("ds_remint_v8_8.apply_geometry") as geometry_call:
                report = apply_ds_remint_v8_9(
                    source_path,
                    output_path,
                    creator_id="v45-r0-reference",
                    settings=geometry_settings("geom-r0"),
                )

        private_reference = report[PRIVATE_GEOMETRY_REFERENCE_KEY]
        self.assertEqual(geometry_call.call_count, 0)
        self.assertEqual(report["layers"]["geometry"]["warp_affine_calls"], 0)
        self.assertIs(private_reference, observed_references[0])

    def test_private_reference_is_consumed_before_public_serialization(self):
        reference = detailed_image(300, 300)
        report = {
            "settings": {"geometry": dict(GEOMETRY_PRESETS["geom-r3"])},
            PRIVATE_GEOMETRY_REFERENCE_KEY: reference,
            "layers": {},
        }
        consumed, required = pop_quality_reference(report)
        self.assertIs(consumed, reference)
        self.assertTrue(required)
        self.assertNotIn(PRIVATE_GEOMETRY_REFERENCE_KEY, report)
        json.dumps(report)

    def test_non_geometry_jobs_keep_legacy_source_resize_selection_and_outcome(self):
        source = detailed_image(600, 450)
        legacy_reference = source.resize((400, 300), Image.Resampling.LANCZOS)
        ignored_private_value = detailed_image(400, 300)
        report = {"settings": {}, PRIVATE_GEOMETRY_REFERENCE_KEY: ignored_private_value}
        consumed, required = pop_quality_reference(report)
        self.assertIs(consumed, ignored_private_value)
        self.assertFalse(required)
        self.assertNotIn(PRIVATE_GEOMETRY_REFERENCE_KEY, report)

        with tempfile.TemporaryDirectory() as tmpdir:
            source_path = Path(tmpdir) / "source.png"
            output_path = Path(tmpdir) / "output.png"
            source.save(source_path, format="PNG")
            legacy_reference.save(output_path, format="PNG")
            result = quality_check(
                source_path,
                output_path,
                matched_reference=ignored_private_value,
                geometry_reference_required=required,
            )

        self.assertTrue(result["ok"])
        self.assertEqual(result["psnr"], 99.0)
        self.assertEqual(result["reference_mode"], LEGACY_REFERENCE_MODE)

    def test_worker_passes_exact_reference_and_never_serializes_it(self):
        worker = load_worker_without_server_start()
        source = detailed_image(300, 300)
        matched_reference = source.copy()
        public_bodies = []
        quality_arguments = {}

        def fake_download(_url, path):
            source.save(path, format="PNG")

        def fake_engine(**kwargs):
            matched_reference.save(kwargs["output_path"], format="PNG")
            return {
                "settings": {"geometry": dict(GEOMETRY_PRESETS["geom-r3"])},
                PRIVATE_GEOMETRY_REFERENCE_KEY: matched_reference,
                "layers": {},
                "checkpoint_errors": [],
            }

        def fake_quality(input_path, output_path, **kwargs):
            quality_arguments.update(kwargs)
            return {
                "ok": True,
                "reference_mode": GEOMETRY_REFERENCE_MODE,
                "psnr": 99.0,
                "variance": float(np.var(np.asarray(matched_reference))),
                "min_psnr_db": 18.0,
            }

        def fake_finalize(cleaned_path, output_path, **_kwargs):
            shutil.copyfile(cleaned_path, output_path)
            return {
                "photo_naturalization": {"enabled": False},
                "expert_refinement": {"applied": False},
            }

        payload = {
            "job_id": "v45-worker-handoff",
            "webhook_url": "https://example.invalid/webhook",
            "webhook_secret": "test-secret",
            "input_url": "https://example.invalid/input.png",
            "input_path": "incoming/input.png",
            "output_path": "outgoing/output.jpg",
            "profile": "standard",
            "output_mode": "stripped",
            "expert_refinement": geometry_settings("geom-r3"),
        }
        with patch.object(worker, "download", side_effect=fake_download), patch.object(
            worker, "identify_image", return_value={}
        ), patch.object(
            worker, "apply_ds_remint_v8_9", side_effect=fake_engine
        ), patch.object(
            worker, "make_detector", return_value=None
        ), patch.object(
            worker, "quality_check", side_effect=fake_quality
        ), patch.object(
            worker, "finalize_output", side_effect=fake_finalize
        ), patch.object(
            worker, "upload_output"
        ), patch.object(
            worker, "delete_storage_object"
        ), patch.object(
            worker, "notify", side_effect=lambda _url, _secret, body: public_bodies.append(body)
        ):
            result = worker.handler({"input": payload})

        self.assertTrue(result["ok"])
        self.assertIs(quality_arguments["matched_reference"], matched_reference)
        self.assertTrue(quality_arguments["geometry_reference_required"])
        public_engine = public_bodies[-1]["report"]["engine"]
        self.assertNotIn(PRIVATE_GEOMETRY_REFERENCE_KEY, public_engine)
        json.dumps(worker._json_safe(public_bodies[-1]))


if __name__ == "__main__":
    unittest.main()
