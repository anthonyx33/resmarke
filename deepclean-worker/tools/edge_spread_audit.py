#!/usr/bin/env python3
"""edge_spread_audit.py — 4D-CAM-1 substage edge-spread diagnosis.

Answers the question C88 posed before any camera work:
  Is the edge-widening observed under optics_psf_scale 0.50
  (a) TRUE broadening of the edge transition (PSF/resample composition), or
  (b) RINGING — overshoot/undershoot moving the 10%/90% crossings outward
      while the monotonic fitted width stays put (scene-modulated sharpen)?

Uses only buffers already retrieved and hash-verified:
  OR_postresample.png  (post-resample, pre-camera) and
  O2_precamera.png     (post-camera, pre-codec) for B and C arms of 17 pairs.

Per isolated edge profile (subpixel-aligned, normalized to local step):
  - raw 10-90 width (px) with crossing-candidate count
  - monotonic (isotonic/PAVA) 10-90 width (px)
  - overshoot / undershoot (fraction of step height)
  - out-of-transition excess energy (fraction of step area)
Stratified by orientation (h/v) and contrast (per-image median split).
Diagnostic; no frozen file is modified and no thresholds are production law.
"""

import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

TOOLS_DIR = Path(__file__).resolve().parent
WORKER_DIR = TOOLS_DIR.parent
ROOT = WORKER_DIR.parent
sys.path.insert(0, str(TOOLS_DIR))
sys.path.insert(0, str(WORKER_DIR))

import checkpoint_attribution as ca  # noqa: E402 (frozen primitives only)

CPS = ROOT / "round-4d-cam-1" / "checkpoints"
OUT = ROOT / "round-4d-cam-1" / "edge-spread-audit.json"

HALF_W = 21          # profile half-length in px
CENTER_SMOOTH = 0.5  # smoothing for edge-center detection only
PROFILE_CAP = 320    # max profiles per image


def isotonic(y):
    """Pool-adjacent-violators isotonic regression (non-decreasing)."""
    blocks_v, blocks_w = [], []
    for v in y:
        blocks_v.append(float(v))
        blocks_w.append(1.0)
        while len(blocks_v) >= 2 and blocks_v[-1] < blocks_v[-2]:
            w = blocks_w[-1] + blocks_w[-2]
            m = (blocks_v[-1] * blocks_w[-1] + blocks_v[-2] * blocks_w[-2]) / w
            blocks_v.pop(); blocks_w.pop()
            blocks_v.pop(); blocks_w.pop()
            blocks_v.append(m); blocks_w.append(w)
    edges = np.concatenate(([0], np.cumsum(blocks_w)))
    out = np.zeros(len(y))
    for i, (a, b) in enumerate(zip(edges[:-1], edges[1:])):
        out[int(a):int(b)] = blocks_v[i]
    return out


def _bilinear(a, y, x):
    y = np.clip(y, 0, a.shape[0] - 1.001)
    x = np.clip(x, 0, a.shape[1] - 1.001)
    y0, x0 = int(y), int(x)
    fy, fx = y - y0, x - x0
    return (a[y0, x0] * (1 - fy) * (1 - fx) + a[y0, x0 + 1] * (1 - fy) * fx
            + a[y0 + 1, x0] * fy * (1 - fx) + a[y0 + 1, x0 + 1] * fy * fx)


def edge_profiles(luma):
    """Return list of metric dicts for isolated strong edges in `luma`."""
    img = Image.fromarray((np.clip(luma, 0, 1) * 255).astype(np.uint8))
    sm = np.asarray(img.filter(ImageFilter.GaussianBlur(radius=CENTER_SMOOTH)),
                    dtype=np.float64) / 255.0
    gy, gx = np.gradient(sm)
    mag = np.hypot(gx, gy)
    thr = np.percentile(mag, 92.0)

    centers = []
    for cy in range(HALF_W, luma.shape[0] - HALF_W, 3):
        for cx in range(HALF_W, luma.shape[1] - HALF_W, 3):
            m = mag[cy, cx]
            if m < thr:
                continue
            dx, dy = gx[cy, cx], gy[cy, cx]
            norm = max(float(np.hypot(dx, dy)), 1e-9)
            ux, uy = dx / norm, dy / norm
            if (m >= _bilinear(mag, cy + uy, cx + ux) and
                    m >= _bilinear(mag, cy - uy, cx - ux) and
                    m >= _bilinear(mag, cy + 2 * uy, cx + 2 * ux) and
                    m >= _bilinear(mag, cy - 2 * uy, cx - 2 * ux)):
                centers.append((m, cy, cx))
    centers.sort(reverse=True)

    chosen, used = [], set()
    for m, cy, cx in centers:
        if len(chosen) >= PROFILE_CAP:
            break
        if any((cy - py) ** 2 + (cx - px) ** 2 <= 36 for py, px in used):
            continue
        used.add((cy, cx))
        chosen.append((cy, cx))

    rows = []
    for cy, cx in chosen:
        dx, dy = gx[cy, cx], gy[cy, cx]
        horizontal = abs(dy) >= abs(dx)  # edge runs along x; profile along y
        axis = 0 if horizontal else 1
        xs = np.arange(-HALF_W, HALF_W + 1, dtype=np.float64)
        raw = luma[cy - HALF_W:cy + HALF_W + 1, cx] if horizontal else luma[cy, cx - HALF_W:cx + HALF_W + 1]
        raw = raw.astype(np.float64)
        mline = mag[cy - HALF_W:cy + HALF_W + 1, cx] if horizontal else mag[cy, cx - HALF_W:cx + HALF_W + 1]
        # parabolic subpixel refinement of the magnitude peak along the profile
        idx = HALF_W
        if mline[idx - 1] + mline[idx + 1] - 2 * mline[idx] < 0:
            off = 0.5 * (mline[idx - 1] - mline[idx + 1]) / (mline[idx - 1] + mline[idx + 1] - 2 * mline[idx])
        else:
            off = 0.0
        p = np.interp(xs, xs - off, raw)
        lo, hi = np.percentile(p[np.abs(xs) >= 8], 5), np.percentile(p[np.abs(xs) >= 8], 95)
        step = hi - lo
        if step < 0.04:
            continue
        pn = (p - lo) / step
        if pn[HALF_W - 3] > pn[HALF_W + 3]:  # make rising
            pn = pn[::-1]
        # crossings of 0.1 and 0.9
        crosses = []
        for level in (0.1, 0.9):
            s = np.sign(pn - level)
            hits = np.where(np.diff(s) != 0)[0]
            crosses.extend([xs[h] + (level - pn[h]) / (pn[h + 1] - pn[h]) if pn[h + 1] != pn[h] else xs[h]
                            for h in hits])
        crosses = sorted(crosses)
        n_cross = len(crosses)
        if n_cross >= 2:
            raw_width = crosses[-1] - crosses[0]
        else:
            continue
        mono = isotonic(pn)
        c10 = np.interp(0.1, mono, xs)
        c90 = np.interp(0.9, mono, xs)
        mono_width = abs(c90 - c10)
        if mono_width < 0.2 or mono_width > 2 * HALF_W - 2:
            continue
        overshoot = float(max(0.0, pn.max() - 1.0))
        undershoot = float(max(0.0, -pn.min()))
        outside = np.abs(xs) > 0.75 * mono_width
        if outside.any():
            oot = float(np.mean(np.maximum(pn - 1.0, 0)[outside]) +
                        np.mean(np.maximum(-pn, 0)[outside]))
        else:
            oot = 0.0
        rows.append({
            "orientation": "h" if horizontal else "v",
            "contrast": float(step),
            "raw_width": float(raw_width),
            "mono_width": float(mono_width),
            "overshoot": overshoot,
            "undershoot": undershoot,
            "oot_energy": oot,
            "n_crossings": n_cross,
        })
    return rows


def summarize(rows):
    if not rows:
        return None
    keys = ("raw_width", "mono_width", "overshoot", "undershoot", "oot_energy", "n_crossings")
    med = {k: float(np.median([r[k] for r in rows])) for k in keys}
    med["n_profiles"] = len(rows)
    by_ori, by_con = {}, {}
    for ori in ("h", "v"):
        sub = [r for r in rows if r["orientation"] == ori]
        if sub:
            by_ori[ori] = {k: float(np.median([r[k] for r in sub]))
                           for k in ("raw_width", "mono_width", "overshoot", "oot_energy")}
            by_ori[ori]["n"] = len(sub)
    if rows:
        cmed = float(np.median([r["contrast"] for r in rows]))
        for tag, sub in (("high", [r for r in rows if r["contrast"] >= cmed]),
                         ("low", [r for r in rows if r["contrast"] < cmed])):
            if sub:
                by_con[tag] = {k: float(np.median([r[k] for r in sub]))
                               for k in ("raw_width", "mono_width", "overshoot", "oot_energy")}
                by_con[tag]["n"] = len(sub)
    med["by_orientation"] = by_ori
    med["by_contrast"] = by_con
    return med


def main():
    from round_4d_cam_1_gates import PAIRS  # noqa: E402

    audit = {"pairs": [], "summary": {}}
    all_rows = {"B": [], "C": [], "OR": []}
    for img, seed, bid, cid in PAIRS:
        row = {"image": img, "seed": seed}
        for tag, jid in (("B", bid), ("C", cid)):
            or_rgb = np.asarray(Image.open(CPS / jid / "OR_postresample.png").convert("RGB"),
                                dtype=np.float64) / 255.0
            o2_rgb = np.asarray(Image.open(CPS / jid / "O2_precamera.png").convert("RGB"),
                                dtype=np.float64) / 255.0
            or_luma = ca._luma(or_rgb)
            o2_luma = ca._luma(o2_rgb)
            or_prof = edge_profiles(or_luma)
            o2_prof = edge_profiles(o2_luma)
            row[tag] = {"OR": summarize(or_prof), "O2": summarize(o2_prof)}
            all_rows[tag].extend(o2_prof)
            if tag == "B":
                all_rows["OR"].extend(or_prof)
            print(f"{img}/{seed} {tag}: OR n={len(or_prof)} (w{row[tag]['OR']['mono_width']:.2f}px) "
                  f"O2 n={len(o2_prof)} (raw {row[tag]['O2']['raw_width']:.2f}px / "
                  f"mono {row[tag]['O2']['mono_width']:.2f}px / os {row[tag]['O2']['overshoot']:.4f} / "
                  f"oot {row[tag]['O2']['oot_energy']:.4f})", flush=True)
        audit["pairs"].append(row)
    audit["summary"] = {tag: summarize(rows) for tag, rows in all_rows.items()}
    json.dump(audit, open(OUT, "w"), indent=1)
    print("\nGlobal medians (O2):")
    for tag in ("B", "C"):
        s = audit["summary"][tag]
        print(f"  {tag}: n={s['n_profiles']} raw={s['raw_width']:.2f} mono={s['mono_width']:.2f} "
              f"os={s['overshoot']:.4f} us={s['undershoot']:.4f} oot={s['oot_energy']:.4f} "
              f"xings={s['n_crossings']:.2f}")
    s = audit["summary"]["OR"]
    print(f"  OR: n={s['n_profiles']} raw={s['raw_width']:.2f} mono={s['mono_width']:.2f} "
          f"os={s['overshoot']:.4f} oot={s['oot_energy']:.4f}")
    print(f"Saved {OUT}")


if __name__ == "__main__":
    main()
