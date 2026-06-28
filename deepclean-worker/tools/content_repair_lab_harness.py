#!/usr/bin/env python3
"""Run Automatic Content Repair Lab v1 across a folder and write a JSONL ledger.

The lab is intentionally one-pass and narrow: text/glyph plus geometry/grid
localization and repair. Detector scores are joined from an optional JSON file
because production detector calls currently live outside the worker.
"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from content_repair import (  # noqa: E402
    apply_content_repair_lab,
    evaluate_detector_gate,
    localize_content_artifacts,
    mask_precision_recall,
    normalize_content_repair_settings,
    render_regions_mask,
)
from neural_texture import compare_images  # noqa: E402
from photo_naturalization import apply_expert_refinement  # noqa: E402


SUPPORTED_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input_dir", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--creator-id", default="content-repair-lab")
    parser.add_argument(
        "--labels",
        type=Path,
        help=(
            "Optional JSON keyed by input filename/path with content_type and "
            "negative_control fields."
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
    parser.add_argument(
        "--manual-mask-dir",
        type=Path,
        help="Optional directory of ground-truth masks named like the input stem.",
    )
    parser.add_argument("--preset", choices=["conservative", "balanced", "aggressive"], default="balanced")
    parser.add_argument(
        "--engine",
        choices=["qwen", "telea"],
        default="qwen",
        help="Repair engine. qwen (default, v2) or telea (offline A/B diagnosis only).",
    )
    parser.add_argument("--negative-control-max-rise", type=float, default=5.0)
    args = parser.parse_args()

    images = [p for p in sorted(args.input_dir.iterdir()) if p.suffix.lower() in SUPPORTED_SUFFIXES]
    if not images:
        raise SystemExit(f"No supported images found in {args.input_dir}")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    ledger_path = args.output_dir / "content-repair-lab.jsonl"
    labels = read_json(args.labels)
    detector_scores = read_json(args.detector_scores)

    with ledger_path.open("w", encoding="utf-8") as ledger:
        for path in images:
            source = Image.open(path).convert("RGB")
            label = lookup_record(labels, path) or {}
            settings = content_repair_settings(args.preset, args.engine)
            cfg = normalize_content_repair_settings(settings)

            candidates, localizer_report = localize_content_artifacts(np.asarray(source), cfg)
            predicted_mask = render_regions_mask(source.size, candidates)
            mask_path = args.output_dir / f"{path.stem}-auto-mask.png"
            predicted_mask.save(mask_path)

            truth_mask_path = find_manual_mask(args.manual_mask_dir, path)
            calibration = None
            if truth_mask_path:
                calibration = mask_precision_recall(predicted_mask, Image.open(truth_mask_path).convert("L"))

            tmp_png = args.output_dir / f"{path.stem}-content-repair.png"
            repair_report = apply_content_repair_lab(
                input_path=path,
                output_path=tmp_png,
                creator_id=args.creator_id,
                settings=settings,
                seed_extra=f"{path.name}:content-repair",
            )

            repaired_path = tmp_png if repair_report.get("applied") else path
            final = Image.open(repaired_path).convert("RGB")
            expert_report, save_options = apply_expert_refinement(
                final,
                settings,
                args.creator_id,
                seed_extra=f"{path.name}:content-repair:final",
            )
            out_path = args.output_dir / f"{path.stem}-content-repair-final.jpg"
            final.save(
                out_path,
                format="JPEG",
                quality=save_options.get("jpeg_quality", 92),
                optimize=True,
                subsampling=save_options.get("jpeg_subsampling", "4:2:2"),
            )

            input_scores = lookup_record(detector_scores, path)
            repair_scores = lookup_record(detector_scores, tmp_png)
            output_scores = lookup_record(detector_scores, out_path)
            input_to_output_delta = detector_score_delta(input_scores, output_scores)
            input_to_repair_delta = detector_score_delta(input_scores, repair_scores)
            # The ship-original-if-worse gate (v2). With the v1 run this would
            # have flagged ship_original=true for deep 96.7->99.6 / stat 59->97,
            # surfacing the failure in the ledger instead of silently shipping it.
            repair_gate = evaluate_detector_gate(input_scores, repair_scores)
            output_gate = evaluate_detector_gate(input_scores, output_scores)
            negative_control_gate = build_negative_control_gate(
                bool(label.get("negative_control", False)),
                len(candidates),
                input_to_output_delta,
                args.negative_control_max_rise,
            )

            row = {
                "input": str(path),
                "output": str(out_path),
                "predicted_mask": str(mask_path),
                "manual_mask": str(truth_mask_path) if truth_mask_path else None,
                "content_type": label.get("content_type"),
                "negative_control": bool(label.get("negative_control", False)),
                "preset": args.preset,
                "settings": repair_report.get("settings"),
                "localizer": localizer_report,
                "localizer_calibration": calibration,
                "regions": repair_report.get("regions", []),
                "content_repair": repair_report,
                "expert_refinement": expert_report,
                "final_metrics": compare_images(source, final),
                "detector_scores": {
                    "input": input_scores,
                    "post_repair": repair_scores,
                    "post_finalize": output_scores,
                    "input_to_repair_delta": input_to_repair_delta,
                    "input_to_output_delta": input_to_output_delta,
                },
                "detector_gate": {
                    "post_repair": repair_gate,
                    "post_finalize": output_gate,
                },
                "fingerprint_gate": negative_control_gate,
                "promotion_checks": promotion_checks(calibration, negative_control_gate),
            }
            ledger.write(json.dumps(row, sort_keys=True) + "\n")
            status = "applied" if repair_report.get("applied") else f"skipped:{repair_report.get('reason')}"
            print(f"{path.name} -> {out_path.name} {status}; candidates={len(candidates)}")

    print(f"ledger: {ledger_path}")
    return 0


def content_repair_settings(preset, engine="qwen"):
    return {
        "mode": "content-repair-lab",
        "intensity": 100,
        "preserve_straight_lines": True,
        "techniques": {},
        "content_repair": {
            "preset": preset,
            "patch_size": 256,
            "stride": 128,
            "candidate_threshold": 0.80,
            "min_region_area_ratio": 0.004,
            "max_regions": 3,
            "mask_dilation_px": 10,
            "mask_feather_px": 20,
            "engine": engine,
        },
    }


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


def build_negative_control_gate(is_negative_control, candidate_count, score_delta, max_rise):
    if not is_negative_control:
        return {"required": False}
    selected_candidates_status = "pass" if candidate_count == 0 else "fail"
    detector_status = "not_scored"
    rises = None
    if isinstance(score_delta, dict):
        rises = {key: value for key, value in score_delta.items() if value > max_rise}
        detector_status = "fail" if rises else "pass"
    return {
        "required": True,
        "status": "fail" if selected_candidates_status == "fail" or detector_status == "fail" else detector_status,
        "selected_candidates": candidate_count,
        "selected_candidates_status": selected_candidates_status,
        "detector_status": detector_status,
        "max_allowed_rise": max_rise,
        "rises": rises,
    }


def promotion_checks(calibration, negative_control_gate):
    return {
        "localizer_precision_target": 0.8,
        "localizer_recall_target": 0.6,
        "localizer_precision_pass": (
            None if calibration is None else calibration["precision"] >= 0.8
        ),
        "localizer_recall_pass": None if calibration is None else calibration["recall"] >= 0.6,
        "negative_control_pass": (
            None
            if not negative_control_gate.get("required")
            else negative_control_gate.get("status") == "pass"
        ),
    }


def find_manual_mask(mask_dir, image_path):
    if not mask_dir:
        return None
    for suffix in (".png", ".jpg", ".jpeg", ".webp"):
        candidate = mask_dir / f"{image_path.stem}{suffix}"
        if candidate.exists():
            return candidate
    return None


if __name__ == "__main__":
    raise SystemExit(main())
