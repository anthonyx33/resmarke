#!/usr/bin/env python3
"""C8 v3 six-variant experiment: one final float buffer, six quantizers.

Produces the diagnostic the consultant specified:
  1. no-dither float -> Q95 (baseline)
  2. no-dither float -> 8-bit PNG
  3. 0.25 LSB shaped dither -> 8-bit PNG
  4. 0.35 LSB shaped dither -> 8-bit PNG
  5. 0.35 LSB dither -> Q95 4:4:4
  6. 0.35 LSB dither -> Q97 4:4:4

If #4 is smooth but #5 bands again, the JPEG encoder is killing the
correction. If #3/#4 still band, test gradient reconstruction instead.

Usage:
  python tools/qf_v3_experiment.py --image /path/to/sky-heavy.jpg
      [--preset standard] [--scale 1.6] [--outdir /tmp/qf-v3-experiment]
"""

import argparse
import io
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from quality_finish import _finish_rgb, _rgb_to_ycbcr, _small_step_fraction, _tiled_noise  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description="C8 v3 six-variant quantization experiment")
    ap.add_argument("--image", required=True)
    ap.add_argument("--preset", default="standard")
    ap.add_argument("--scale", type=float, default=1.6)
    ap.add_argument("--outdir", default="/tmp/qf-v3-experiment")
    args = ap.parse_args()

    img = np.asarray(Image.open(args.image).convert("RGB")).astype(np.uint8)
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    # One float buffer for all variants: pipeline WITHOUT the dither stage.
    out_float, qc, passed = _finish_rgb(
        img, args.preset, args.scale, True, f"exp:{Path(args.image).name}",
        dither=False, return_float=True,
    )
    y, cb, cr = _rgb_to_ycbcr(out_float)
    mask = np.ones(y.shape, dtype=np.float32)

    def quantize_and_index(name, y_in, save_mode, quality=None):
        rgb = np.clip(
            np.stack(
                [y_in + 1.402 * cr, y_in - 0.344136 * cb - 0.714136 * cr, y_in + 1.772 * cb],
                axis=-1,
            ),
            0.0,
            1.0,
        )
        u8 = np.rint(rgb * 255).clip(0, 255).astype(np.uint8)
        buf = io.BytesIO()
        if save_mode == "png":
            Image.fromarray(u8).save(buf, "PNG")
            ext = "png"
        else:
            Image.fromarray(u8).save(buf, "JPEG", quality=quality, subsampling=0)
            ext = "jpg"
        buf.seek(0)
        Image.open(buf).convert("RGB").save(outdir / f"{name}.{ext}")
        buf.seek(0)
        dec = np.asarray(Image.open(buf).convert("RGB")).astype(np.float32) / 255.0
        y_dec = 0.299 * dec[..., 0] + 0.587 * dec[..., 1] + 0.114 * dec[..., 2]
        idx = _small_step_fraction(y_dec, mask)
        print(f"{name:36s} step-frac={idx:.5f}  size={len(buf.getvalue()) // 1024}KB")
        return idx

    d025 = _tiled_noise(y.shape, 64, "exp-025") * (0.25 / 255.0)
    d035 = _tiled_noise(y.shape, 64, "exp-035") * (0.35 / 255.0)

    print(f"pipeline QC passed={passed} rho1={qc['rho1']} (float buffer, no dither)")
    quantize_and_index("1_q95_baseline_no_dither", y, "jpg", 95)
    quantize_and_index("2_8bit_png_no_dither", y, "png")
    quantize_and_index("3_8bit_png_d025", y + d025, "png")
    quantize_and_index("4_8bit_png_d035", y + d035, "png")
    quantize_and_index("5_d035_q95", y + d035, "jpg", 95)
    quantize_and_index("6_d035_q97", y + d035, "jpg", 97)


if __name__ == "__main__":
    main()
