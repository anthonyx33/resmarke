#!/usr/bin/env python3
"""Max ReMint harness: run apply_max_remint across a folder, join external
detector scores, run the ship-original-if-worse gate, write a JSONL ledger.

Enables the Phase 0 scored comparison (original vs Max Mint vs Max ReMint) and
the A/B set. Detector scores are joined from an optional JSON file keyed by
input/output filename -- production detector calls live outside the worker,
same pattern as content_repair_lab_harness.

Diagnostic knob: --min-psnr-db overrides the quality gate's PSNR threshold. For
the Phase 0 diagnostic, set it LOW (e.g. 10) so the full FFT-reshaped output is
preserved and scoreable -- otherwise auto-reduce may discard the FFT layer
exactly on the runs where it is doing useful work, and you cannot measure
whether statistical reshaping moves the detector score. Once you have data on
(fft_strength, psnr, detector_delta), recalibrate the gate to a realism +
structural-SSIM bar instead of pixel PSNR.
"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from content_repair import evaluate_detector_gate  # noqa: E402
from max_remint import apply_max_remint  # noqa: E402
from neural_texture import compare_images  # noqa: E402


SUPPORTED_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input_dir", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--creator-id", default="max-remint-harness")
    parser.add_argument("--preset", choices=["conservative", "balanced", "aggressive"], default="balanced")
    parser.add_argument(
        "--detector-scores",
        type=Path,
        help="Optional JSON keyed by input/output filename/path with numeric detector score fields.",
    )
    parser.add_argument(
        "--min-psnr-db",
        type=float,
        default=None,
        help="Override the quality gate PSNR threshold. Set LOW (e.g. 10) for the Phase 0 diagnostic so the full FFT output is scoreable.",
    )
    parser.add_argument("--no-repair", action="store_true", help="Disable Layer C local repair.")
    parser.add_argument("--fft-strength", type=float, default=None, help="Override Layer B FFT strength.")
    args = parser.parse_args()

    images = [p for p in sorted(args.input_dir.iterdir()) if p.suffix.lower() in SUPPORTED_SUFFIXES]
    if not images:
        raise SystemExit(f"No supported images found in {args.input_dir}")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    ledger_path = args.output_dir / "max-remint.jsonl"
    detector_scores = read_json(args.detector_scores)

    with ledger_path.open("w", encoding="utf-8") as ledger:
        for path in images:
            out_png = args.output_dir / f"{path.stem}-max-remint.png"
            settings = {
                "mode": "max-remint",
                "max_remint": {
                    "preset": args.preset,
                    "repair_enabled": not args.no_repair,
                },
            }
            if args.min_psnr_db is not None:
                settings["max_remint"]["min_psnr_db"] = args.min_psnr_db
            if args.fft_strength is not None:
                settings["max_remint"]["fft_strength"] = args.fft_strength

            source = Image.open(path).convert("RGB")
            report = apply_max_remint(
                input_path=str(path),
                output_path=str(out_png),
                creator_id=args.creator_id,
                settings=settings,
                seed_extra=f"{path.name}:max-remint",
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
                "max_remint": report,
                "final_metrics": compare_images(source, final),
                "detector_scores": {
                    "input": input_scores,
                    "output": output_scores,
                },
                "detector_gate": gate,
            }
            ledger.write(json.dumps(row, sort_keys=True) + "\n")
            status = "applied" if report.get("applied") else f"skipped:{report.get('reason')}"
            ar = report.get("quality_gates", {}).get("auto_reduced", False)
            print(
                f"{path.name} -> {out_png.name} {status}; "
                f"auto_reduced={ar}; ship_original={gate.get('ship_original')}"
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
