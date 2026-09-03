#!/usr/bin/env python3
"""Frozen-quality metrics for the full matrix (44 delivered files) + 1.01 cohort.

Uses the exact frozen recipe `metric_record` and `_roi_for` from
tools/round_remint_1_01_validate.py — no substitutions.
"""
import json
import os
import sys
from pathlib import Path

TOOLS = Path("/Users/a/Documents/NOSYNF/deepclean-worker/tools")
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(TOOLS.parent))

import round_remint_1_01_validate as v  # noqa: E402

HERE = Path("/Users/a/Documents/NOSYNF/round-full-matrix")
SRC = Path("/Users/a/Documents/NOSYNF/round-remint-1-01/full-corpus")
EXT = {1: "jpg", 2: "jpg", 3: "png", 4: "png", 5: "png", 6: "png",
       7: "png", 8: "png", 9: "png", 10: "png", 11: "jpeg"}

PRESET_CODES = {
    "Config A": "SEQ-CFA-lhbmeve33nn3",
    "Config 1A": "SEQ-1A-tpxokpv5c53f",
    "Config 2B": "SEQ-2B-vr6sikgjt3ap",
    "Config 3C": "SEQ-3C-nzzomjahxuyi",
    "ReMint 1.01": "SEQ-1.01-yg63qja3got4",
}
PRESET_PREFIX = {
    "Config A": "A", "Config 1A": "1A", "Config 2B": "2B", "Config 3C": "3C",
    "ReMint 1.01": "1.01",
}


def source_for(image: str) -> Path:
    n = int(image.split("-")[1])
    return SRC / f"{image}_source.{EXT[n]}"


def summary(rows):
    keys = ["h0_energy_ratio", "h1_energy_ratio", "h2_energy_ratio"]
    return {
        "cell_count": len(rows),
        "global": {
            k: round(sum(r["metrics"]["global"][k] for r in rows) / len(rows), 6)
            for k in keys
        },
        "texture_h1_energy": round(
            sum(r["metrics"]["texture_h1_energy"] for r in rows) / len(rows), 6),
        "eatr_p95": round(sum(r["metrics"]["eatr_p95"] for r in rows) / len(rows), 6),
        "protected_eatr_absolute_min": round(
            min(r["metrics"]["protected_eatr_absolute_min"] for r in rows), 6),
        "texture_residual": {
            "luma_rms_255": round(sum(r["metrics"]["texture_residual"]["luma_rms_255"] for r in rows) / len(rows), 6),
            "chroma_rms_255": round(sum(r["metrics"]["texture_residual"]["chroma_rms_255"] for r in rows) / len(rows), 6),
            "rho1": round(sum(r["metrics"]["texture_residual"]["rho1"] for r in rows) / len(rows), 6),
        },
        "band_residual": {
            k: round(sum(r["metrics"]["source_relative_band_residual_rms"][k] for r in rows) / len(rows), 6)
            for k in ("h0_rms", "h1_rms", "h2_rms")
        },
        "staircase": round(sum(r["metrics"]["staircase_attribution_recipe"] for r in rows) / len(rows), 6),
    }


def main():
    cells = [json.loads(l) for l in
             (HERE / "ledger.jsonl").read_text().splitlines() if '"cell"' in l]
    assert len(cells) == 44, len(cells)

    rows = []
    for c in cells:
        image = c["image"]
        roi = v._roi_for(image)
        metrics = v.metric_record(HERE / c["delivered_file"], source_for(image), roi)
        rows.append({
            "preset": c["preset"],
            "image": image,
            "file": c["delivered_file"],
            "settings_code": c["settings_code"],
            "delivered_sha256": c["delivered_sha256"],
            "metrics": metrics,
        })
        print(f"metrics {c['preset']:9s} {image:6s} {c['delivered_file']}", flush=True)

    # 1.01 cohort (same frozen recipe, same canonical sources)
    for n in range(1, 12):
        image = f"IMG-{n}"
        fn = f"1.01_{image}_lab-ctla1.jpg"
        p = SRC / fn
        metrics = v.metric_record(p, source_for(image), v._roi_for(image))
        rows.append({
            "preset": "ReMint 1.01",
            "image": image,
            "file": str(p),
            "settings_code": PRESET_CODES["ReMint 1.01"],
            "delivered_sha256": v._sha256(p),
            "metrics": metrics,
        })
        print(f"metrics ReMint 1.01 {image:6s} {fn}", flush=True)

    cohort = {preset: summary([r for r in rows if r["preset"] == preset])
              for preset in PRESET_CODES}

    out = {
        "recipe": "tools/round_remint_1_01_validate.metric_record + _roi_for (frozen 1.01)",
        "note_resolution_sensitivity": (
            "vs-source energy ratios are resolution-sensitive; delivered dims differ "
            "per preset/cell (Config A delivers min(src,1800)). Compare cohorts with care."),
        "files": rows,
        "cohort_summary": cohort,
    }
    (HERE / "frozen-metrics.json").write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")
    print("WROTE frozen-metrics.json")
    for preset, s in cohort.items():
        print(preset, json.dumps(s["global"]), "protected_min",
              s["protected_eatr_absolute_min"])


if __name__ == "__main__":
    main()
