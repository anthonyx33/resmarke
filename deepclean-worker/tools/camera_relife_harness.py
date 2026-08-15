#!/usr/bin/env python3
"""Camera Re-Life harness: run apply_camera_relife across a corpus and write a
JSONL ledger with before/after metrics and (optionally) live detector probes.

Usage:
    python3 tools/camera_relife_harness.py /path/to/inputs /path/to/out \
        --preset balanced

    CX_DETECTOR_URL=... [CX_DETECTOR_KEY=...] \
    python3 tools/camera_relife_harness.py /path/to/inputs /path/to/out \
        --preset strong --probe-detector

The quality bar for V7: re-life must keep the washed frame's content
(SSIM/PSNR vs input) while the detector read on the OUTPUT drops
(ai_probability AND flux-family source score). Compare presets on the SAME
inputs -- ideally inputs are washed frames exported from a RunPod job, but any
image works for pure iteration on the classical chain.

Saves `<stem>-relife.png` (the re-lived pixels) and `<stem>-relife.jpg`
(q94, 4:2:2 -- the delivery-like encode; the detector is probed on THIS file,
because the grader sees the JPEG, not the PNG).
"""

import argparse
import json
import os
import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from camera_relife import PRESETS, apply_camera_relife  # noqa: E402
from neural_texture import compare_images  # noqa: E402


SUPPORTED_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}
JPEG_QUALITY = 94
JPEG_SUBSAMPLING = "4:2:2"


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


def probe(detector, path):
    try:
        return detector(path)
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "reason": f"probe_error: {str(exc)[:200]}", "infra_error": True}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input_dir", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--creator-id", default="camera-relife-harness")
    parser.add_argument("--preset", choices=sorted(PRESETS), default="balanced")
    parser.add_argument("--probe-detector", action="store_true",
                        help="Probe input + output with CX_DETECTOR_URL (env-gated).")
    parser.add_argument(
        "--detector-scores",
        type=Path,
        help="Optional JSON keyed by filename/path with detector scores, same as the other harnesses.",
    )
    args = parser.parse_args()

    images = [p for p in sorted(args.input_dir.iterdir()) if p.suffix.lower() in SUPPORTED_SUFFIXES]
    if not images:
        raise SystemExit(f"No supported images found in {args.input_dir}")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    ledger_path = args.output_dir / "camera-relife.jsonl"
    detector_scores = read_json(args.detector_scores)

    live_detector = None
    if args.probe_detector:
        # Lazy import: requests is only needed when live probing is requested,
        # so plain corpus runs stay dependency-free.
        from deepclean_detector import make_detector

        live_detector = make_detector()
        if live_detector is None:
            print("warning: --probe-detector set but CX_DETECTOR_URL is not configured; "
                  "falling back to --detector-scores only", file=sys.stderr)

    with ledger_path.open("w", encoding="utf-8") as ledger:
        for path in images:
            out_png = args.output_dir / f"{path.stem}-relife.png"
            out_jpg = args.output_dir / f"{path.stem}-relife.jpg"

            source = Image.open(path).convert("RGB")
            settings = {"mode": "camera-relife", "camera_relife": {"preset": args.preset}}
            relifed, report = apply_camera_relife(
                source,
                settings=settings,
                creator_id=args.creator_id,
                seed_extra=f"{path.name}:relife",
            )
            relifed.save(out_png, format="PNG")
            relifed.save(out_jpg, format="JPEG", quality=JPEG_QUALITY,
                         optimize=True, subsampling=JPEG_SUBSAMPLING)

            input_probe = probe(live_detector, path) if live_detector else lookup_record(detector_scores, path)
            output_probe = probe(live_detector, out_jpg) if live_detector else lookup_record(detector_scores, out_jpg)

            row = {
                "input": str(path),
                "output": str(out_jpg),
                "preset": args.preset,
                "settings": report.get("settings"),
                "camera_relife": report,
                "final_metrics": compare_images(source, relifed),
                "detector": {"input": input_probe, "output": output_probe},
            }
            ledger.write(json.dumps(row, sort_keys=True, default=str) + "\n")

            metrics = row["final_metrics"]
            psnr = metrics.get("psnr")
            ssim = metrics.get("ssim_luma_window11_mean")
            psnr_text = f"{psnr:.2f}" if isinstance(psnr, (int, float)) else "?"
            ssim_text = f"{ssim:.3f}" if isinstance(ssim, (int, float)) else "?"

            def compact(p):
                if not isinstance(p, dict):
                    return "-"
                ai = p.get("ai_probability")
                sources = p.get("sources") if isinstance(p.get("sources"), dict) else None
                top = max(sources, key=sources.get) if sources else None
                return f"ai={ai} top={top}"

            print(
                f"{path.name} -> {out_jpg.name}; "
                f"psnr={psnr_text} ssim={ssim_text} "
                f"det_in[{compact(input_probe)}] det_out[{compact(output_probe)}]"
            )

    print(f"ledger: {ledger_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
