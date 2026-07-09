#!/usr/bin/env python3
"""CX Remint harness: run apply_cx_remint across a folder and write a JSONL
ledger for side-by-side comparison against the original and the other Max
profiles (same pattern as max_optimised_remint_harness.py).

The CX Remint quality bar is different from the regen profiles: it INTENTIONALLY
reduces resolution to break the SynthID/diffusion carrier non-generatively, so
PSNR-vs-original-at-full-res is meaningless. This harness reports:
  - output long edge vs source (the resolution retention)
  - matched-resolution PSNR/SSIM (how much the re-acquisition damaged detail
    beyond the intended resize)
  - beats_competitor_free_768 (must always be True)

Usage:
    python3 tools/max_cx_remint_harness.py /path/to/inputs /path/to/out_cx \\
        --quality-floor balanced --engine-mode template

Adaptive gating uses the env-configured detector (deepclean_detector.make_detector);
without CX_DETECTOR_URL set, --engine-mode adaptive degrades to a single run.
"""

import argparse
import json
import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from deepclean_detector import make_detector  # noqa: E402
from max_cx_remint import apply_cx_remint  # noqa: E402
from neural_texture import compare_images  # noqa: E402


SUPPORTED_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input_dir", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--creator-id", default="cx-remint-harness")
    parser.add_argument("--quality-floor", choices=["studio", "high", "balanced", "strong", "floor"],
                        default="balanced")
    parser.add_argument("--engine-mode", choices=["template", "adaptive"], default="template")
    parser.add_argument("--acquisition", choices=["conservative", "balanced", "aggressive"],
                        default="balanced")
    parser.add_argument("--device", default="auto")
    parser.add_argument("--no-iphone-exif", action="store_true")
    args = parser.parse_args()

    images = [p for p in sorted(args.input_dir.iterdir()) if p.suffix.lower() in SUPPORTED_SUFFIXES]
    if not images:
        raise SystemExit(f"No supported images found in {args.input_dir}")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    ledger_path = args.output_dir / "max-cx-remint.jsonl"
    detector = make_detector() if args.engine_mode == "adaptive" else None
    if args.engine_mode == "adaptive" and detector is None:
        print("WARNING: adaptive mode requested but CX_DETECTOR_URL not set; running single pass.")

    with ledger_path.open("w", encoding="utf-8") as ledger:
        for path in images:
            out_jpg = args.output_dir / f"{path.stem}-cx-remint.jpg"
            settings = {
                "mode": "max-cx-remint",
                "max_cx_remint": {
                    "engine_mode": args.engine_mode,
                    "quality_floor": args.quality_floor,
                    "acquisition": args.acquisition,
                    "iphone_exif": not args.no_iphone_exif,
                    "device": args.device,
                },
            }
            source = Image.open(path).convert("RGB")
            report = apply_cx_remint(
                input_path=str(path),
                output_path=str(out_jpg),
                creator_id=args.creator_id,
                settings=settings,
                seed_extra=f"{path.name}:cx-remint",
                detector=detector,
            )

            final = Image.open(out_jpg).convert("RGB")
            matched = compare_images(source.resize(final.size, Image.Resampling.LANCZOS), final)
            row = {
                "input": str(path),
                "output": str(out_jpg),
                "source_size": list(source.size),
                "output_size": list(final.size),
                "resolution_retention": round(max(final.size) / max(source.size), 4),
                "matched_metrics": {"psnr": matched.get("psnr"), "ssim": matched.get("ssim_luma_window11_mean")},
                "report": report,
            }
            ledger.write(json.dumps(row, sort_keys=True) + "\n")

            qfg = report.get("quality_floor_gate", {})
            dg = report.get("detector_gate", {})
            print(
                f"{path.name} -> {out_jpg.name} "
                f"{max(source.size)}->{max(final.size)}px "
                f"ssim={qfg.get('ssim')} psnr={qfg.get('psnr')} "
                f"floor_ok={qfg.get('accepted')} "
                f"detector={'cleared' if dg.get('cleared') else dg.get('evaluated') and 'not_cleared' or 'n/a'} "
                f">768={qfg.get('beats_competitor_free_768')}"
            )

    print(f"ledger: {ledger_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
