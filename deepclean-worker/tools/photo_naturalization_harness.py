#!/usr/bin/env python3
"""Apply Photo Naturalization profiles to a folder of cleaned images.

Use this on the 8-image acceptance set after DeepClean regeneration. It writes
Standard/Standard+/Strong/Max naturalized JPEGs plus a small JSONL metrics file for review.
"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from photo_naturalization import PHOTO_NATURALIZATION_PROFILES, apply_photo_naturalization  # noqa: E402


SUPPORTED_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input_dir", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument(
        "--profiles",
        nargs="+",
        default=["standard", "standard-plus", "strong", "max", "max-jitter", "optimised"],
    )
    parser.add_argument("--creator-id", default="acceptance-set")
    args = parser.parse_args()

    images = [p for p in sorted(args.input_dir.iterdir()) if p.suffix.lower() in SUPPORTED_SUFFIXES]
    if not images:
        raise SystemExit(f"No supported images found in {args.input_dir}")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    metrics_path = args.output_dir / "photo-naturalization-metrics.jsonl"

    with metrics_path.open("w", encoding="utf-8") as metrics_file:
        for path in images:
            source = Image.open(path).convert("RGB")
            for profile in args.profiles:
                cfg = PHOTO_NATURALIZATION_PROFILES[profile]
                result = source.copy()
                report = apply_photo_naturalization(
                    result,
                    args.creator_id,
                    cfg,
                    seed_extra=f"{path.name}:{profile}",
                )
                out_path = args.output_dir / f"{path.stem}-{profile}.jpg"
                save_kwargs = {
                    "format": "JPEG",
                    "quality": cfg["jpeg_quality"],
                    "optimize": True,
                }
                if cfg.get("jpeg_subsampling"):
                    save_kwargs["subsampling"] = cfg["jpeg_subsampling"]
                result.save(out_path, **save_kwargs)

                row = {
                    "input": str(path),
                    "output": str(out_path),
                    "profile": profile,
                    "report": report,
                    "metrics": compare_images(source, result),
                }
                metrics_file.write(json.dumps(row, sort_keys=True) + "\n")
                print(f"{profile:8s} {path.name} -> {out_path.name} psnr={row['metrics']['psnr']:.2f}")

    print(f"metrics: {metrics_path}")
    return 0


def compare_images(before, after):
    before_arr = np.asarray(before).astype(np.float32)
    after_arr = np.asarray(after).astype(np.float32)
    mse = float(np.mean((before_arr - after_arr) ** 2))
    psnr = 99.0 if mse == 0 else float(20 * np.log10(255.0 / np.sqrt(mse)))
    return {
        "psnr": psnr,
        "mean_abs_delta": float(np.mean(np.abs(before_arr - after_arr))),
        "before_texture": texture_energy(before_arr),
        "after_texture": texture_energy(after_arr),
    }


def texture_energy(arr):
    dx = np.abs(arr[:, 1:, :] - arr[:, :-1, :])
    dy = np.abs(arr[1:, :, :] - arr[:-1, :, :])
    return float((np.mean(dx) + np.mean(dy)) / 2.0)


if __name__ == "__main__":
    raise SystemExit(main())
