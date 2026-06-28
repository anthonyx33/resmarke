#!/usr/bin/env python3
"""Max Optimised Re Mint harness: run apply_max_optimised_remint across a
folder and write a JSONL ledger keyed for side-by-side comparison against the
original and against Max Mint / Max ReMint outputs (same pattern as
max_remint_harness.py).

Usage:
    python3 tools/max_optimised_remint_harness.py \\
        /path/to/inputs /path/to/out_optimised \\
        --preset balanced

Then compare original vs Max Mint vs Max ReMint vs Max Optimised Re Mint on the
SAME images. The quality bar is: Max Optimised should keep the highest PSNR/SSIM
vs the original of any profile that still clears the identify oracle, and the
visual eyeball test (faces/text/detail preserved, not grainy).

Optional --detector-scores joins an external JSON keyed by filename for the
deep-detector read (production detector calls live outside the worker, same as
the other harnesses).
"""

import argparse
import json
import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from content_repair import evaluate_detector_gate  # noqa: E402
from max_optimised_remint import apply_max_optimised_remint  # noqa: E402
from neural_texture import compare_images  # noqa: E402


SUPPORTED_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input_dir", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--creator-id", default="max-opt-remint-harness")
    parser.add_argument("--preset", choices=["conservative", "balanced", "aggressive"], default="balanced")
    parser.add_argument("--adaptive-level", type=int, default=None, help="Override purification adaptive_level (3-6).")
    parser.add_argument("--min-psnr-db", type=float, default=None, help="Override the quality gate PSNR floor.")
    parser.add_argument("--no-skip-processed", action="store_true", help="Disable idempotent skip-if-processed.")
    parser.add_argument(
        "--detector-scores",
        type=Path,
        help="Optional JSON keyed by input/output filename/path with numeric detector score fields.",
    )
    args = parser.parse_args()

    images = [p for p in sorted(args.input_dir.iterdir()) if p.suffix.lower() in SUPPORTED_SUFFIXES]
    if not images:
        raise SystemExit(f"No supported images found in {args.input_dir}")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    ledger_path = args.output_dir / "max-optimised-remint.jsonl"
    detector_scores = read_json(args.detector_scores)

    with ledger_path.open("w", encoding="utf-8") as ledger:
        for path in images:
            out_png = args.output_dir / f"{path.stem}-max-opt-remint.png"
            settings = {
                "mode": "max-optimised-remint",
                "max_optimised_remint": {
                    "preset": args.preset,
                    "skip_if_processed": not args.no_skip_processed,
                },
            }
            if args.adaptive_level is not None:
                settings["max_optimised_remint"]["adaptive_level"] = args.adaptive_level
            if args.min_psnr_db is not None:
                settings["max_optimised_remint"]["min_psnr_db"] = args.min_psnr_db

            source = Image.open(path).convert("RGB")
            report = apply_max_optimised_remint(
                input_path=str(path),
                output_path=str(out_png),
                creator_id=args.creator_id,
                settings=settings,
                seed_extra=f"{path.name}:max-opt-remint",
            )

            output_scores = lookup_record(detector_scores, out_png)
            input_scores = lookup_record(detector_scores, path)
            gate = evaluate_detector_gate(input_scores, output_scores)

            final = Image.open(out_png).convert("RGB") if report.get("applied") else source
            row = {
                "input": str(path),
                "output": str(out_png),
                "preset": args.preset,
                "settings": report.get("settings"),
                "max_optimised_remint": report,
                "final_metrics": compare_images(source, final),
                "detector_scores": {"input": input_scores, "output": output_scores},
                "detector_gate": gate,
            }
            ledger.write(json.dumps(row, sort_keys=True) + "\n")

            qg = report.get("quality_gates", {})
            oracle = report.get("oracle", {})
            metrics = qg.get("metrics", {})
            psnr = metrics.get("psnr") if isinstance(metrics, dict) else None
            psnr_text = f"{psnr:.2f}" if isinstance(psnr, (int, float)) else "?"
            status = "applied" if report.get("applied") else f"skipped:{qg.get('reason', 'not_applied')}"
            print(
                f"{path.name} -> {out_png.name} {status}; "
                f"psnr={psnr_text} "
                f"meta_sparkle={oracle.get('metadata_sparkle')} "
                f"ship_original={gate.get('ship_original')}"
            )

    print(f"ledger: {ledger_path}")
    return 0


def read_json(path):
    if not path:
        return {}
    with path.open("r", encoding="utf-8") as file_handle:
        return json.load(file_handle)


def lookup_record(records, path):
    if not isinstance(records, dict):
        return None
    for key in (str(path), str(path.resolve()), path.name, path.stem):
        value = records.get(key)
        if isinstance(value, dict):
            return value
    return None


if __name__ == "__main__":
    raise SystemExit(main())
