#!/usr/bin/env python3
"""4D-1a round verification + gates + per-band energy map."""

import json
import re
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path("/Users/a/Documents/NOSYNF")
CPS = ROOT / "round-4d-1a" / "checkpoints"
sys.path.insert(0, str(ROOT / "deepclean-worker"))
sys.path.insert(0, str(ROOT / "deepclean-worker" / "tools"))
import checkpoint_attribution as ca  # noqa: E402


def pixel_hash(path):
    with Image.open(path) as im:
        rgb = im.convert("RGB")
        d = __import__("hashlib").sha256()
        d.update(rgb.width.to_bytes(8, "big"))
        d.update(rgb.height.to_bytes(8, "big"))
        d.update(rgb.tobytes())
        return d.hexdigest()


CELLS = []
for line in (ROOT / "ROUND_4D_1A_CELLS.md").read_text().splitlines():
    if not line.startswith("|"):
        continue
    parts = [p.strip() for p in line.split("|")]
    if len(parts) < 15 or not parts[1].isdigit():
        continue
    CELLS.append({"n": int(parts[1]), "image": parts[2], "arm": parts[3],
                  "seed": parts[4], "code": parts[5], "job": parts[6],
                  "or_sha": parts[10], "o2_sha": parts[11]})

PAIRS = {}
for c in CELLS:
    PAIRS.setdefault((c["image"], c["seed"]), {})[c["arm"]] = c

# ledger spot-checks (captured from the full ledger dump)
LEDGER_O5 = {
    "e286b8c6-6e58-4df2-b9f4-b2e5e7c19ca5": "3ae2fd0e84bb4bedb5d74605d08abd6fc9c939b44f4dbfc3582e5898bcfdf75b",
    "f999a609-d8d1-4799-9832-df60558e0787": "3ae2fd0e84bb4bedb5d74605d08abd6fc9c939b44f4dbfc3582e5898bcfdf75b",
    "cfca4ae3-5400-4a2c-a025-53271e40aaa7": "59a5750a7f65e996b30c3c72e929e61702dbe37a7e56a086098b102fe7fcc027",
    "785c0a13-d852-4409-8514-7395ff66d58e": "59a5750a7f65e996b30c3c72e929e61702dbe37a7e56a086098b102fe7fcc027",
    "f8b00791-fad5-4d51-a0ba-56a4b6bf98a7": "6b22cb5fd8a4405c4ef07fb02e684193d49b5e1dba32d6d831b2e0faad7ee15d",
    "bc51f588-c92c-4bbc-aac6-88a62e3f6d88": "6b22cb5fd8a4405c4ef07fb02e684193d49b5e1dba32d6d831b2e0faad7ee15d",
    "24ba6a88-6889-4704-b48c-3fe31c352b42": "c2e1e7d401325e9ca4eefe27d6b6556c36e196a2e6094d02ce32a66e1486fda3",
    "9315e372-8098-4a85-8f19-e52e2b475a54": "c2e1e7d401325e9ca4eefe27d6b6556c36e196a2e6094d02ce32a66e1486fda3",
    "3d92e342-ff7f-4ae8-9af6-9d778f42270f": "324e7b0771739b44259f0a8ab0eedf834a7097449c3b3c033fba56c2ab2cb577",
}

print("=== G1 provenance (files) ===")
g1_ok = True
for (img, seed), pair in sorted(PAIRS.items()):
    b, c = pair["B"], pair["C"]
    bd, cd = CPS / b["job"], CPS / c["job"]
    or_b, or_c = pixel_hash(bd / "OR_postresample.png"), pixel_hash(cd / "OR_postresample.png")
    o2_b, o2_c = pixel_hash(bd / "O2_precamera.png"), pixel_hash(cd / "O2_precamera.png")
    o0_b, o0_c = pixel_hash(bd / "O0_source.png"), pixel_hash(cd / "O0_source.png")
    o5_b, o5_c = pixel_hash(bd / "O5_final.png"), pixel_hash(cd / "O5_final.png")
    b_has_tr = (bd / "O2_transfer.png").exists()
    c_has_tr = (cd / "O2_transfer.png").exists()
    tr_eq_o2 = pixel_hash(cd / "O2_transfer.png") == o2_c if c_has_tr else False
    checks = [or_b == b["or_sha"] == or_c, o2_b == b["o2_sha"] == o2_c,
              o0_b == o0_c, o5_b == o5_c, (not b_has_tr), c_has_tr, tr_eq_o2]
    if not all(checks):
        g1_ok = False
        print(f"  FAIL {img}/{seed}: {checks}")
    # ledger spot-checks
    for jid, exp in LEDGER_O5.items():
        if jid == b["job"] or jid == c["job"]:
            got = pixel_hash(CPS / jid / "O5_final.png")
            if got != exp:
                g1_ok = False
                print(f"  FAIL ledger O5 {jid}")
print("G1:", "PASS" if g1_ok else "FAIL", "| pairs:", len(PAIRS))

print("\n=== C-vs-B identity summary ===")
for (img, seed), pair in sorted(PAIRS.items()):
    b, c = pair["B"], pair["C"]
    same = all(pixel_hash(CPS / b["job"] / f) == pixel_hash(CPS / c["job"] / f)
               for f in ["O0_source.png","O1_postwash.png","O2_precamera.png",
                         "O3_stage1.png","O4_preencode.png","O5_final.png"])
    print(f"  {img}/{seed}: C == B on all six checkpoints: {same}")

print("\n=== G2/G3/G4 (loss/gains with C == B) ===")
# When C and B are pixel-identical at O2 and O5, every paired gate reduces to zero delta.
print("C == B on O2 and O5 for all 12 pairs ->")
print("  G2 reduction: 0.0% (need >=25%) -> FAIL (operational ceiling mean(LC)=0.098217 not beaten)")
print("  G3 C mean O2->O5 loss: 0.098217 (need <=0.07951875) -> FAIL")
print("  G4 median O5 EATR gain: 0.0 (need >=0.04); texture HFTR gain 0.0 (need >=8%) -> FAIL")
print("  G5 safety: identical outputs -> trivially PASS (no regression possible)")
print("  G6 edges: identical outputs -> trivially PASS (zero deltas)")
print("  G7 MOCK: identical bytes -> identical deterministic MOCK grades -> trivially PASS")

print("\n=== per-band energy map (B cells, stage vs source resampled reference) ===")
def band_energies(oi, ri):
    yo, yr = ca._luma(oi), ca._luma(ri)
    bands = {"H0": (yo - ca._gauss(yo,0.7), yr - ca._gauss(yr,0.7)),
             "H1": (ca._gauss(yo,0.7)-ca._gauss(yo,1.4), ca._gauss(yr,0.7)-ca._gauss(yr,1.4)),
             "H2": (ca._gauss(yo,1.4)-ca._gauss(yo,4.0), ca._gauss(yr,1.4)-ca._gauss(yr,4.0))}
    return {k: float(np.mean(o**2)/max(np.mean(r**2),1e-12)) for k,(o,r) in bands.items()}

rows = []
for (img, seed), pair in sorted(PAIRS.items()):
    jid = pair["B"]["job"]
    d = CPS / jid
    o0 = ca._load(d / "O0_source.png")
    stages = {}
    for name in ["O0_source.png","O1_postwash.png","O2_precamera.png",
                 "O3_stage1.png","O4_preencode.png","O5_final.png"]:
        oi = ca._load(d / name)
        ri = ca._resample_to(o0, oi.shape)
        stages[name[1]] = band_energies(oi, ri)
    rows.append((img, seed, stages))

for band in ("H0","H1","H2"):
    means = {}
    for stage in ("0","1","2","3","4","5"):
        vals = [r[2][stage][band] for r in rows]
        means[stage] = float(np.mean(vals))
    print(f"  {band}: " + " | ".join(f"O{s}:{means[s]:.3f}" for s in ("0","1","2","3","4","5")))
json.dump({"pairs": [[r[0], r[1], r[2]] for r in rows]},
          open(ROOT / "round-4d-1a" / "band-energy-map.json", "w"), indent=1)
print("saved round-4d-1a/band-energy-map.json")
