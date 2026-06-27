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

from neural_texture import apply_neural_texture_lab, compare_images  # noqa: E402
from photo_naturalization import apply_expert_refinement  # noqa: E402


SUPPORTED_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input_dir", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--alphas", nargs="+", type=float, default=[0.30, 0.45, 0.60, 0.80])
    parser.add_argument("--creator-id", default="neural-texture-lab")
    parser.add_argument(
        "--labels",
        type=Path,
        help=(
            "Optional JSON keyed by input filename/path with content_type, "
            "negative_control, and x4plus_applicable fields."
        ),
    )
    parser.add_argument(
        "--detector-scores",
        type=Path,
        help=(
            "Optional JSON keyed by input/output filename/path. Values should be "
            "detector score objects with numeric fields such as basic_detector_score "
            "or deep_detector_score."
        ),
    )
    parser.add_argument("--negative-control-max-rise", type=float, default=5.0)
    args = parser.parse_args()

    images = [p for p in sorted(args.input_dir.iterdir()) if p.suffix.lower() in SUPPORTED_SUFFIXES]
    if not images:
        raise SystemExit(f"No supported images found in {args.input_dir}")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    ledger_path = args.output_dir / "neural-texture-lab.jsonl"
    labels = read_json(args.labels)
    detector_scores = read_json(args.detector_scores)

    with ledger_path.open("w", encoding="utf-8") as ledger:
        for path in images:
            source = Image.open(path).convert("RGB")
            label = lookup_record(labels, path) or {}
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
                input_scores = lookup_record(detector_scores, path)
                output_scores = lookup_record(detector_scores, out_path)
                score_delta = detector_score_delta(input_scores, output_scores)
                fingerprint_gate = negative_control_gate(
                    bool(label.get("negative_control", False)),
                    score_delta,
                    args.negative_control_max_rise,
                )

                row = {
                    "input": str(path),
                    "output": str(out_path),
                    "alpha": alpha,
                    "content_type": label.get("content_type"),
                    "negative_control": bool(label.get("negative_control", False)),
                    "x4plus_applicable": label.get("x4plus_applicable"),
                    "neural_texture": report,
                    "expert_refinement": expert_report,
                    "final_metrics": compare_images(source, final),
                    "detector_scores": {
                        "input": input_scores,
                        "output": output_scores,
                        "delta": score_delta,
                    },
                    "fingerprint_gate": fingerprint_gate,
                }
                ledger.write(json.dumps(row, sort_keys=True) + "\n")
                status = "applied" if report.get("applied") else f"skipped:{report.get('reason')}"
                print(f"alpha={alpha:.2f} {path.name} -> {out_path.name} {status}")

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
    keys = [
        str(path),
        str(path.resolve()),
        path.name,
        path.stem,
    ]
    for key in keys:
        value = records.get(key)
        if isinstance(value, dict):
            return value
    return None


def detector_score_delta(input_scores, output_scores):
    if not isinstance(input_scores, dict) or not isinstance(output_scores, dict):
        return None
    delta = {}
    for key, before in input_scores.items():
        after = output_scores.get(key)
        if isinstance(before, (int, float)) and isinstance(after, (int, float)):
            delta[key] = float(after) - float(before)
    return delta or None


def negative_control_gate(is_negative_control, score_delta, max_rise):
    if not is_negative_control:
        return {"required": False}
    if not isinstance(score_delta, dict):
        return {
            "required": True,
            "status": "not_scored",
            "max_allowed_rise": max_rise,
        }
    rises = {key: value for key, value in score_delta.items() if value > max_rise}
    return {
        "required": True,
        "status": "fail" if rises else "pass",
        "max_allowed_rise": max_rise,
        "rises": rises,
    }


if __name__ == "__main__":
    raise SystemExit(main())
