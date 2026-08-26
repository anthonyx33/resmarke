"""checkpoint_attribution.py — V10 Priority-1 tool (zero vendor grades).

Metrics are diagnostics; they do not drive decisions until owner-approved.

Locates WHERE quality is lost in the remint chain by comparing each
checkpoint against a GEOMETRY-MATCHED reference (the original resampled
only to the checkpoint's lattice), so the measurements separate processing
damage from resampling itself.

Usage:
  python checkpoint_attribution.py <checkpoint_dir> [--jsonl out.jsonl]

The checkpoint dir (populated by setting DEEPCLEAN_CHECKPOINT_DIR on the
worker) contains:
  O0_source.png       the original
  O1_postwash.png     post-wash, pre-camera
  O2_precamera.png    post-camera, pre-stage-1-codec (chosen candidate)
  O3_stage1.png       delivered stage-one file (decoded)
  O4_preencode.png    finisher output pre-final-encode
  O5_final.png        final delivery (decoded)

For every checkpoint Oi: Ri = O0 resampled to Oi's geometry (LANCZOS).
Metrics are computed on the full frame + fixed positional bands (center,
top, left, bottom):
  EATR        p95 Sobel magnitude ratio  edge(Oi) / edge(Ri)
  HFTR_H0/H1/H2  band-RMS ratio (I-g0.7 / g0.7-g1.4 / g1.4-g4.0)
  rho1, rho2  spatial horizontal/vertical lag-1/2 correlation of Oi-Ri
  corr_len    first lag where smooth-residual autocorrelation < 0.1
  luma_rms    smooth-region residual RMS (LSB)
  chroma_rms  Cb/Cr residual RMS (LSB)

Transition losses between consecutive checkpoints feed the dominance bands:
  loss_i = max(|min(dEATR,0)|, |min(dHFTR,0)|)   (normalized and native)
  normalized: Ri = O0 resampled to Oi's geometry (resample cost removed)
  native:     Oi resampled to O0's geometry (resample cost INCLUDED)
  PRIMARY >=35% of attributable loss · CO-PRIMARY >=25% · SECONDARY 10-25% ·
  NEGLIGIBLE <10%. Runner-up ratio is confidence evidence only.
Report-only; no thresholds are production constants.
"""

import argparse
import json
import math
import os
import sys

import numpy as np
from PIL import Image, ImageFilter

CHECKPOINTS = [
    ("O0", "O0_source.png"),
    ("O1", "O1_postwash.png"),
    ("O2", "O2_precamera.png"),
    ("O3", "O3_stage1.png"),
    ("O4", "O4_preencode.png"),
    ("O5", "O5_final.png"),
]

# Fixed positional bands (normalized boxes x0,y0,x1,y1) — hand-auditable,
# registration-free (the chain can drift slightly). These are not semantic
# regions and must not be described as semantic masks.
POSITIONAL_BANDS = {
    "full": (0.0, 0.0, 1.0, 1.0),
    "center": (0.25, 0.25, 0.75, 0.75),
    "top": (0.15, 0.02, 0.85, 0.35),
    "left": (0.02, 0.25, 0.35, 0.75),
    "bottom": (0.15, 0.65, 0.85, 0.98),
}


def _load(path):
    return np.asarray(Image.open(path).convert("RGB")).astype(np.float64) / 255.0


def _luma(a):
    return 0.2126 * a[..., 0] + 0.7152 * a[..., 1] + 0.0722 * a[..., 2]


def _resample_to(a, shape):
    h, w = shape[:2]
    img = Image.fromarray((np.clip(a, 0.0, 1.0) * 255.0).astype(np.uint8))
    img = img.resize((w, h), Image.Resampling.LANCZOS)
    return np.asarray(img).astype(np.float64) / 255.0


def _gauss(y, sigma):
    """Box-free gaussian via PIL."""
    img = Image.fromarray((np.clip(y, 0.0, 1.0) * 255.0).astype(np.uint8))
    img = img.filter(ImageFilter.GaussianBlur(radius=sigma))
    return np.asarray(img).astype(np.float64) / 255.0


def _crop(a, box):
    h, w = a.shape[:2]
    x0, y0, x1, y1 = box
    return a[int(y0 * h) : int(y1 * h), int(x0 * w) : int(x1 * w)]


def _edge_mag(y):
    gy, gx = np.gradient(y)
    return np.hypot(gx, gy)


def _edge_width_10_90(y):
    """Median run-length of strong gradient profile (proxy for 10-90%
    edge spread, V11 metric)."""
    mag = _edge_mag(y)
    thr = np.percentile(mag, 90)
    widths = []
    for axis in (0, 1):
        prof = np.max(mag, axis=1 - axis)
        above = prof > thr
        idx = np.where(np.diff(np.concatenate(([0], above.astype(int), [0]))))[0]
        for a, b in zip(idx[::2], idx[1::2]):
            if 2 <= (b - a) <= 64:
                widths.append(float(b - a))
    return float(np.median(widths)) if widths else 0.0


def _delta_e76(oi, ri):
    """Median CIE-Lab (D65) colour difference, 1976 approximation (V11)."""

    def srgb_to_lab(a):
        a = np.clip(a, 0.0, 1.0)
        lin = np.where(a <= 0.04045, a / 12.92, ((a + 0.055) / 1.055) ** 2.4)
        xyz = np.dot(lin, np.array([[0.4124, 0.3576, 0.1805],
                                    [0.2126, 0.7152, 0.0722],
                                    [0.0193, 0.1192, 0.9505]]).T)

        def f(t):
            d = 6.0 / 29.0
            return np.where(t > d ** 3, np.cbrt(t), t / (3 * d ** 2) + 4.0 / 29.0)

        fx, fy, fz = f(xyz[..., 0]), f(xyz[..., 1]), f(xyz[..., 2])
        L = 116.0 * fy - 16.0
        aa = 500.0 * (fx - fy)
        bb = 200.0 * (fy - fz)
        return np.stack([L, aa, bb], axis=-1)

    return float(np.median(np.linalg.norm(srgb_to_lab(oi) - srgb_to_lab(ri), axis=-1)))


def _staircase(y):
    """Step-ness index: share of +-1 quantized deltas among small deltas
    (V11 banding proxy)."""
    q = (np.clip(y, 0.0, 1.0) * 255.0).astype(np.uint8)
    dx = np.abs(np.diff(q.astype(np.int16), axis=1))
    ones = np.mean(dx == 1)
    small = np.mean((dx >= 1) & (dx <= 3))
    return float(ones / max(small, 1e-6))


def _metrics_for(oi, ri):
    """oi / ri must be same geometry. Returns dict of metrics."""
    yo, yref = _luma(oi), _luma(ri)
    eo, er = _edge_mag(yo), _edge_mag(yref)
    eatr = float(np.percentile(eo, 95) / max(np.percentile(er, 95), 1e-9))

    bands_o = {"H0": yo - _gauss(yo, 0.7), "H1": _gauss(yo, 0.7) - _gauss(yo, 1.4),
               "H2": _gauss(yo, 1.4) - _gauss(yo, 4.0)}
    bands_r = {"H0": yref - _gauss(yref, 0.7), "H1": _gauss(yref, 0.7) - _gauss(yref, 1.4),
               "H2": _gauss(yref, 1.4) - _gauss(yref, 4.0)}
    hftr = {k: float(np.sqrt(np.mean(bands_o[k] ** 2)) / max(np.sqrt(np.mean(bands_r[k] ** 2)), 1e-9))
            for k in bands_o}

    residual = yo - yref
    # smooth mask: low edge energy in the REFERENCE (structure-poor regions)
    smooth = _edge_mag(yref) < np.percentile(_edge_mag(yref), 30)
    if smooth.sum() < 64:
        smooth = np.ones_like(smooth)
    res_s = residual[smooth]
    spatial = _spatial_correlations(residual, smooth)

    luma_rms = float(np.sqrt(np.mean(res_s ** 2))) * 255.0
    co = oi[..., 1:3] - ri[..., 1:3]
    chroma_rms = float(np.sqrt(np.mean(co ** 2))) * 255.0
    return {
        "eatr": eatr,
        "hftr": hftr,
        **spatial,
        "luma_rms_lsb": luma_rms,
        "chroma_rms_lsb": chroma_rms,
        "edge_width_10_90": _edge_width_10_90(yo),
        "delta_e76": _delta_e76(oi, ri),
        "staircase": _staircase(yo),
    }


def _masked_spatial_corr(field, mask, dy, dx):
    """Pearson correlation over genuine 2-D neighbours selected by mask."""
    height, width = field.shape
    if dy >= height or dx >= width:
        return 0.0
    left = field[: height - dy or None, : width - dx or None]
    right = field[dy:, dx:]
    left_mask = mask[: height - dy or None, : width - dx or None]
    right_mask = mask[dy:, dx:]
    valid = left_mask & right_mask
    if int(valid.sum()) < 64:
        return 0.0
    first = left[valid]
    second = right[valid]
    if float(np.var(first)) < 1e-12 or float(np.var(second)) < 1e-12:
        return 0.0
    return float(np.corrcoef(first, second)[0, 1])


def _spatial_correlations(field, mask):
    rho1_h = _masked_spatial_corr(field, mask, 0, 1)
    rho1_v = _masked_spatial_corr(field, mask, 1, 0)
    rho2_h = _masked_spatial_corr(field, mask, 0, 2)
    rho2_v = _masked_spatial_corr(field, mask, 2, 0)
    corr_len = 0
    for lag in range(1, 32):
        values = [
            _masked_spatial_corr(field, mask, 0, lag),
            _masked_spatial_corr(field, mask, lag, 0),
        ]
        correlation = float(np.mean(values))
        corr_len = lag
        if correlation < 0.1:
            break
    return {
        "rho1": float(np.mean([rho1_h, rho1_v])),
        "rho2": float(np.mean([rho2_h, rho2_v])),
        "rho1_h": rho1_h,
        "rho1_v": rho1_v,
        "rho2_h": rho2_h,
        "rho2_v": rho2_v,
        "corr_len": corr_len,
    }


def _combine(positional_band_metrics):
    """Average metrics across positional bands; eatr/hftr per band."""
    metrics = list(positional_band_metrics)
    out = {"eatr": float(np.mean([m["eatr"] for m in metrics]))}
    for band in ("H0", "H1", "H2"):
        out[f"hftr_{band}"] = float(np.mean([m["hftr"][band] for m in metrics]))
    for k in ("rho1", "rho2", "rho1_h", "rho1_v", "rho2_h", "rho2_v",
              "corr_len", "luma_rms_lsb", "chroma_rms_lsb",
              "edge_width_10_90", "delta_e76", "staircase"):
        out[k] = float(np.mean([m[k] for m in metrics]))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("checkpoint_dir")
    ap.add_argument("--jsonl", default=None)
    args = ap.parse_args()

    files = {}
    for name, fname in CHECKPOINTS:
        path = os.path.join(args.checkpoint_dir, fname)
        if os.path.exists(path):
            files[name] = path
    if "O0" not in files:
        print("O0_source.png missing — cannot build references.", file=sys.stderr)
        sys.exit(2)
    present = [n for n, _ in CHECKPOINTS if n in files]
    if len(present) < 2:
        print("Need at least O0 + one checkpoint.", file=sys.stderr)
        sys.exit(2)

    o0 = _load(files["O0"])
    rows = {}
    for name in present:
        oi = _load(files[name])
        ri = _resample_to(o0, oi.shape)
        positional_metrics = {}
        for band, box in POSITIONAL_BANDS.items():
            positional_metrics[band] = _metrics_for(_crop(oi, box), _crop(ri, box))
        rows[name] = {"positional_bands": positional_metrics,
                      "combined": _combine(positional_metrics.values()),
                      "dims": list(oi.shape[:2])}
        # native-reference metrics: checkpoint resampled UP to O0 geometry, so the
        # lattice/resample cost is INCLUDED instead of normalized away.
        oi_native = _resample_to(oi, o0.shape)
        native_metrics = {}
        for band, box in POSITIONAL_BANDS.items():
            native_metrics[band] = _metrics_for(_crop(oi_native, box), _crop(o0, box))
        rows[name]["native"] = _combine(native_metrics.values())

    # transition losses + dominance
    order = [n for n, _ in CHECKPOINTS if n in files]
    losses = {}
    for a, b in zip(order, order[1:]):
        da = rows[b]["combined"]["eatr"] - rows[a]["combined"]["eatr"]
        dh = rows[b]["combined"]["hftr_H1"] - rows[a]["combined"]["hftr_H1"]
        losses[f"{a}->{b}"] = {
            "dEATR": round(da, 4),
            "dHFTR_H1": round(dh, 4),
            "loss": round(max(abs(min(da, 0.0)), abs(min(dh, 0.0))), 4),
        }
    native_losses = {}
    for a, b in zip(order, order[1:]):
        da = rows[b]["native"]["eatr"] - rows[a]["native"]["eatr"]
        dh = rows[b]["native"]["hftr_H1"] - rows[a]["native"]["hftr_H1"]
        native_losses[f"{a}->{b}"] = round(max(abs(min(da, 0.0)), abs(min(dh, 0.0))), 4)
    total = sum(v["loss"] for v in losses.values()) or 1e-9
    ranked = sorted(losses.items(), key=lambda kv: -kv[1]["loss"])
    nz = [v["loss"] for _, v in ranked if v["loss"] > 1e-4]
    second = nz[1] if len(nz) > 1 else 0.0
    bands = {}
    for name, v in ranked:
        share = v["loss"] / total
        if share >= 0.35:
            band = "PRIMARY"
        elif share >= 0.25:
            band = "CO-PRIMARY"
        elif share >= 0.10:
            band = "SECONDARY"
        else:
            band = "NEGLIGIBLE"
        bands[name] = {"band": band, "share": round(share, 3),
                       "runnerup_ratio": round(v["loss"] / (second or 1e-9), 2)}
    print("Transition loss bands (normalized | native, native includes resample):")
    for name, v in ranked:
        b = bands[name]
        print(f"  {name} loss={v['loss']:.4f} (native {native_losses.get(name, 0):.4f}) "
              f"{b['band']} share={b['share']} runnerup_ratio={b['runnerup_ratio']}")

    print("Checkpoint metrics (positional-band averaged):")
    for name in order:
        c = rows[name]["combined"]
        print(f"  {name} dims={rows[name]['dims']} EATR={c['eatr']:.3f} "
              f"HFTR H0/H1/H2={c['hftr_H0']:.3f}/{c['hftr_H1']:.3f}/{c['hftr_H2']:.3f} "
              f"rho1 h/v={c['rho1_h']:.3f}/{c['rho1_v']:.3f} "
              f"rho2 h/v={c['rho2_h']:.3f}/{c['rho2_v']:.3f} corr_len={c['corr_len']:.1f} "
              f"lumaRMS={c['luma_rms_lsb']:.2f}LSB chromaRMS={c['chroma_rms_lsb']:.2f}LSB "
              f"edgeW={c['edge_width_10_90']:.1f}px dE76={c['delta_e76']:.2f} "
              f"stair={c['staircase']:.3f}")
    print("\nTransition losses (negative = detail lost):")
    for name, v in ranked:
        b = bands[name]
        print(f"  {name}: dEATR={v['dEATR']:+.3f} dHFTR_H1={v['dHFTR_H1']:+.3f} "
              f"loss={v['loss']:.3f} [{b['band']}]")
    primary = [n for n, b in bands.items() if b["band"] == "PRIMARY"]
    if primary:
        print("\nPRIMARY transitions:", ", ".join(primary))
        print("Next paid A/B targets the largest measured loss — budget "
              "follows evidence (EXPERT_TESTING_SYSTEM.md §5/§6).")
    else:
        print("\nNo PRIMARY band (losses spread) — treat the largest loss as the "
              "first target; do not force a winner.")

    if args.jsonl:
        record = {
            "checkpoints": {n: {"metrics": rows[n]["combined"],
                                "native_metrics": rows[n]["native"],
                                "positional_bands": rows[n]["positional_bands"],
                                "dims": rows[n]["dims"]} for n in order},
            "transitions": losses,
            "transitions_native": native_losses,
            "bands": bands,
        }
        with open(args.jsonl, "a") as fh:
            fh.write(json.dumps(record) + "\n")
        print(f"\nJSONL appended: {args.jsonl}")


if __name__ == "__main__":
    main()
