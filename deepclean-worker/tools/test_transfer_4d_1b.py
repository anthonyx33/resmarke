#!/usr/bin/env python3
"""Deterministic unit proofs for the frozen 4D-1b replay candidate."""

import sys
import unittest
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

TOOLS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS_DIR))

from transfer_4d_1b import DOSE, WINDOW, _synthesize, build_candidate


def _textured_pair(size=96):
    yy, xx = np.mgrid[:size, :size]
    envelope = ((xx > size // 4) & (xx < 3 * size // 4) &
                (yy > size // 4) & (yy < 3 * size // 4)).astype(np.float64)
    base = 0.50 + envelope * (0.12 * np.sin(xx * 0.42) + 0.08 * np.sin(yy * 0.31))
    chroma = np.stack([base + 0.04, base, base - 0.03], axis=2)
    original = np.rint(np.clip(chroma, 0, 1) * 255).astype(np.uint8)
    blurred = np.asarray(
        Image.fromarray(original).filter(ImageFilter.GaussianBlur(radius=0.8)), dtype=np.uint8
    )
    return original, blurred


class Transfer4D1BTests(unittest.TestCase):
    def test_constants_are_frozen(self):
        self.assertEqual(WINDOW, 15)
        self.assertEqual(DOSE, 0.25)

    def test_geometry_mismatch_rejected(self):
        with self.assertRaises(ValueError):
            build_candidate(np.zeros((32, 32, 3), np.uint8), np.zeros((31, 32, 3), np.uint8))

    def test_small_input_rejected(self):
        with self.assertRaises(ValueError):
            build_candidate(np.zeros((14, 20, 3), np.uint8), np.zeros((14, 20, 3), np.uint8))

    def test_flat_input_fails_closed_without_support(self):
        flat = np.full((48, 48, 3), 127, dtype=np.uint8)
        result = build_candidate(flat, flat)
        self.assertTrue(result.report["fail_closed"])
        self.assertEqual(result.report["stop_reason"], "empty_support")
        self.assertEqual(result.report["support_pixels"], 0)
        np.testing.assert_array_equal(result.rgb, flat)

    def test_synthesis_adds_equal_channel_delta_and_clips_safely(self):
        base = np.array([[[10, 50, 100], [250, 220, 200]]], dtype=np.uint8)
        delta = np.array([[0.02, 0.10]], dtype=np.float64)
        out, capped_fraction = _synthesize(base, delta)
        before_diff = base[0, 0].astype(int) - base[0, 0, 0].astype(int)
        after_diff = out[0, 0].astype(int) - out[0, 0, 0].astype(int)
        np.testing.assert_array_equal(before_diff, after_diff)
        self.assertGreater(capped_fraction, 0.0)
        self.assertLessEqual(int(out.max()), 255)

    def test_textured_support_is_binary_and_data_boundary_is_explicit(self):
        original, blurred = _textured_pair()
        result = build_candidate(original, blurred)
        self.assertEqual(result.support.dtype, np.bool_)
        self.assertGreater(result.report["support_pixels"], 0)
        self.assertEqual(result.report["data_boundary"], ["OR_postresample", "O2_precamera"])

    def test_same_inputs_are_bit_deterministic(self):
        original, blurred = _textured_pair()
        first = build_candidate(original, blurred)
        second = build_candidate(original, blurred)
        np.testing.assert_array_equal(first.rgb, second.rgb)
        np.testing.assert_array_equal(first.support, second.support)
        self.assertEqual(first.report, second.report)


if __name__ == "__main__":
    unittest.main()
