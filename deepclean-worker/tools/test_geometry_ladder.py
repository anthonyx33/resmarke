"""Offline C8 v4.4 build gate for the Phase-A geometry module."""

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
    def test_phase_a_allowlist_and_vector_fixture(self):
        vectors_path = Path(__file__).with_name("geometry_settings_vectors.json")
        vectors = json.loads(vectors_path.read_text(encoding="utf-8"))
        self.assertEqual([row["preset_id"] for row in vectors], list(GEOMETRY_PRESETS))
        for row in vectors:
            geometry = normalize_geometry_settings(row["geometry"], True)
            self.assertEqual(geometry, GEOMETRY_PRESETS[row["preset_id"]])
            self.assertEqual(geometry_preset_id(geometry), row["preset_id"])
            self.assertTrue(row["unseeded_code"].startswith("SEQ-G"))
            self.assertTrue(row["lab_ctla1_code"].startswith("SEQ-G"))

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

    JOINT_SIZES = (
        (1250, 1250), (1250, 703), (703, 1250),
        (1000, 1000), (1000, 562), (562, 1000),
        (800, 800), (800, 450), (450, 800),
    )

    def test_prospective_joint_tuples_keep_the_lanczos_margin_all_caps(self):
        # v4.4 §5 conservative construction: every permitted tuple, including
        # the Phase-B J joints, must hold margin >= LANCZOS4_SUPPORT by
        # construction on ALL resize caps and orientations.  The Phase-A
        # allow-list still rejects these tuples; these fixtures pin the
        # transform math the Phase-B build must reuse.  (The superseded v4.3
        # form under-scaled on 800/1000-cap portrait joints: measured
        # 3.9891-3.9974 px.)
        base = {
            "resample_mode": "affine",
            "resize_target": 1250,
            "tilt_degrees": 0.6,
            "micro_warp": "shift_squash",
        }
        for width, height in self.JOINT_SIZES:
            for tilt in (0.6, 1.2):
                for micro_warp in ("shift", "shift_squash"):
                    with self.subTest(width=width, height=height, tilt=tilt, micro_warp=micro_warp):
                        geometry = {**base, "tilt_degrees": tilt, "micro_warp": micro_warp}
                        _, inverse, _, _ = build_affine_matrices(width, height, geometry)
                        self.assertGreaterEqual(
                            source_coordinate_margin(width, height, inverse),
                            LANCZOS4_SUPPORT,
                        )
                        self.assertEqual(int(diagnostic_mask(width, height, inverse).min()), 255)

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
