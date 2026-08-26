#!/usr/bin/env python3
"""4D-CAM-1 fixed-rung replay and OR-relative camera-only metrics."""

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

TOOLS_DIR = Path(__file__).resolve().parent
WORKER_DIR = TOOLS_DIR.parent
sys.path.insert(0, str(TOOLS_DIR))
sys.path.insert(0, str(WORKER_DIR))

from checkpoint_attribution import _metrics_for  # noqa: E402
from ds_remint_v8_8 import _v88_candidate, normalize_ds_remint_v8_8_settings  # noqa: E402


def pixel_sha256_image(image):
    """Hash decoded RGB pixels plus dimensions, matching checkpoint_capture."""
    rgb = image.convert("RGB")
    digest = hashlib.sha256()
    digest.update(rgb.width.to_bytes(8, "big"))
    digest.update(rgb.height.to_bytes(8, "big"))
    digest.update(rgb.tobytes())
    return digest.hexdigest()


def camera_only_metrics(or_image, o2_image):
    """Measure O2 against the identical-lattice post-resample OR reference."""
    reference = or_image.convert("RGB")
    output = o2_image.convert("RGB")
    if reference.size != output.size:
        raise ValueError(f"OR/O2 lattice mismatch: {reference.size} != {output.size}")
    ref_array = np.asarray(reference).astype(np.float64) / 255.0
    out_array = np.asarray(output).astype(np.float64) / 255.0
    metrics = _metrics_for(out_array, ref_array)
    hftr_h1 = float(metrics["hftr"]["H1"])
    loss = max(
        1.0 - float(metrics["eatr"]),
        1.0 - hftr_h1,
        0.0,
    )
    return {
        "eatr": float(metrics["eatr"]),
        "hftr_H1": hftr_h1,
        "loss": float(loss),
    }


def fixed_rung_pair(or_image, rung, creator_id, seed_extra, rung_index=0):
    """Replay one DS camera rung with absence/1.00 baseline versus sealed 0.50."""
    if rung not in ("light", "balanced", "deep"):
        raise ValueError(f"unsupported camera rung: {rung}")
    base_cfg = normalize_ds_remint_v8_8_settings({
        "mode": "ds-remint-v8.9",
        "ds_remint_v8_9": {"engine_mode": "template", "strength": rung},
    })
    candidate_cfg = normalize_ds_remint_v8_8_settings({
        "mode": "ds-remint-v8.9",
        "ds_remint_v8_9": {
            "engine_mode": "template",
            "strength": rung,
            "optics_psf_scale": 0.5,
        },
    })
    baseline, baseline_layers = _v88_candidate(
        or_image, rung, base_cfg, creator_id, seed_extra, rung_index
    )
    candidate, candidate_layers = _v88_candidate(
        or_image, rung, candidate_cfg, creator_id, seed_extra, rung_index
    )
    return {
        "or_sha256": pixel_sha256_image(or_image),
        "rung": rung,
        "creator_id": creator_id,
        "seed_extra": seed_extra,
        "baseline": {
            "image": baseline,
            "sha256": pixel_sha256_image(baseline),
            "metrics": camera_only_metrics(or_image, baseline),
            "layers": baseline_layers,
        },
        "candidate": {
            "image": candidate,
            "sha256": pixel_sha256_image(candidate),
            "metrics": camera_only_metrics(or_image, candidate),
            "layers": candidate_layers,
        },
    }


def existing_pair(baseline_or_path, candidate_or_path, baseline_o2_path, candidate_o2_path):
    """Measure captured B/C outputs after proving their two OR buffers identical."""
    with Image.open(baseline_or_path) as baseline_or_raw, Image.open(
        candidate_or_path
    ) as candidate_or_raw, Image.open(baseline_o2_path) as baseline_raw, Image.open(
        candidate_o2_path
    ) as candidate_raw:
        baseline_or = baseline_or_raw.convert("RGB")
        candidate_or = candidate_or_raw.convert("RGB")
        baseline_or_sha = pixel_sha256_image(baseline_or)
        candidate_or_sha = pixel_sha256_image(candidate_or)
        if baseline_or_sha != candidate_or_sha:
            raise ValueError("paired OR_postresample pixel hashes do not match")
        baseline = baseline_raw.convert("RGB")
        candidate = candidate_raw.convert("RGB")
        return {
            "or_identical": True,
            "or_sha256": baseline_or_sha,
            "baseline": {
                "sha256": pixel_sha256_image(baseline),
                "metrics": camera_only_metrics(baseline_or, baseline),
            },
            "candidate": {
                "sha256": pixel_sha256_image(candidate),
                "metrics": camera_only_metrics(candidate_or, candidate),
            },
        }


def _json_ready(result):
    if isinstance(result, Image.Image):
        return None
    if isinstance(result, dict):
        return {key: _json_ready(value) for key, value in result.items() if key != "image"}
    if isinstance(result, list):
        return [_json_ready(value) for value in result]
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("or_path", help="OR_postresample.png")
    parser.add_argument("--rung", choices=("light", "balanced", "deep"), default="balanced")
    parser.add_argument("--creator-id", default="4d-cam-1-replay")
    parser.add_argument("--seed-extra", default="lab:4d-cam-1-replay")
    args = parser.parse_args()
    with Image.open(args.or_path) as source:
        result = fixed_rung_pair(source.convert("RGB"), args.rung, args.creator_id, args.seed_extra)
    print(json.dumps(_json_ready(result), sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
