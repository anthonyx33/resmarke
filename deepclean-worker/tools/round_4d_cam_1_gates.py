#!/usr/bin/env python3
"""4D-CAM-1 master-engineer screening gate computation (MOCK round).

All metrics reuse the frozen checkpoint_attribution / camera_only_replay
primitives. Nothing here changes any frozen file. Outputs:
  round-4d-cam-1/gate-results.json  (full record)
"""

import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image

TOOLS_DIR = Path(__file__).resolve().parent
WORKER_DIR = TOOLS_DIR.parent
ROOT = WORKER_DIR.parent
sys.path.insert(0, str(TOOLS_DIR))
sys.path.insert(0, str(WORKER_DIR))

import checkpoint_attribution as ca  # noqa: E402  (frozen, never modified)
import camera_only_replay as cor  # noqa: E402

CPS = ROOT / "round-4d-cam-1" / "checkpoints"
ROI = json.load(open(ROOT / "round-4d-cam-1" / "roi-manifest.json"))["images"]
OUT = ROOT / "round-4d-cam-1" / "gate-results.json"

CREATOR_ID = "anthonyx33@proton.me"
RUNG = "deep"
RUNG_INDEX = 0

# image, seed, B job id, C job id  (from ROUND_4D_CAM_1_CELLS.md, server-verified)
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
SENTINELS = ["IMG-5", "IMG-6", "IMG-7", "IMG-8", "IMG-9", "IMG-11"]
SUBSET = ["IMG-5", "IMG-6", "IMG-9", "IMG-11"]

CACHE = {}


def load(jid, fname):
    return ca._load(CPS / jid / fname)


def pixel_hash(jid, fname):
    with Image.open(CPS / jid / fname) as im:
        rgb = im.convert("RGB")
        d = hashlib.sha256()
        d.update(rgb.width.to_bytes(8, "big"))
        d.update(rgb.height.to_bytes(8, "big"))
        d.update(rgb.tobytes())
        return d.hexdigest()


def eatr_of(oi, ri):
    yo, yr = ca._luma(oi), ca._luma(ri)
    return float(np.percentile(ca._edge_mag(yo), 95) /
                 max(np.percentile(ca._edge_mag(yr), 95), 1e-9))


def hftr_h1_of(oi, ri):
    yo, yr = ca._luma(oi), ca._luma(ri)
    bo = ca._gauss(yo, 0.7) - ca._gauss(yo, 1.4)
    br = ca._gauss(yr, 0.7) - ca._gauss(yr, 1.4)
    return float(np.sqrt(np.mean(bo ** 2)) /
                 max(np.sqrt(np.mean(br ** 2)), 1e-9))


def combined_eatr_h1(oi, ri):
    """Frozen-tool recipe: mean over the 5 positional bands."""
    eatrs, h1s = [], []
    for box in ca.POSITIONAL_BANDS.values():
        co, cr = ca._crop(oi, box), ca._crop(ri, box)
        eatrs.append(eatr_of(co, cr))
        h1s.append(hftr_h1_of(co, cr))
    return float(np.mean(eatrs)), float(np.mean(h1s))


def combined_edge_width(img):
    widths = []
    for box in ca.POSITIONAL_BANDS.values():
        widths.append(ca._edge_width_10_90(ca._luma(ca._crop(img, box))))
    return float(np.mean(widths))


def cell_ckpt(jid, ck):
    """Geometry-matched combined metrics for one checkpoint."""
    key = (jid, ck)
    if key in CACHE:
        return CACHE[key]
    oi = load(jid, ck)
    o0 = load(jid, "O0_source.png")
    ri = ca._resample_to(o0, oi.shape)
    eatr, h1 = combined_eatr_h1(oi, ri)
    CACHE[key] = {"eatr": eatr, "hftr_H1": h1, "edge_width": combined_edge_width(oi)}
    return CACHE[key]


def transition_loss(jid, a, b):
    ma, mb = cell_ckpt(jid, a), cell_ckpt(jid, b)
    de = mb["eatr"] - ma["eatr"]
    dh = mb["hftr_H1"] - ma["hftr_H1"]
    return {"dEATR": round(de, 4), "dHFTR_H1": round(dh, 4),
            "loss": round(max(abs(min(de, 0.0)), abs(min(dh, 0.0))), 4)}


def roi_metrics(jid, ck, boxes):
    """ROI crops of O5 vs geometry-matched R5."""
    oi = load(jid, ck)
    o0 = load(jid, "O0_source.png")
    ri = ca._resample_to(o0, oi.shape)
    eatrs, h1s, lrms, crms, r1, r2 = [], [], [], [], [], []
    for box in boxes:
        co, cr = ca._crop(oi, box), ca._crop(ri, box)
        eatrs.append(eatr_of(co, cr))
        h1s.append(hftr_h1_of(co, cr))
        resid = ca._luma(co) - ca._luma(cr)
        lrms.append(float(np.sqrt(np.mean(resid ** 2))) * 255.0)
        cc = co[..., 1:3] - cr[..., 1:3]
        crms.append(float(np.sqrt(np.mean(cc ** 2))) * 255.0)
        mask = np.ones_like(resid, dtype=bool)
        r1.append(ca._masked_spatial_corr(resid, mask, 0, 1))
        r2.append(ca._masked_spatial_corr(resid, mask, 0, 2))
    return {"eatr": float(np.mean(eatrs)), "hftr_H1": float(np.mean(h1s)),
            "luma_rms_lsb": float(np.mean(lrms)), "chroma_rms_lsb": float(np.mean(crms)),
            "rho1": float(np.mean(r1)), "rho2": float(np.mean(r2))}


def main():
    t0 = time.time()
    results = {"pairs": [], "gates": {}}
    live_loss = {}  # jid -> O1->O2 loss
    print("--- Gate 1/3/4/5/6 metrics + live-adaptive losses ---", flush=True)

    pair_rows = []
    for img, seed, bid, cid in PAIRS:
        # gate 1 file-level pairing
        or_b, or_c = pixel_hash(bid, "OR_postresample.png"), pixel_hash(cid, "OR_postresample.png")
        o0_b, o0_c = pixel_hash(bid, "O0_source.png"), pixel_hash(cid, "O0_source.png")
        assert or_b == or_c, (img, seed, "OR mismatch")
        assert o0_b == o0_c, (img, seed, "O0 mismatch")
        # live-adaptive transition losses (B and C cells)
        lb = transition_loss(bid, "O1_postwash.png", "O2_precamera.png")
        lc = transition_loss(cid, "O1_postwash.png", "O2_precamera.png")
        live_loss[bid], live_loss[cid] = lb["loss"], lc["loss"]
        row = {"image": img, "seed": seed, "B": bid, "C": cid,
               "or_sha": or_b,
               "O1->O2_loss": {"B": lb, "C": lc}}
        pair_rows.append(row)
        print(f"  {img}/{seed}: OR ok, B loss={lb['loss']:.4f} C loss={lc['loss']:.4f}", flush=True)

    # ---- gate 4/5/6 O5-level metrics ----
    o5_eatr, tex_h1, prot_eatr = {}, {}, {}
    smooth, edge = {}, {}
    for img, seed, bid, cid in PAIRS:
        b5, c5 = cell_ckpt(bid, "O5_final.png"), cell_ckpt(cid, "O5_final.png")
        b0, c0 = cell_ckpt(bid, "O0_source.png"), cell_ckpt(cid, "O0_source.png")
        o5_eatr[bid], o5_eatr[cid] = b5["eatr"], c5["eatr"]
        r = ROI[img]
        tex = r.get("texture") or []
        prt = r.get("protected") or []
        smo = r.get("smooth") or []
        tb, tc = roi_metrics(bid, "O5_final.png", tex), roi_metrics(cid, "O5_final.png", tex)
        tex_h1[bid], tex_h1[cid] = tb["hftr_H1"], tc["hftr_H1"]
        pb, pc = roi_metrics(bid, "O5_final.png", prt), roi_metrics(cid, "O5_final.png", prt)
        prot_eatr[bid], prot_eatr[cid] = pb["eatr"], pc["eatr"]
        sb, sc = roi_metrics(bid, "O5_final.png", smo), roi_metrics(cid, "O5_final.png", smo)
        smooth[bid], smooth[cid] = sb, sc
        # edge width: O5 vs geometry-matched R5 (O0 at delivery geometry)
        ob = load(bid, "O5_final.png")
        rb = ca._resample_to(load(bid, "O0_source.png"), ob.shape)
        oc = load(cid, "O5_final.png")
        rc = ca._resample_to(load(cid, "O0_source.png"), oc.shape)
        ew_b0 = combined_edge_width(rb)
        ew_b5 = combined_edge_width(ob)
        ew_c0 = combined_edge_width(rc)
        ew_c5 = combined_edge_width(oc)
        gap_b = abs(ew_b5 - ew_b0) / max(ew_b0, 1e-9)
        gap_c = abs(ew_c5 - ew_c0) / max(ew_c0, 1e-9)
        edge[bid] = {"ew_ref": ew_b0, "ew_o5": ew_b5, "gap": gap_b}
        edge[cid] = {"ew_ref": ew_c0, "ew_o5": ew_c5, "gap": gap_c}
        print(f"  {img}/{seed}: O5 EATR B={b5['eatr']:.3f}/C={c5['eatr']:.3f} "
              f"texH1 B={tb['hftr_H1']:.3f}/C={tc['hftr_H1']:.3f} "
              f"protEATR B={pb['eatr']:.3f}/C={pc['eatr']:.3f} "
              f"gap B={gap_b:.3f}/C={gap_c:.3f}", flush=True)

    # ---------- gate 3: subset ----------
    subset_c = [live_loss[cid] for img, _, _, cid in PAIRS if img in SUBSET]
    subset_mean = float(np.mean(subset_c))
    results["gates"]["g3_subset"] = {
        "cells": sorted(subset_c), "mean": round(subset_mean, 6),
        "threshold": 0.1561, "baseline_A": 0.2081125,
        "pass": subset_mean <= 0.1561,
    }

    # ---------- gate 4 ----------
    gains_eatr, gains_tex_rel = [], []
    for img, seed, bid, cid in PAIRS:
        gains_eatr.append(o5_eatr[cid] - o5_eatr[bid])
        gains_tex_rel.append((tex_h1[cid] - tex_h1[bid]) / max(tex_h1[bid], 1e-9))
    med_eatr = float(np.median(gains_eatr))
    med_tex = float(np.median(gains_tex_rel))
    sent_dirs = {}
    for s in SENTINELS:
        cells = [(img, seed, bid, cid) for img, seed, bid, cid in PAIRS if img == s]
        de = float(np.mean([o5_eatr[cid] - o5_eatr[bid] for _, _, bid, cid in cells]))
        dh = float(np.mean([tex_h1[cid] - tex_h1[bid] for _, _, bid, cid in cells]))
        sent_dirs[s] = {"eatr_delta": de, "tex_delta": dh}
    n_dir = sum(1 for s in SENTINELS if sent_dirs[s]["eatr_delta"] > 0)
    results["gates"]["g4_delivered_detail"] = {
        "o5_eatr_gains": sorted(gains_eatr),
        "median_eatr_gain": round(med_eatr, 4), "threshold": 0.04,
        "texture_h1_rel_gains": sorted(gains_tex_rel),
        "median_texture_rel_gain": round(med_tex, 4), "threshold": 0.08,
        "sentinels": sent_dirs, "sentinel_direction_count": n_dir,
        "pass": med_eatr >= 0.04 and med_tex >= 0.08 and n_dir >= 5,
    }

    # ---------- gate 5 ----------
    worst_prot_ratio, worst_luma_inc, worst_chroma_inc = 1e9, -1e9, -1e9
    worst_rho_rise = -1e9
    for img, seed, bid, cid in PAIRS:
        ratio = prot_eatr[cid] / max(prot_eatr[bid], 1e-9)
        worst_prot_ratio = min(worst_prot_ratio, ratio)
        for key, inc in (("luma_rms_lsb", worst_luma_inc), ("chroma_rms_lsb", worst_chroma_inc)):
            base = max(smooth[bid][key], 1e-9)
            rel = (smooth[cid][key] - smooth[bid][key]) / base
            if key == "luma_rms_lsb":
                worst_luma_inc = max(worst_luma_inc, rel)
            else:
                worst_chroma_inc = max(worst_chroma_inc, rel)
        rise = max(smooth[cid]["rho1"] - smooth[bid]["rho1"],
                   smooth[cid]["rho2"] - smooth[bid]["rho2"])
        worst_rho_rise = max(worst_rho_rise, rise)
    results["gates"]["g5_protected_smooth"] = {
        "worst_protected_eatr_ratio": round(worst_prot_ratio, 4),
        "protected_floor": 0.98,
        "worst_smooth_luma_rel_increase": round(worst_luma_inc, 4),
        "worst_smooth_chroma_rel_increase": round(worst_chroma_inc, 4),
        "smooth_floor": 0.05,
        "worst_rho_rise": round(worst_rho_rise, 4), "rho_floor": 0.03,
        "pass": worst_prot_ratio >= 0.98 and worst_luma_inc <= 0.05
                and worst_chroma_inc <= 0.05 and worst_rho_rise <= 0.03,
    }

    # ---------- gate 6 ----------
    closures = []
    for img, seed, bid, cid in PAIRS:
        closures.append((edge[bid]["gap"] - edge[cid]["gap"]) / max(edge[bid]["gap"], 1e-9))
    med_close = float(np.median(closures))
    results["gates"]["g6_edge"] = {
        "relative_closures": sorted(closures),
        "median_relative_closure": round(med_close, 4),
        "threshold": 0.10,
        "pass": med_close >= 0.10,
    }

    # ---------- gate 2 live-adaptive ----------
    live_b = [live_loss[bid] for _, _, bid, _ in PAIRS]
    live_c = [live_loss[cid] for _, _, _, cid in PAIRS]
    sent_live = {}
    for s in SENTINELS:
        cells = [(img, seed, bid, cid) for img, seed, bid, cid in PAIRS if img == s]
        sent_live[s] = {
            "B_mean": float(np.mean([live_loss[b] for _, _, b, _ in cells])),
            "C_mean": float(np.mean([live_loss[c] for _, _, _, c in cells])),
        }
    results["gates"]["g2_live_adaptive"] = {
        "B_mean": round(float(np.mean(live_b)), 4),
        "C_mean": round(float(np.mean(live_c)), 4),
        "paired_mean_improves": float(np.mean(live_c)) < float(np.mean(live_b)),
        "sentinel_two_seed_means": sent_live,
        "sentinel_no_worsen": all(v["C_mean"] <= v["B_mean"] for v in sent_live.values()),
    }
    results["pairs"] = [
        {"image": img, "seed": seed, "B": bid, "C": cid,
         "or_sha": row["or_sha"], "O1->O2_loss": row["O1->O2_loss"],
         "o5_eatr": {"B": o5_eatr[bid], "C": o5_eatr[cid]},
         "texture_h1": {"B": tex_h1[bid], "C": tex_h1[cid]},
         "protected_eatr": {"B": prot_eatr[bid], "C": prot_eatr[cid]},
         "smooth": {"B": smooth[bid], "C": smooth[cid]},
         "edge": {"B": edge[bid], "C": edge[cid]}}
        for (img, seed, bid, cid), row in zip(PAIRS, pair_rows)
    ]

    # ---------- gate 2 fixed-rung replay ----------
    print("\n--- Gate 2: fixed-rung OR->O2 replay (rung deep, index 0) ---", flush=True)
    replay = []
    for img, seed, bid, cid in PAIRS:
        with Image.open(CPS / bid / "OR_postresample.png") as im:
            or_img = im.convert("RGB")
        res = cor.fixed_rung_pair(or_img, RUNG, CREATOR_ID, f"lab:{seed}", RUNG_INDEX)
        fidelity = res["baseline"]["sha256"] == pixel_hash(bid, "O2_precamera.png")
        replay.append({"image": img, "seed": seed,
                       "baseline_loss": res["baseline"]["metrics"]["loss"],
                       "candidate_loss": res["candidate"]["metrics"]["loss"],
                       "baseline_o2_sha": res["baseline"]["sha256"],
                       "live_B_o2_sha": pixel_hash(bid, "O2_precamera.png"),
                       "fidelity": fidelity})
        print(f"  {img}/{seed}: B={res['baseline']['metrics']['loss']:.4f} "
              f"C={res['candidate']['metrics']['loss']:.4f} fidelity={fidelity}", flush=True)
    rb = [r["baseline_loss"] for r in replay]
    rc = [r["candidate_loss"] for r in replay]
    sent_replay = {}
    for s in SENTINELS:
        cells = [r for r in replay if r["image"] == s]
        sent_replay[s] = {
            "B_mean": float(np.mean([r["baseline_loss"] for r in cells])),
            "C_mean": float(np.mean([r["candidate_loss"] for r in cells])),
        }
    results["gates"]["g2_camera_only"] = {
        "baseline_mean": round(float(np.mean(rb)), 4),
        "candidate_mean": round(float(np.mean(rc)), 4),
        "required_reduction": 0.25,
        "reduction": round(1.0 - float(np.mean(rc)) / float(np.mean(rb)), 4),
        "pass": float(np.mean(rc)) <= 0.75 * float(np.mean(rb)),
        "all_fidelity": all(r["fidelity"] for r in replay),
        "sentinel_two_seed_means": sent_replay,
        "sentinel_no_worsen": all(v["C_mean"] <= v["B_mean"] for v in sent_replay.values()),
        "replay": replay,
    }

    json.dump(results, open(OUT, "w"), indent=2)
    print(f"\nSaved {OUT} in {time.time()-t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
