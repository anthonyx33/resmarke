#!/usr/bin/env python3
"""DS ReMint V7 harness: run apply_ds_remint_v7 across a corpus and write a
JSONL ledger with the full report (rungs, verdicts, gate) per image.

Usage:
    # Local (no GPU): feed pre-washed frames, run re-life + gate + encode.
    python3 tools/ds_remint_v7_harness.py /path/to/washed /path/to/out --no-wash

    # Live detector gating (adaptive mode):
    CX_DETECTOR_URL=... python3 tools/ds_remint_v7_harness.py \\
        /path/to/washed /path/to/out --no-wash --probe-detector

    # Inside the worker image: full pipeline including the ComfyUI wash.
    python3 tools/ds_remint_v7_harness.py /path/to/inputs /path/to/out --wash

The wash flag is OFF by default so the whole gate + re-life chain iterates on
a Mac against pre-washed PNGs exported from a RunPod job.
"""

import argparse
import json
import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from camera_relife import PRESETS  # noqa: E402
from ds_remint_v7 import apply_ds_remint_v7  # noqa: E402
from neural_texture import compare_images  # noqa: E402


SUPPORTED_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}


def read_json(path):
    if path is None:
        return {}
    if not path.exists():
        print(f"warning: detector scores file missing: {path}", file=sys.stderr)
        return {}
    try:
        with path.open(encoding="utf-8") as handle:
            return json.load(handle)
    except json.JSONDecodeError as exc:
        print(f"warning: invalid detector scores file: {exc}", file=sys.stderr)
        return {}


def lookup_record(scores, path):
    if not scores:
        return None
    key = str(path)
    for candidate in (key, Path(key).name, Path(key).stem):
        if candidate in scores:
            return scores[candidate]
    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input_dir", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--creator-id", default="ds-remint-v7-harness")
    parser.add_argument("--template-preset", choices=sorted(PRESETS), default="balanced")
    parser.add_argument("--no-wash", action="store_true", default=True,
                        help="Default: skip the ComfyUI pre-wash (input dir holds washed frames).")
    parser.add_argument("--wash", action="store_true", dest="wash",
                        help="Run the full pipeline including the ComfyUI pre-wash (worker image only).")
    parser.add_argument("--no-iphone-exif", action="store_true",
                        help="Skip the iPhone EXIF pass (keeps local deps minimal).")
    parser.add_argument("--probe-detector", action="store_true",
                        help="Adaptive mode with live CX_DETECTOR_URL probes.")
    parser.add_argument(
        "--detector-scores",
        type=Path,
        help="Optional JSON keyed by filename/path with detector scores (fallback when not probing live).",
    )
    args = parser.parse_args()

    images = [p for p in sorted(args.input_dir.iterdir()) if p.suffix.lower() in SUPPORTED_SUFFIXES]
    if not images:
        raise SystemExit(f"No supported images found in {args.input_dir}")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    ledger_path = args.output_dir / "ds-remint-v7.jsonl"
    detector_scores = read_json(args.detector_scores)

    live_detector = None
    if args.probe_detector:
        from deepclean_detector import make_detector

        live_detector = make_detector()
        if live_detector is None:
            print("warning: --probe-detector set but CX_DETECTOR_URL is not configured; "
                  "falling back to --detector-scores only", file=sys.stderr)

    def fallback_detector(path):
        # Used when live probing is unavailable: returns the external JSON
        # record wrapped in the normalized shape the gate expects.
        record = lookup_record(detector_scores, path)
        if isinstance(record, dict):
            return record
        return {"ok": False, "reason": "no_detector_record", "infra_error": True}

    detector = live_detector or (fallback_detector if detector_scores else None)
    engine_mode = "adaptive" if detector is not None else "template"

    with ledger_path.open("w", encoding="utf-8") as ledger:
        for path in images:
            out_jpg = args.output_dir / f"{path.stem}-v7.jpg"
            settings = {
                "mode": "ds-remint-v7",
                "ds_remint_v7": {
                    "engine_mode": engine_mode,
                    "pre_regen": bool(args.wash),
                    "template_preset": args.template_preset,
                    "iphone_exif": not args.no_iphone_exif,
                },
            }
            report = apply_ds_remint_v7(
                input_path=str(path),
                output_path=str(out_jpg),
                creator_id=args.creator_id,
                settings=settings,
                seed_extra=f"{path.name}:v7",
                detector=detector,
            )

            source = Image.open(path).convert("RGB")
            final = Image.open(out_jpg).convert("RGB") if report.get("applied") else source
            row = {
                "input": str(path),
                "output": str(out_jpg),
                "engine_mode": engine_mode,
                "settings": report.get("settings"),
                "ds_remint_v7": report,
                "final_metrics": compare_images(source, final),
            }
            ledger.write(json.dumps(row, sort_keys=True, default=str) + "\n")

            gate = report.get("detector_gate", {})
            qg = report.get("quality_floor_gate", {})
            base = report.get("input_baseline")
            base_ai = base.get("ai_probability") if isinstance(base, dict) else None
            verdict = gate.get("verdict") or {}
            print(
                f"{path.name} -> {out_jpg.name}; mode={engine_mode}; "
                f"baseline_ai={base_ai}; "
                f"ai={verdict.get('ai')} flux={verdict.get('flux_family')} "
                f"cleared={gate.get('cleared')}; "
                f"rungs={gate.get('rungs_tried', 1)}; "
                f"psnr={qg.get('psnr')} ssim={qg.get('ssim')}"
            )

    print(f"ledger: {ledger_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
