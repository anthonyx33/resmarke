"""Offline C8 v4.4 algebra gate for frozen Phase-A and Phase-B geometry."""

from __future__ import annotations

import hashlib
import io
import json
import math
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

import cv2
import numpy as np
from PIL import Image

WORKER_DIR = Path(__file__).resolve().parents[1]
if str(WORKER_DIR) not in sys.path:
    sys.path.insert(0, str(WORKER_DIR))

from geometry_ladder import (  # noqa: E402
    GEOMETRY_PRESETS,
    LANCZOS4_SUPPORT,
    analyze_normalized_box,
    apply_geometry,
    build_affine_matrices,
    diagnostic_mask,
    geometry_preset_id,
    kernel_affected_strips,
    normalize_geometry_settings,
    retained_source_area_fraction,
    source_coordinate_margin,
    transform_normalized_box,
)
from ds_remint_v8_8 import _legacy_delivery_resize, normalize_ds_remint_v8_8_settings  # noqa: E402


PINNED_TILT_MATRICES = {
    (1250, 1250, "geom-r3"): [[0.9831991129352631, -0.010296413412822815, 16.92226414823605], [0.010296413412822815, 0.9831991129352631, 4.062043795620388]],
    (1250, 1250, "geom-r4"): [[0.973111741170141, -0.020383785177944393, 29.521391482873053], [0.020383785177944393, 0.973111741170141, 4.062043795620519]],
    (1250, 703, "geom-r3"): [[0.9704237717059025, -0.010162625461779335, 22.03743610674847], [0.010162625461779335, 0.9704237717059025, 4.034696530347028]],
    (1250, 703, "geom-r4"): [[0.9529882431839676, -0.019962257985717, 36.3655946845988], [0.019962257985717, 0.9529882431839676, 4.034696530347004]],
    (703, 1250, "geom-r3"): [[0.9704237717059025, -0.010162625461779335, 16.72781573210946], [0.010162625461779335, 0.9704237717059025, 14.90327303257928]],
    (703, 1250, "geom-r4"): [[0.9529882431839676, -0.019962257985717, 28.967556754507587], [0.019962257985717, 0.9529882431839676, 22.352089578625534]],
}

PHASE_A_IDS = (
    "geom-r0", "geom-x0", "geom-r1", "geom-r2",
    "geom-r3", "geom-r4", "geom-r5", "geom-r6",
)
PHASE_B_IDS = ("geom-j1", "geom-j2", "geom-j3")
PHASE_B_PINNED_INVERSE_800_SQUARE = {
    "geom-j1": [[0.9683529534097216, -0.020284102784533766, 21.24649417523747], [0.020284102784533766, 0.9683529534097216, 4.839496050394966]],
    "geom-j2": [[0.9783909951141114, -0.01024606108014389, 13.226098853429953], [0.01024606108014389, 0.9783909951141114, 4.8394960503949935]],
    "geom-j3": [[0.9695787166418858, -0.02030977886400786, 20.267059357737782], [0.02030977886400786, 0.9695787166418858, 4.039546045395511]],
}
PHASE_A_PIXEL_SHA256 = {
    "geom-r0": "51f7b3ec57be8ae386b3f3d5a4c0505743ffc0f01042f629aa95a2a4d75535a4",
    "geom-x0": "51f7b3ec57be8ae386b3f3d5a4c0505743ffc0f01042f629aa95a2a4d75535a4",
    "geom-r1": "51f7b3ec57be8ae386b3f3d5a4c0505743ffc0f01042f629aa95a2a4d75535a4",
    "geom-r2": "51f7b3ec57be8ae386b3f3d5a4c0505743ffc0f01042f629aa95a2a4d75535a4",
    "geom-r3": "d51fb349fad7f47cabbd74b5ffe4394ec9a004c3ae629e54750d73b8bca5e9ca",
    "geom-r4": "ac132349efc0f1a133ccabfd7ad55bfaaae9bbcb41a79e1b5876664d7d90c94f",
    "geom-r5": "8d51735363d5ce1a2a143bd52de82965f7c6c2d235401ab266e1258ddd9eec89",
    "geom-r6": "3536f181ac532606b7b0bd01dc196153b0278dd832a896aa2f630765819dbd37",
}
# Frozen round-4d-cam-1/roi-manifest.json boxes consumed by Geometry Phase A.
# Manifest SHA-256: 5b0d73779e2855e5deafff5534d01aca647342e2b21370bf8664f9571ad3d329.
FROZEN_CORPUS_ROIS = {
    "IMG-1": {
        "protected": ((0.65, 0.19, 0.84, 0.61),),
        "smooth": ((0.50, 0.56, 0.63, 0.72),),
        "texture": ((0.10, 0.72, 0.46, 0.92),),
    },
    "IMG-2": {
        "protected": ((0.34, 0.35, 0.48, 0.66),),
        "smooth": ((0.69, 0.13, 0.92, 0.30),),
        "texture": ((0.18, 0.68, 0.34, 0.90),),
    },
    "IMG-3": {
        "protected": ((0.63, 0.24, 0.75, 0.52),),
        "smooth": ((0.37, 0.03, 0.70, 0.17),),
        "texture": ((0.45, 0.72, 0.62, 0.90),),
    },
    "IMG-4": {
        "protected": ((0.68, 0.36, 0.79, 0.59),),
        "smooth": ((0.42, 0.04, 0.72, 0.20),),
        "texture": ((0.52, 0.60, 0.65, 0.75),),
    },
    "IMG-5": {
        "protected": ((0.44, 0.21, 0.56, 0.32),),
        "smooth": ((0.31, 0.04, 0.65, 0.17),),
        "texture": ((0.40, 0.46, 0.64, 0.69),),
    },
    "IMG-6": {
        "protected": ((0.38, 0.18, 0.57, 0.31),),
        "smooth": ((0.31, 0.02, 0.68, 0.14),),
        "texture": ((0.36, 0.48, 0.63, 0.75),),
    },
    "IMG-7": {
        "protected": ((0.44, 0.51, 0.62, 0.68),),
        "smooth": ((0.32, 0.05, 0.68, 0.22),),
        "texture": ((0.53, 0.70, 0.71, 0.83),),
    },
    "IMG-8": {
        "protected": ((0.42, 0.56, 0.82, 0.89),),
        "smooth": ((0.64, 0.05, 0.90, 0.20),),
        "texture": ((0.10, 0.79, 0.38, 0.96),),
    },
    "IMG-9": {
        "protected": ((0.44, 0.69, 0.57, 0.91),),
        "smooth": ((0.63, 0.02, 0.88, 0.16),),
        "texture": ((0.05, 0.58, 0.39, 0.76),),
    },
    "IMG-10": {
        "protected": ((0.69, 0.14, 0.84, 0.31),),
        "smooth": ((0.39, 0.04, 0.63, 0.20),),
        "texture": ((0.60, 0.52, 0.84, 0.77),),
    },
    "IMG-11": {
        "protected": ((0.24, 0.55, 0.46, 0.82),),
        "smooth": ((0.46, 0.04, 0.71, 0.18),),
        "texture": ((0.48, 0.55, 0.80, 0.72),),
    },
}


def pinned_postwash_fixture() -> Image.Image:
    width, height = 127, 83
    y, x = np.indices((height, width), dtype=np.uint16)
    array = np.stack(
        ((3 * x + 5 * y) % 256, (11 * x + 7 * y + 19) % 256, (x * x + y * 13 + 31) % 256),
        axis=2,
    ).astype(np.uint8)
    digest = hashlib.sha256(array.tobytes()).hexdigest()
    if digest != "51f7b3ec57be8ae386b3f3d5a4c0505743ffc0f01042f629aa95a2a4d75535a4":
        raise AssertionError("pinned post-wash fixture drifted")
    return Image.fromarray(array)


def pinned_large_postwash_fixture() -> Image.Image:
    width, height = 1403, 907
    y, x = np.indices((height, width), dtype=np.uint32)
    array = np.stack(
        ((3 * x + 5 * y) % 256, (11 * x + 7 * y + 19) % 256, (x * x + y * 13 + 31) % 256),
        axis=2,
    ).astype(np.uint8)
    digest = hashlib.sha256(array.tobytes()).hexdigest()
    if digest != "e932131aad663d422ce72f83bd2989d27d24d5f2db22fc3e5a36daf8e6fd6238":
        raise AssertionError("pinned large post-wash fixture drifted")
    return Image.fromarray(array)


def encoded_bytes(image: Image.Image) -> bytes:
    output = io.BytesIO()
    image.save(output, format="JPEG", quality=92, subsampling=2)
    return output.getvalue()


class GeometryLadderTests(unittest.TestCase):
    def test_frozen_allowlist_and_vector_fixture(self):
        vectors_path = Path(__file__).with_name("geometry_settings_vectors.json")
        vectors = json.loads(vectors_path.read_text(encoding="utf-8"))
        self.assertEqual([row["preset_id"] for row in vectors], list(GEOMETRY_PRESETS))
        for row in vectors:
            geometry = normalize_geometry_settings(row["geometry"], True)
            self.assertEqual(geometry, GEOMETRY_PRESETS[row["preset_id"]])
            self.assertEqual(geometry_preset_id(geometry), row["preset_id"])
            self.assertTrue(row["unseeded_code"].startswith("SEQ-G"))
            self.assertTrue(row["lab_ctla1_code"].startswith("SEQ-G"))

    def test_phase_b_registry_is_exact_and_all_tuples_are_unique(self):
        expected = {
            "geom-j1": {"resample_mode": "affine", "resize_target": 800, "tilt_degrees": 1.2, "micro_warp": "shift"},
            "geom-j2": {"resample_mode": "affine", "resize_target": 800, "tilt_degrees": 0.6, "micro_warp": "shift"},
            "geom-j3": {"resample_mode": "affine", "resize_target": 800, "tilt_degrees": 1.2, "micro_warp": "none"},
        }
        self.assertEqual(tuple(GEOMETRY_PRESETS)[-3:], PHASE_B_IDS)
        self.assertEqual({key: GEOMETRY_PRESETS[key] for key in PHASE_B_IDS}, expected)
        tuple_keys = {
            (
                value["resample_mode"], value["resize_target"],
                value["tilt_degrees"], value["micro_warp"],
            )
            for value in GEOMETRY_PRESETS.values()
        }
        self.assertEqual(len(tuple_keys), len(GEOMETRY_PRESETS))

    def test_boundary_rejects_partial_arbitrary_extra_and_conflicting_blocks(self):
        base = dict(GEOMETRY_PRESETS["geom-r3"])
        invalid = [
            None,
            {**base, "tilt_degrees": 0.7},
            {**base, "resize_target": 900},
            {**base, "micro_warp": "shift"},
            {**base, "extra": True},
            {key: value for key, value in base.items() if key != "micro_warp"},
            {**base, "resize_target": True},
        ]
        for value in invalid:
            with self.subTest(value=value), self.assertRaises(ValueError):
                normalize_geometry_settings(value, True)
        with self.assertRaises(ValueError):
            normalize_geometry_settings(base, True, output_target=1000)
        with self.assertRaises(ValueError):
            normalize_geometry_settings(base, True, output_target=1250.5)
        self.assertEqual(normalize_geometry_settings(base, True, output_target=1250), base)
        self.assertIsNone(normalize_geometry_settings(None, False))

    def test_worker_boundary_consumes_the_same_closed_tuple_contract(self):
        geometry = dict(GEOMETRY_PRESETS["geom-r0"])
        settings = {
            "mode": "ds-remint-v8.9",
            "ds_remint_v8_9": {"geometry": geometry},
        }
        self.assertEqual(normalize_ds_remint_v8_8_settings(settings)["geometry"], geometry)
        settings["ds_remint_v8_9"]["output_target"] = 1000
        with self.assertRaises(ValueError):
            normalize_ds_remint_v8_8_settings(settings)
        with self.assertRaises(ValueError):
            normalize_ds_remint_v8_8_settings({
                "mode": "ds-remint-v8.8",
                "ds_remint_v8_8": {"geometry": geometry},
            })

    def test_pinned_tilt_matrices_margin_and_coverage(self):
        for (width, height, preset_id), expected in PINNED_TILT_MATRICES.items():
            with self.subTest(width=width, height=height, preset_id=preset_id):
                _, inverse, _, _ = build_affine_matrices(width, height, GEOMETRY_PRESETS[preset_id])
                np.testing.assert_allclose(inverse, np.asarray(expected), rtol=0.0, atol=1e-12)
                self.assertGreaterEqual(source_coordinate_margin(width, height, inverse), LANCZOS4_SUPPORT)
                mask = diagnostic_mask(width, height, inverse)
                self.assertEqual(int(mask.min()), 255)

    def test_identity_shift_and_squash_matrices(self):
        width, height = 1250, 703
        _, identity, _, _ = build_affine_matrices(width, height, GEOMETRY_PRESETS["geom-x0"])
        _, shift, _, _ = build_affine_matrices(width, height, GEOMETRY_PRESETS["geom-r5"])
        _, squash, _, _ = build_affine_matrices(width, height, GEOMETRY_PRESETS["geom-r6"])
        np.testing.assert_array_equal(identity, np.array(((1.0, -0.0, 0.0), (-0.0, 1.0, 0.0))))
        np.testing.assert_allclose(shift, np.array(((1.0, 0.0, 0.5), (0.0, 1.0, 0.3))), atol=2e-14)
        expected_x_translation = (width - 1.0) / 2.0 - ((width - 1.0) / 2.0) / 0.988 + 0.5
        np.testing.assert_allclose(
            squash,
            np.array(((1.0 / 0.988, 0.0, expected_x_translation), (0.0, 1.0, 0.3))),
            atol=2e-14,
        )

    def test_bypass_control_and_identity_semantics_are_byte_exact(self):
        fixture = pinned_postwash_fixture()
        baseline_pixels = fixture.tobytes()
        baseline_jpeg = encoded_bytes(fixture)
        bypass, report = apply_geometry(fixture, GEOMETRY_PRESETS["geom-r0"])
        self.assertIs(bypass, fixture)
        self.assertEqual(report["warp_affine_calls"], 0)
        self.assertEqual(bypass.tobytes(), baseline_pixels)
        self.assertEqual(encoded_bytes(bypass), baseline_jpeg)

        identity, identity_report = apply_geometry(fixture, GEOMETRY_PRESETS["geom-x0"])
        self.assertEqual(identity_report["warp_affine_calls"], 1)
        self.assertEqual(identity.size, fixture.size)
        self.assertEqual(identity.tobytes(), baseline_pixels)

    def test_config_a_and_r0_keep_the_incumbent_resize_bytes(self):
        fixture = pinned_large_postwash_fixture()
        ratio = 1250 / float(max(fixture.size))
        incumbent = fixture.resize(
            (max(1, int(round(fixture.width * ratio))), max(1, int(round(fixture.height * ratio)))),
            Image.Resampling.LANCZOS,
        )
        current_config_a = _legacy_delivery_resize(fixture, 1250)
        r0_resized = _legacy_delivery_resize(fixture, 1250)
        current_r0, report = apply_geometry(r0_resized, GEOMETRY_PRESETS["geom-r0"])
        self.assertEqual(incumbent.size, (1250, 808))
        self.assertEqual(current_config_a.tobytes(), incumbent.tobytes())
        self.assertEqual(current_r0.tobytes(), incumbent.tobytes())
        self.assertEqual(encoded_bytes(current_config_a), encoded_bytes(incumbent))
        self.assertEqual(encoded_bytes(current_r0), encoded_bytes(incumbent))
        self.assertEqual(report["warp_affine_calls"], 0)

    def test_all_affine_arms_are_single_call_dimension_stable_and_deterministic(self):
        fixture = pinned_postwash_fixture()
        for preset_id, geometry in GEOMETRY_PRESETS.items():
            if geometry["resample_mode"] == "bypass":
                continue
            with self.subTest(preset_id=preset_id):
                warp_affine = cv2.warpAffine
                with patch("geometry_ladder.cv2.warpAffine", wraps=warp_affine) as mocked_warp:
                    first, first_report = apply_geometry(fixture, geometry)
                self.assertEqual(mocked_warp.call_count, 1)
                second, second_report = apply_geometry(fixture, geometry)
                self.assertEqual(first.size, fixture.size)
                self.assertEqual(first_report["warp_affine_calls"], 1)
                self.assertEqual(first.tobytes(), second.tobytes())
                self.assertEqual(first_report["inverse_matrix"], second_report["inverse_matrix"])

    def test_phase_a_pixel_goldens_remain_byte_exact(self):
        fixture = pinned_postwash_fixture()
        for preset_id in PHASE_A_IDS:
            with self.subTest(preset_id=preset_id):
                output, _ = apply_geometry(fixture, GEOMETRY_PRESETS[preset_id])
                self.assertEqual(
                    hashlib.sha256(output.tobytes()).hexdigest(),
                    PHASE_A_PIXEL_SHA256[preset_id],
                )

    def test_replicated_kernel_strip_thresholds(self):
        thresholds = {
            "geom-r5": {"horizontal": 6, "vertical": 6},
            "geom-r6": {"horizontal": 14, "vertical": 6},
        }
        for preset_id, limit in thresholds.items():
            _, inverse, _, _ = build_affine_matrices(1250, 703, GEOMETRY_PRESETS[preset_id])
            strips = kernel_affected_strips(diagnostic_mask(1250, 703, inverse))
            self.assertLessEqual(max(strips["left"], strips["right"]), limit["horizontal"])
            self.assertLessEqual(max(strips["top"], strips["bottom"]), limit["vertical"])

    def test_roi_transform_is_plain_clipped_box(self):
        forward, _, _, _ = build_affine_matrices(1250, 703, GEOMETRY_PRESETS["geom-r4"])
        box, inflation = transform_normalized_box((0.2, 0.2, 0.8, 0.8), 1250, 703, forward)
        self.assertTrue(all(0.0 <= value <= 1.0 for value in box))
        self.assertLessEqual(inflation, 1.5)
        analysis = analyze_normalized_box((0.2, 0.2, 0.8, 0.8), 1250, 703, forward)
        self.assertTrue(analysis["valid"])
        self.assertFalse(analysis["clipped"])
        self.assertEqual(analysis["box"], list(box))

    def test_retained_area_matches_registered_square_calibration(self):
        expected = {800: 0.9404953748824313, 1250: 0.9473619595013648}
        for size, retained in expected.items():
            forward, _, _, _ = build_affine_matrices(size, size, GEOMETRY_PRESETS["geom-r4"])
            self.assertAlmostEqual(retained_source_area_fraction(forward), retained, places=14)

    def test_retained_area_r4_passes_the_aspect_safe_floor_on_rectangles(self):
        # v4.3 retired the 0.94 floor: r4 retains 0.9086 on rectangular
        # fixtures, so the frozen gate is retained >= 0.90 (aspect-safe).
        retained_expected = 0.9085850833907536
        for width, height in ((1250, 703), (703, 1250)):
            with self.subTest(width=width, height=height):
                forward, _, _, _ = build_affine_matrices(width, height, GEOMETRY_PRESETS["geom-r4"])
                retained = retained_source_area_fraction(forward)
                self.assertAlmostEqual(retained, retained_expected, places=14)
                self.assertGreaterEqual(retained, 0.90)

    JOINT_SIZES = ((800, 800), (800, 450), (450, 800))

    def test_registered_phase_b_joints_pin_matrices_margin_and_coverage(self):
        for preset_id in PHASE_B_IDS:
            geometry = GEOMETRY_PRESETS[preset_id]
            for width, height in self.JOINT_SIZES:
                with self.subTest(preset_id=preset_id, width=width, height=height):
                    forward, inverse, scale, border_mode = build_affine_matrices(
                        width, height, geometry
                    )
                    self.assertEqual(forward.dtype, np.float64)
                    self.assertEqual(inverse.dtype, np.float64)
                    self.assertGreaterEqual(
                        source_coordinate_margin(width, height, inverse),
                        LANCZOS4_SUPPORT,
                    )
                    self.assertEqual(border_mode, cv2.BORDER_CONSTANT)
                    self.assertEqual(int(diagnostic_mask(width, height, inverse).min()), 255)
                    if (width, height) == (800, 800):
                        np.testing.assert_allclose(
                            inverse,
                            np.asarray(PHASE_B_PINNED_INVERSE_800_SQUARE[preset_id]),
                            rtol=0.0,
                            atol=1e-12,
                        )
                        self.assertLessEqual(scale, 1.05)
                        self.assertGreaterEqual(retained_source_area_fraction(forward), 0.90)
                        for image_id, roi_classes in FROZEN_CORPUS_ROIS.items():
                            for roi_class, boxes in roi_classes.items():
                                for box in boxes:
                                    with self.subTest(
                                        preset_id=preset_id,
                                        image_id=image_id,
                                        roi_class=roi_class,
                                    ):
                                        analysis = analyze_normalized_box(
                                            box, width, height, forward
                                        )
                                        self.assertTrue(analysis["valid"])
                                        if roi_class == "protected":
                                            self.assertFalse(analysis["clipped"])
                                        self.assertLessEqual(analysis["area_ratio"], 1.5)

    def test_v43_joint_formula_underscales_on_small_portrait_regression(self):
        # Pin the measured defect that forced v4.4: the v4.3 form
        # s >= |B·p_k + t|/(half − L) treats the unscaled source-space shift
        # as if divided by s.  On 450x800 @ 1.2deg shift_squash it yields
        # margin 3.9891 < L; the v4.4 form holds >= 4.021998.
        width, height = 450, 800
        tilt = 1.2
        squash = 0.988
        half_x = (width - 1.0) / 2.0
        half_y = (height - 1.0) / 2.0
        theta = math.radians(tilt)
        cosine = math.cos(theta)
        sine = math.sin(theta)
        shift_x, shift_y = 0.5, 0.3
        b00 = cosine / squash
        b01 = sine
        b10 = -sine / squash
        b11 = cosine
        v43_scale = 1.0
        for corner_x in (-half_x, half_x):
            for corner_y in (-half_y, half_y):
                qx = b00 * corner_x + b01 * corner_y + shift_x
                qy = b10 * corner_x + b11 * corner_y + shift_y
                v43_scale = max(
                    v43_scale,
                    abs(qx) / (half_x - LANCZOS4_SUPPORT),
                    abs(qy) / (half_y - LANCZOS4_SUPPORT),
                )
        v43_scale *= 1.0 + 1e-4
        rotation = np.array(((cosine, sine), (-sine, cosine)), dtype=np.float64)
        squash_matrix = np.array(((squash, 0.0), (0.0, 1.0)), dtype=np.float64)
        linear = squash_matrix @ rotation
        center = np.array((half_x, half_y), dtype=np.float64)
        shift = np.array((shift_x, shift_y), dtype=np.float64)
        forward = np.column_stack(
            (v43_scale * linear, center - v43_scale * linear @ (center + shift))
        ).astype(np.float64)
        inverse = cv2.invertAffineTransform(forward).astype(np.float64)
        v43_margin = source_coordinate_margin(width, height, inverse)
        self.assertLess(v43_margin, LANCZOS4_SUPPORT)
        self.assertAlmostEqual(v43_margin, 3.9891, places=3)
        geometry = {"resample_mode": "affine", "resize_target": 800, "tilt_degrees": tilt, "micro_warp": "shift_squash"}
        _, v44_inverse, _, _ = build_affine_matrices(width, height, geometry)
        self.assertGreaterEqual(
            source_coordinate_margin(width, height, v44_inverse), LANCZOS4_SUPPORT
        )

    def test_tiny_tilt_images_fail_closed(self):
        with self.assertRaises(ValueError):
            build_affine_matrices(9, 100, GEOMETRY_PRESETS["geom-r3"])
        with self.assertRaises(ValueError):
            build_affine_matrices(100, 9, GEOMETRY_PRESETS["geom-r4"])


if __name__ == "__main__":
    unittest.main()
