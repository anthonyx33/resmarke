#!/usr/bin/env python3
"""Run Neural Texture Lab across a folder and write a JSONL ledger.

Requires the worker's ComfyUI service to be running with RealESRGAN_x4plus.pth
available in models/upscale_models. Intended for internal Day-1 matrix runs.
"""

import argparse
import json
import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from neural_texture import apply_neural_texture_lab  # noqa: E402
from photo_naturalization import apply_expert_refinement  # noqa: E402


SUPPORTED_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input_dir", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--alphas", nargs="+", type=float, default=[0.30, 0.45, 0.60, 0.80])
    parser.add_argument("--creator-id", default="neural-texture-lab")
    args = parser.parse_args()

    images = [p for p in sorted(args.input_dir.iterdir()) if p.suffix.lower() in SUPPORTED_SUFFIXES]
    if not images:
        raise SystemExit(f"No supported images found in {args.input_dir}")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    ledger_path = args.output_dir / "neural-texture-lab.jsonl"

    with ledger_path.open("w", encoding="utf-8") as ledger:
        for path in images:
            for alpha in args.alphas:
                settings = {
                    "mode": "neural-texture-lab",
                    "intensity": 100,
                    "preserve_straight_lines": True,
                    "techniques": {},
                    "neural_texture": {
                        "alpha": alpha,
                        "model_name": "RealESRGAN_x4plus.pth",
                    },
                }
                tmp_png = args.output_dir / f"{path.stem}-alpha{alpha:.2f}.png"
                report = apply_neural_texture_lab(
                    input_path=path,
                    output_path=tmp_png,
                    creator_id=args.creator_id,
                    settings=settings,
                    seed_extra=f"{path.name}:alpha={alpha:.2f}",
                )

                final = Image.open(tmp_png if report.get("applied") else path).convert("RGB")
                expert_report, save_options = apply_expert_refinement(
                    final,
                    settings,
                    args.creator_id,
                    seed_extra=f"{path.name}:alpha={alpha:.2f}:final",
                )
                out_path = args.output_dir / f"{path.stem}-neural-alpha{alpha:.2f}.jpg"
                final.save(
                    out_path,
                    format="JPEG",
                    quality=save_options.get("jpeg_quality", 92),
                    optimize=True,
                    subsampling=save_options.get("jpeg_subsampling", "4:2:2"),
                )

                row = {
                    "input": str(path),
                    "output": str(out_path),
                    "alpha": alpha,
                    "neural_texture": report,
                    "expert_refinement": expert_report,
                }
                ledger.write(json.dumps(row, sort_keys=True) + "\n")
                status = "applied" if report.get("applied") else f"skipped:{report.get('reason')}"
                print(f"alpha={alpha:.2f} {path.name} -> {out_path.name} {status}")

    print(f"ledger: {ledger_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
