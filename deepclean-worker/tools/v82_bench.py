#!/usr/bin/env python3
"""V8.2 benchmark: corpus runner + manual-grader ledger + config ranking.

You already grade TruthScan and Hive manually. This tool turns those numbers
into optimization data:

  1. Runs the V8.2 (or V8.1) pipeline locally in template mode for every
     requested config (quality floor x metadata mode) and writes one candidate
     JPEG per config.
  2. Reads `scores.json` -- your manual grader verdicts keyed by output
     filename -- and joins them with the QC metrics.
  3. Ranks: per image, the config with the LOWEST ensemble-max score wins
     (quality breaks ties); across the corpus, reports which config wins most.

Usage:
    python3 tools/v82_bench.py /path/to/washed /path/to/out --scores scores.json

    # Full matrix (floors x metadata) with a V8.1 control:
    python3 tools/v82_bench.py washed/ out/ --scores scores.json \\
        --mode v8.2 --floors balanced,strong --metadata device,minimal \\
        --control v8.1-balanced

scores.json shape (keyed by the OUTPUT filename this tool writes):
    {
      "portrait__v82__balanced__device.jpg": {"truthscan": 95, "hive": 62, "sightengine": 17.2}
    }

Local runs need no GPU: the wash is skipped (input dir holds washed frames)
and the restore is classical Lanczos. On the worker image, add --pre-regen
and --neural to exercise the full pipeline.
"""

import argparse
import json
import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ds_remint_v7 import apply_ds_remint_v8_1, apply_ds_remint_v8_2  # noqa: E402
from neural_texture import compare_images  # noqa: E402

SUPPORTED_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}
FLOORS = ["studio", "balanced", "strong"]
METADATA_MODES = ["device", "minimal"]


def read_json(path):
    if path is None:
        return {}
    if not path.exists():
        print(f"warning: scores file missing: {path}", file=sys.stderr)
        return {}
    try:
        with path.open(encoding="utf-8") as handle:
            return json.load(handle)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"invalid scores json: {exc}")


def run_config(mode, floor, metadata, input_path, out_jpg, args, creator_id, seed_extra):
    if mode == "v8.1":
        settings = {
            "mode": "ds-remint-v8.1",
            "ds_remint_v8_1": {
                "engine_mode": "template",
                "pre_regen": bool(args.pre_regen),
                "quality_floor": floor,
                "metadata_mode": metadata,
                "iphone_exif": metadata == "device",
                "template_preset": "balanced",
            },
        }
        report = apply_ds_remint_v8_1(
            input_path=str(input_path), output_path=str(out_jpg),
            creator_id=creator_id, settings=settings, seed_extra=seed_extra,
        )
    else:
        settings = {
            "mode": "ds-remint-v8.2",
            "ds_remint_v8_2": {
                "engine_mode": "template",
                "pre_regen": bool(args.pre_regen),
                "quality_floor": floor,
                "metadata_mode": metadata,
                "iphone_exif": metadata == "device",
                "restore_engine": "neural" if args.neural else "classical",
            },
        }
        report = apply_ds_remint_v8_2(
            input_path=str(input_path), output_path=str(out_jpg),
            creator_id=creator_id, settings=settings, seed_extra=seed_extra,
        )
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input_dir", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--scores", type=Path, help="Manual grader verdicts keyed by output filename.")
    parser.add_argument("--mode", choices=["v8.2", "v8.1"], default="v8.2")
    parser.add_argument("--floors", default="balanced,strong", help="Comma list from studio,balanced,strong.")
    parser.add_argument("--metadata", default="device,minimal", help="Comma list from device,minimal.")
    parser.add_argument("--control", choices=["v8.1-balanced"], default=None,
                        help="Optional control config appended to the matrix.")
    parser.add_argument("--pre-regen", action="store_true",
                        help="Run the ComfyUI wash (worker image only).")
    parser.add_argument("--neural", action="store_true",
                        help="Neural restore (worker image only); default classical for local runs.")
    parser.add_argument("--creator-id", default="v82-bench")
    parser.add_argument("--no-skip", action="store_true", help="Re-run configs whose output already exists.")
    args = parser.parse_args()

    images = [p for p in sorted(args.input_dir.iterdir()) if p.suffix.lower() in SUPPORTED_SUFFIXES]
    if not images:
        raise SystemExit(f"No supported images found in {args.input_dir}")
    floors = [f for f in args.floors.split(",") if f in FLOORS] or ["balanced"]
    metas = [m for m in args.metadata.split(",") if m in METADATA_MODES] or ["device"]

    args.output_dir.mkdir(parents=True, exist_ok=True)
    scores = read_json(args.scores)
    ledger_path = args.output_dir / "v82-bench.jsonl"
    rows = []

    with ledger_path.open("w", encoding="utf-8") as ledger:
        for image in images:
            source = Image.open(image).convert("RGB")
            configs = [(args.mode, f, m) for f in floors for m in metas]
            if args.control == "v8.1-balanced":
                configs.append(("v8.1", "balanced", "device"))
            for mode, floor, meta in configs:
                stem = f"{image.stem}__{mode}__{floor}__{meta}"
                out_jpg = args.output_dir / f"{stem}.jpg"
                if out_jpg.exists() and not args.no_skip:
                    report = {"skipped": True, "pipeline": mode}
                else:
                    report = run_config(mode, floor, meta, image, out_jpg, args, args.creator_id, stem)
                final = Image.open(out_jpg).convert("RGB") if out_jpg.exists() else source
                metrics = compare_images(source, final)
                verdicts = scores.get(out_jpg.name, scores.get(stem, {}))
                row = {
                    "input": image.name,
                    "config": f"{mode}__{floor}__{meta}",
                    "output": out_jpg.name,
                    "ssim": metrics.get("ssim_luma_window11_mean"),
                    "psnr": metrics.get("psnr"),
                    "manual_scores": verdicts,
                    "ensemble_max": max(verdicts.values()) if verdicts else None,
                    "report_pipeline": report.get("pipeline"),
                }
                rows.append(row)
                ledger.write(json.dumps(row, sort_keys=True, default=str) + "\n")
                print(f"{image.name} {row['config']:24s} ssim={row['ssim']:.3f} "
                      f"max={row['ensemble_max'] if row['ensemble_max'] is not None else '?'}")

    # --- ranking -------------------------------------------------------------
    print("\n=== per-image winner (lowest ensemble-max; quality breaks ties) ===")
    scored = [r for r in rows if r["ensemble_max"] is not None]
    wins: dict[str, int] = {}
    for image in {r["input"] for r in scored}:
        candidates = [r for r in scored if r["input"] == image]
        candidates.sort(key=lambda r: (r["ensemble_max"], -r["ssim"]))
        best = candidates[0]
        wins[best["config"]] = wins.get(best["config"], 0) + 1
        runner = candidates[1]["config"] if len(candidates) > 1 else "-"
        print(f"{image:32s} -> {best['config']:24s} max={best['ensemble_max']} "
              f"(2nd: {runner})")
    if wins:
        print("\n=== config wins across corpus ===")
        for config, count in sorted(wins.items(), key=lambda item: -item[1]):
            print(f"{config:24s} {count}")
    print(f"\nledger: {ledger_path}")
    print("Add/update scores.json with your manual TruthScan/Hive/Sightengine "
          "numbers keyed by output filename, then re-run: the runner skips "
          "existing outputs and only re-ranks.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
