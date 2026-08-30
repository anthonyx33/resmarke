#!/usr/bin/env python3
"""edge_stage_pin.py — locate the stage where gate-6 edge widening appears.

For worst/best pairs: compute the frozen edge_width_10_90 metric (combined
bands) per stage (OR, O2, O5, R5) and ESF profiles on O5 vs R5.
"""

import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

TOOLS_DIR = Path(__file__).resolve().parent
WORKER_DIR = TOOLS_DIR.parent
ROOT = WORKER_DIR.parent
sys.path.insert(0, str(TOOLS_DIR))
sys.path.insert(0, str(WORKER_DIR))

import checkpoint_attribution as ca  # noqa: E402
from edge_spread_audit import edge_profiles, summarize  # noqa: E402

CPS = ROOT / "round-4d-cam-1" / "checkpoints"

# (image, seed, B, C) — worst 4 + best 1 from gate 6
CASES = [
    ("IMG-8", "lab-ctla1", "b7c88690-6e2d-4b83-8d5c-27597c22c329", "9dbf0b85-01d2-4284-a8ac-652777f2f037"),
    ("IMG-5", "lab-ctla1", "cdc39738-3f0c-4260-809d-12b60854acd5", "289a3098-2963-4a7e-b320-85affda102f6"),
    ("IMG-6", "lab-ctla1", "fb8e1d63-bcc8-4a4f-a770-34be1d9ee62d", "132fb974-2891-4c6c-8327-076316bd1aee"),
    ("IMG-7", "lab-ctla1", "b5bdd673-1fef-4cb5-80b6-946900e0331a", "b7093a06-853e-4acd-86d6-8116bba90cba"),
    ("IMG-8", "lab-ctla2", "ded27f0f-011d-49ce-93a3-cf4e1c0d1b00", "a29528bb-5b3e-4317-86e2-8907718d0aaa"),
]


def load(jid, fname):
    return ca._load(CPS / jid / fname)


def combined_ew(img):
    return float(np.mean([ca._edge_width_10_90(ca._luma(ca._crop(img, box)))
                          for box in ca.POSITIONAL_BANDS.values()]))


def main():
    out = []
    for img, seed, bid, cid in CASES:
        for tag, jid in (("B", bid), ("C", cid)):
            or_img = load(jid, "OR_postresample.png")
            o2_img = load(jid, "O2_precamera.png")
            o5_img = load(jid, "O5_final.png")
            r5_img = ca._resample_to(load(jid, "O0_source.png"), o5_img.shape)
            row = {
                "case": f"{img}/{seed}", "arm": tag,
                "ew_OR": round(combined_ew(or_img), 2),
                "ew_O2": round(combined_ew(o2_img), 2),
                "ew_O5": round(combined_ew(o5_img), 2),
                "ew_R5": round(combined_ew(r5_img), 2),
                "esf_O5": summarize(edge_profiles(ca._luma(o5_img))),
                "esf_R5": summarize(edge_profiles(ca._luma(r5_img))),
            }
            s5, sr = row["esf_O5"], row["esf_R5"]
            print(f"{row['case']} {tag}: EW OR={row['ew_OR']} O2={row['ew_O2']} "
                  f"O5={row['ew_O5']} R5={row['ew_R5']} | ESF O5 raw={s5['raw_width']:.2f} "
                  f"mono={s5['mono_width']:.2f} os={s5['overshoot']:.4f} | "
                  f"ESF R5 raw={sr['raw_width']:.2f} mono={sr['mono_width']:.2f}", flush=True)
            out.append(row)
    json.dump(out, open(ROOT / "round-4d-cam-1" / "edge-stage-pin.json", "w"), indent=1)
    print("saved edge-stage-pin.json")


if __name__ == "__main__":
    main()
