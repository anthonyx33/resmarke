"""codec_replay.py — TRUE codec A/B from a FIXED O2 buffer (V11 #3).

Usage:
  python codec_replay.py <O2_buffer.png> [--source O0_source.png]
      [--finish none|standard|strong] [--out-dir DIR] [--jsonl out.jsonl]

Encodes the SAME post-camera, pre-codec buffer to:
    C0 = JPEG q92 4:2:0      C1 = JPEG q97 4:4:4
decodes both, optionally runs the finisher in FIXED mode (calling
apply_quality_finish directly — never the worker's adaptive branch, so no
adaptive decision ever sees the encoded bytes), and reports scale-normalized
metrics vs the O2 buffer (and vs the original source when given) plus the
C0-vs-C1 encode delta energy. Codec is the ONLY independent variable.

Run on #9, #5, #6 first: if the enormous 2B detection swings reproduce
here, codec bytes genuinely matter to the classifier; if they vanish, the
2B result was adaptive-execution change, not codec.
"""

import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from checkpoint_attribution import (  # noqa: E402  (same-dir tool)
    _combine,
    _load,
    _metrics_for,
    _resample_to,
)
from quality_finish import apply_quality_finish  # noqa: E402


def _encode(buf_path, out_path, quality, subsampling):
    img = Image.open(buf_path).convert("RGB")
    img.save(out_path, format="JPEG", quality=quality,
             subsampling=subsampling, optimize=True)
    return out_path


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("o2_buffer")
    ap.add_argument("--source", default=None)
    ap.add_argument("--finish", default="none", choices=["none", "standard", "strong"])
    ap.add_argument("--out-dir", default=None)
    ap.add_argument("--jsonl", default=None)
    args = ap.parse_args()

    out_dir = args.out_dir or os.path.join(os.path.dirname(args.o2_buffer), "codec_replay")
    os.makedirs(out_dir, exist_ok=True)

    o2 = _load(args.o2_buffer)
    c0_path = os.path.join(out_dir, "C0_q92_420.jpg")
    c1_path = os.path.join(out_dir, "C1_q97_444.jpg")
    _encode(args.o2_buffer, c0_path, 92, 2)   # 2 -> 4:2:0
    _encode(args.o2_buffer, c1_path, 97, 0)   # 0 -> 4:4:4

    variants = {"C0_q92_420": c0_path, "C1_q97_444": c1_path}
    if args.finish != "none":
        for name, path in list(variants.items()):
            fpath = os.path.join(out_dir, f"{name}_finished_{args.finish}.jpg")
            rep = apply_quality_finish(
                input_path=path,
                output_path=fpath,
                settings={"quality_finish": {
                    "preset": args.finish, "scale": None,
                    "finish_mode": "template", "material_clean": True,
                }},
                seed_extra="codec-replay",
            )
            if rep.get("applied"):
                variants[f"{name}_fin_{args.finish}"] = fpath

    record = {"o2_buffer": args.o2_buffer, "finish": args.finish, "variants": {}}
    print("Codec replay (reference = O2 post-camera buffer):")
    for name, path in variants.items():
        arr = _load(path)
        m = _combine([_metrics_for(arr, o2)])
        record["variants"][name] = m
        print(f"  {name}: EATR={m['eatr']:.3f} HFTR_H1={m['hftr_H1']:.3f} "
              f"lumaRMS={m['luma_rms_lsb']:.2f}LSB chromaRMS={m['chroma_rms_lsb']:.2f}LSB "
              f"rho1={m['rho1']:.3f} dE76={m['delta_e76']:.2f}")

    if args.source:
        print("Source-relative (scale-normalized vs original):")
        src = _load(args.source)
        for name, path in variants.items():
            arr = _load(path)
            ref = _resample_to(src, arr.shape)
            m = _combine([_metrics_for(arr, ref)])
            record["variants"][name]["source_relative"] = m
            print(f"  {name}: EATR={m['eatr']:.3f} HFTR_H0/H1/H2="
                  f"{m['hftr_H0']:.3f}/{m['hftr_H1']:.3f}/{m['hftr_H2']:.3f}")

    c0 = _load(c0_path)
    c1 = _load(c1_path)
    delta = np.abs(c0 - c1)
    record["encode_delta"] = {
        "luma_lsb": float(np.sqrt(np.mean((0.2126 * delta[..., 0] + 0.7152 * delta[..., 1]
                                           + 0.0722 * delta[..., 2]) ** 2)) * 255.0),
        "chroma_lsb": float(np.sqrt(np.mean(delta[..., 1:3] ** 2)) * 255.0),
    }
    print(f"Encode delta C0-vs-C1: luma={record['encode_delta']['luma_lsb']:.3f}LSB "
          f"chroma={record['encode_delta']['chroma_lsb']:.3f}LSB")

    if args.jsonl:
        with open(args.jsonl, "a") as fh:
            fh.write(json.dumps(record) + "\n")
        print(f"\nJSONL appended: {args.jsonl}")


if __name__ == "__main__":
    main()
