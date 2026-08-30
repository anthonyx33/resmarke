#!/usr/bin/env python3
"""round_4d_1a_or_split.py — provenance generator for or-band-split.json.

Splits the archived O1->O2 H1 band-energy loss into resample-only (O1->OR)
and camera-ladder-only (OR->O2) using the frozen checkpoint_attribution
recipe (H1 = gauss(0.7) - gauss(1.4), luma 0.2126/0.7152/0.0722, frozen
uint8-quantized _gauss).
"""

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
TOOLS = Path(__file__).resolve().parent
WORKER = TOOLS.parent
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(WORKER))

import checkpoint_attribution as ca  # noqa: E402

CPS = ROOT / "round-4d-1a" / "checkpoints"

# 12 archived incumbent B cells of the 4D-1a round (sentinel set)
B_CELLS = {
    "IMG-5/ctla1": "e286b8c6-6e58-4df2-b9f4-b2e5e7c19ca5",
    "IMG-6/ctla1": "cfca4ae3-5400-4a2c-a025-53271e40aaa7",
    "IMG-7/ctla1": "f8b00791-fad5-4d51-a0ba-56a4b6bf98a7",
    "IMG-8/ctla1": "24ba6a88-6889-4704-b48c-3fe31c352b42",
    "IMG-9/ctla1": "3d92e342-ff7f-4ae8-9af6-9d778f42270f",
    "IMG-11/ctla1": "0e8faaa6-647b-4e8b-86e5-a8ad133d19ab",
    "IMG-5/ctla2": "2f4fa3d1-b871-4d60-a53a-29ef62abde9e",
    "IMG-6/ctla2": "58914774-02ed-45f0-a823-95dce8ad09db",
    "IMG-7/ctla2": "5a702b8a-106d-4c98-928e-517bbaef8fe5",
    "IMG-8/ctla2": "d6fef99d-87ba-4cba-b8ed-63c3b9238c64",
    "IMG-9/ctla2": "ef2935bd-9d2c-4b62-8005-361377e6db95",
    "IMG-11/ctla2": "4d01103a-865d-486f-869f-b56cbb9953b9",
}


def h1_energy(img):
    y = ca._luma(img)
    band = ca._gauss(y, 0.7) - ca._gauss(y, 1.4)
    return float(np.mean(band * band, dtype=np.float64))


def main():
    rows = []
    for name, jid in B_CELLS.items():
        d = CPS / jid
        o1 = ca._load(d / "O1_postwash.png")
        ori = ca._load(d / "OR_postresample.png")
        o2 = ca._load(d / "O2_precamera.png")
        o1_res = ca._resample_to(o1, ori.shape)  # O1 at OR lattice (the resample step)
        e1, eor, e2 = h1_energy(o1_res), h1_energy(ori), h1_energy(o2)
        rows.append((name, e1, eor, e2))
    mean_cam = float(np.mean([r[3] / max(r[2], 1e-12) for r in rows]))
    mean_res = float(np.mean([r[2] / max(r[1], 1e-12) for r in rows]))
    doc = {
        "generator": "tools/round_4d_1a_or_split.py",
        "per_cell": [[r[0], r[1], r[2], r[3]] for r in rows],
        "mean_camera_ladder_retention": mean_cam,
        "mean_resample_retention": mean_res,
        "qualification": ("0.0000 resample loss holds under the geometry-normalized "
                          "comparison only; the earlier native-resolution attribution "
                          "found a real, though secondary, resample cost."),
    }
    out = ROOT / "round-4d-1a" / "or-band-split.json"
    out.write_text(json.dumps(doc, indent=1, sort_keys=True))
    print(f"mean camera-ladder H1 retention: {mean_cam:.6f} (loss {1-mean_cam:.6f})")
    print(f"mean resample H1 retention:      {mean_res:.6f}")
    print(f"saved {out}")


if __name__ == "__main__":
    main()
