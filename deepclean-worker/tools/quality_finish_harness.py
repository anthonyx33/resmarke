#!/usr/bin/env python3
"""Local Quality Finish lab harness.

Runs the post-remint selective-restoration ISP over an already-naturalized
image file and writes a JSONL ledger entry with the full QC report. This is
the two-step flow: run your V8.8/V8.9 remint first, then finish the delivered
file here.

Usage:
  python tools/quality_finish_harness.py --image /path/to/reminted.jpg
      [--preset standard] [--scale 1.6 | none] [--out /path/to/out.jpg]
      [--ledger qf_ledger.jsonl]
"""

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from quality_finish import apply_quality_finish  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description="Quality Finish local lab harness")
    parser.add_argument("--image", required=True, help="input image (naturalized file)")
    parser.add_argument("--preset", choices=["conservative", "standard", "strong"], default="standard")
    parser.add_argument("--scale", default="1.6", help="enlargement factor or 'none' for native")
    parser.add_argument("--out", default=None, help="output path (default: <image>-qf.jpg)")
    parser.add_argument("--ledger", default="qf_ledger.jsonl", help="JSONL ledger path")
    args = parser.parse_args()

    src = Path(args.image).resolve()
    if not src.exists():
        raise SystemExit(f"input not found: {src}")

    scale = None if args.scale.strip().lower() == "none" else float(args.scale)
    out_path = Path(args.out).resolve() if args.out else src.with_name(f"{src.stem}-qf.jpg")

    started = time.time()
    report = apply_quality_finish(
        input_path=str(src),
        output_path=str(out_path),
        settings={"mode": "quality-finish", "quality_finish": {"preset": args.preset, "scale": scale}},
        seed_extra=f"harness:{src.name}",
    )

    record = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "input": str(src),
        "output": str(out_path),
        "wall_s": round(time.time() - started, 3),
        **report,
    }
    print(json.dumps(record, indent=2))

    with open(args.ledger, "a") as fh:
        fh.write(json.dumps(record) + "\n")

    if not report.get("applied"):
        print("NOTE: QC gate FAILED -> the ORIGINAL input bytes were shipped unchanged.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
