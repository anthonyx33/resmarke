#!/usr/bin/env python3
"""4D-CAM-1 replay validation: both arms vs live O2 hashes, pixel deltas,
and self-determinism on this machine."""

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
import camera_only_replay as cor  # noqa: E402

CPS = ROOT / "round-4d-cam-1" / "checkpoints"

PAIRS = [
    ("IMG-1", "lab-ctla1", "acc7276f-4891-4b45-b878-be9c936f139c", "80dd1c67-a096-484d-958f-caf90404fcd0"),
    ("IMG-2", "lab-ctla1", "4f0cc6fa-c135-4128-a1b1-11138368ff9f", "0cc09705-1956-4b61-8154-f3286cc32c6b"),
    ("IMG-3", "lab-ctla1", "83639c9a-4b6a-41e2-bd5c-49fe0b3d31df", "30004fb3-ff55-4d7c-8132-c7a6809b0b3f"),
    ("IMG-4", "lab-ctla1", "0376d4b3-fe1f-4c30-854a-c021353e9a76", "b2fce72c-b2d1-4dca-a5c2-4ac9aa8525bb"),
    ("IMG-5", "lab-ctla1", "cdc39738-3f0c-4260-809d-12b60854acd5", "289a3098-2963-4a7e-b320-85affda102f6"),
    ("IMG-6", "lab-ctla1", "fb8e1d63-bcc8-4a4f-a770-34be1d9ee62d", "132fb974-2891-4c6c-8327-076316bd1aee"),
    ("IMG-7", "lab-ctla1", "b5bdd673-1fef-4cb5-80b6-946900e0331a", "b7093a06-853e-4acd-86d6-8116bba90cba"),
    ("IMG-8", "lab-ctla1", "b7c88690-6e2d-4b83-8d5c-27597c22c329", "9dbf0b85-01d2-4284-a8ac-652777f2f037"),
    ("IMG-9", "lab-ctla1", "88cfd748-679e-4a01-8d7a-d380e61f6ba6", "615e71ca-1d8f-434a-80c3-2f3c4e06f944"),
    ("IMG-10", "lab-ctla1", "22c02cef-8ec5-4231-97c3-27094518fc5b", "198cb8f0-3786-4c56-8b8c-c06a477bd5ac"),
    ("IMG-11", "lab-ctla1", "33c5b63b-5b07-4f00-a796-0323d1ff29f3", "68e7a402-effe-4f16-9751-04ab30214178"),
    ("IMG-5", "lab-ctla2", "5bd6bc05-5763-4c45-b709-b2ecedab38c2", "c5064e1a-a4ca-4e1e-b403-0445212732ea"),
    ("IMG-6", "lab-ctla2", "ebd7f10c-538a-49c9-b3b3-c77e0771e5fa", "4510c2a2-a706-45e5-b5ae-6cf118308f30"),
    ("IMG-9", "lab-ctla2", "f1e03428-3a1e-4c0d-9626-7c2f4220a770", "e044e337-b2db-45f9-ada2-411d7bddfb0b"),
    ("IMG-11", "lab-ctla2", "963c40d7-4ea5-4fe4-a56e-fc84fbd97dd6", "7a4ab192-da0f-43b3-b84c-b87db6e6ed85"),
    ("IMG-7", "lab-ctla2", "c526e593-4a41-409e-8700-e6e825939409", "8dc8fe05-78bc-46bf-a4ab-08578db3aca1"),
    ("IMG-8", "lab-ctla2", "ded27f0f-011d-49ce-93a3-cf4e1c0d1b00", "a29528bb-5b3e-4317-86e2-8907718d0aaa"),
]


def pixel_hash_image(image):
    return cor.pixel_sha256_image(image)


def file_hash(jid, fname):
    with Image.open(CPS / jid / fname) as im:
        return cor.pixel_sha256_image(im.convert("RGB"))


def delta_stats(rep_img, live_path):
    with Image.open(live_path) as im:
        live = np.asarray(im.convert("RGB")).astype(np.float64)
    rep = np.asarray(rep_img.convert("RGB")).astype(np.float64)
    if rep.shape != live.shape:
        return {"shape_mismatch": [rep.shape, live.shape]}
    diff = rep - live
    return {
        "rms_lsb": round(float(np.sqrt(np.mean(diff ** 2))), 4),
        "max_abs_lsb": round(float(np.abs(diff).max()), 4),
        "frac_exact_px": round(float(np.mean(np.abs(diff) < 0.5)), 6),
    }


def main():
    rows = []
    for img, seed, bid, cid in PAIRS:
        with Image.open(CPS / bid / "OR_postresample.png") as im:
            or_img = im.convert("RGB")
        res = cor.fixed_rung_pair(or_img, "deep", "anthonyx33@proton.me", f"lab:{seed}", 0)
        b_sha = res["baseline"]["sha256"]
        c_sha = res["candidate"]["sha256"]
        # self-determinism on this machine
        res2 = cor.fixed_rung_pair(or_img, "deep", "anthonyx33@proton.me", f"lab:{seed}", 0)
        self_det = res2["baseline"]["sha256"] == b_sha and res2["candidate"]["sha256"] == c_sha
        row = {
            "image": img, "seed": seed,
            "B_fidelity": b_sha == file_hash(bid, "O2_precamera.png"),
            "C_fidelity": c_sha == file_hash(cid, "O2_precamera.png"),
            "B_delta": delta_stats(res["baseline"]["image"], CPS / bid / "O2_precamera.png"),
            "C_delta": delta_stats(res["candidate"]["image"], CPS / cid / "O2_precamera.png"),
            "self_deterministic": self_det,
        }
        rows.append(row)
        print(f"{img}/{seed}: B={row['B_fidelity']} C={row['C_fidelity']} "
              f"selfDet={self_det} "
              f"BdRMS={row['B_delta'].get('rms_lsb')} BdMax={row['B_delta'].get('max_abs_lsb')} "
              f"CdRMS={row['C_delta'].get('rms_lsb')} CdMax={row['C_delta'].get('max_abs_lsb')}",
              flush=True)
    out = ROOT / "round-4d-cam-1" / "replay-validation.json"
    json.dump({"pairs": rows}, open(out, "w"), indent=2)
    n_b = sum(1 for r in rows if r["B_fidelity"])
    n_c = sum(1 for r in rows if r["C_fidelity"])
    print(f"\nB arm fidelity: {n_b}/17 | C arm fidelity: {n_c}/17 | self-deterministic: "
          f"{sum(1 for r in rows if r['self_deterministic'])}/17")
    print(f"Saved {out}")


if __name__ == "__main__":
    main()
