"""Quality Finish — standalone non-generative selective-restoration ISP.

Two-step architecture (owner decision, Aug 2026): the remint stages
(V8.8/V8.9 coherent camera pipeline) stay frozen and untouched. This module
is a completely separate sequence that runs AFTER a naturalized file has
been delivered: it removes only compression-visible defects and perceptually
excessive noise, preserves a measured residual noise floor, reconstructs
chroma conservatively, and recovers acutance without boosting the highest
frequency band.

Design follows consultant C8's "selective restoration ISP" (filtered):

  decode -> JPEG-aware cleanup (chroma guide / selective 8x8 deblock /
  mosquito attenuation, standalone JPEG inputs only)
  -> shared masks (shadow, flat, edge, saturated/clipped, chroma-edge)
  -> two-band shadow noise shrinkage with HARD residual floors
     (luma >= ~0.70-0.80x RMS, chroma >= ~0.55-0.70x RMS)
  -> weak gradient cleanup only where banding is already present
  -> saturated-edge chroma-width repair (guided + micro-sharpen, clamped)
  -> optional single-pass 1.6x enlargement (Lanczos3/Y + anti-ring,
     Lanczos2/C, hybrid Lanczos2 at extreme highlights)
  -> ONE masked band-limited luma sharpen (flat gradients k=0, halo k~0)
  -> overshoot limiter -> optional deterministic sub-LSB dither (emergency)
  -> single final JPEG Q95 4:4:4 with EXIF preserved

Deterministic throughout (no RNG; the only pseudo-random source is a
sha256-seeded dither that stays off unless banding QC trips). Pure numpy/PIL.
If any self-QC floor fails, `applied` is False and the input bytes are
shipped unchanged (quality is never allowed to cost acceptance).
"""

import hashlib
import math
import shutil
import time
from pathlib import Path

import numpy as np
from PIL import Image

MODE = "quality-finish"

PRESETS = {
    # C8's three presets. standard is the production default. strong is only
    # for poor standalone JPEGs or unusually noisy naturalization outputs.
    "conservative": {
        "deblock_amt": 0.12,
        "mosquito_luma": 0.08,
        "mosquito_chroma": 0.20,
        "luma_shrink_base": 0.35,
        "shadow_luma_floor": 0.88,
        "shadow_chroma_floor": 0.80,
        "shadow_shrink": 0.5,
        "chroma_guided": 0.45,
        "chroma_gain": 0.04,
        "sharpen_k": 0.05,
        "halo_k_scale": 0.20,
    },
    "standard": {
        "deblock_amt": 0.22,
        "mosquito_luma": 0.15,
        "mosquito_chroma": 0.35,
        "luma_shrink_base": 0.7,
        "shadow_luma_floor": 0.70,
        "shadow_chroma_floor": 0.60,
        "shadow_shrink": 0.7,
        "chroma_guided": 0.65,
        "chroma_gain": 0.08,
        "sharpen_k": 0.09,
        "halo_k_scale": 0.28,
    },
    "strong": {
        "deblock_amt": 0.38,
        "mosquito_luma": 0.25,
        "mosquito_chroma": 0.50,
        "luma_shrink_base": 0.9,
        "shadow_luma_floor": 0.65,
        "shadow_chroma_floor": 0.50,
        "shadow_shrink": 0.9,
        "chroma_guided": 0.85,
        "chroma_gain": 0.12,
        "sharpen_k": 0.12,
        "halo_k_scale": 0.30,
    },
}

# Hard self-QC floors (C8 section 16). Failure -> applied=False.
QC_SSIM_FLOOR = 0.90
QC_NOISE_FLOOR_RATIO = 0.65
QC_FLATNESS_DELTA = 0.05
QC_RINGING_MAX = 0.06
QC_BANDING_TOLERANCE = 0.08

# Final encode policy (C8 section 14).
FINAL_JPEG_QUALITY = 95
FINAL_JPEG_SUBSAMPLING = 0  # 4:4:4

# Delivery cap: passthrough shipping in the worker stays single-encode only
# while the long edge is <= 2048, so enlargement is clamped to that ceiling.
MAX_DELIVERY_EDGE = 2000


# ---------------------------------------------------------------------------
# Fast deterministic filters (numpy only)
# ---------------------------------------------------------------------------

def _box1d(a, r):
    """Box blur along axis=1 (width) with radius r, reflect padding."""
    if r <= 0:
        return a.copy()
    p = np.pad(a, ((0, 0), (r, r)), mode="reflect")
    cum = np.cumsum(p, axis=1)
    return (cum[:, 2 * r:] - cum[:, :-2 * r]) / float(2 * r + 1)


def _box(a, r):
    """Separable square box blur radius r."""
    if r <= 0:
        return a.copy()
    return _box1d(_box1d(a, r).T, r).T


def _gauss(a, sigma):
    """Gaussian blur. Exact small separable kernel below 2.3px; 3-pass box
    above (3 boxes of width w give variance (w^2-1)/4)."""
    if sigma <= 0:
        return a.copy()
    if sigma < 2.3:
        r = max(1, min(8, int(math.ceil(3.0 * sigma))))
        x = np.arange(-r, r + 1, dtype=np.float64)
        k = np.exp(-(x * x) / (2.0 * sigma * sigma))
        k /= k.sum()
        k = k.astype(np.float32)
        p = np.pad(a, ((r, r), (r, r)), mode="reflect")
        win = np.lib.stride_tricks.sliding_window_view(p, (2 * r + 1,), axis=1)
        tmp = np.einsum("hwk,k->hw", win, k)
        win2 = np.lib.stride_tricks.sliding_window_view(tmp, (2 * r + 1,), axis=0)
        return np.einsum("hwk,k->hw", win2, k)
    w = max(3, int(round(math.sqrt(4.0 * sigma * sigma + 1.0))))
    if w % 2 == 0:
        w += 1
    r = (w - 1) // 2
    return _box(a, r)


def _grad_mag(a):
    gx = np.zeros_like(a)
    gy = np.zeros_like(a)
    gx[:, 1:-1] = (a[:, 2:] - a[:, :-2]) * 0.5
    gy[1:-1, :] = (a[2:, :] - a[:-2, :]) * 0.5
    return np.sqrt(gx * gx + gy * gy)


def _dilate(a, r):
    out = a.copy()
    for _ in range(r):
        m = out.copy()
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dy == 0 and dx == 0:
                    continue
                shifted = np.roll(np.roll(out, dy, axis=0), dx, axis=1)
                m = np.maximum(m, shifted)
        out = m
    return out


def _erode(a, r):
    out = a.copy()
    for _ in range(r):
        m = out.copy()
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dy == 0 and dx == 0:
                    continue
                shifted = np.roll(np.roll(out, dy, axis=0), dx, axis=1)
                m = np.minimum(m, shifted)
        out = m
    return out


def _rgb_to_ycbcr(rgb):
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    y = 0.299 * r + 0.587 * g + 0.114 * b
    cb = -0.168736 * r - 0.331264 * g + 0.5 * b
    cr = 0.5 * r - 0.418688 * g - 0.081312 * b
    return y, cb, cr


def _ycbcr_to_rgb(y, cb, cr):
    r = y + 1.402 * cr
    g = y - 0.344136 * cb - 0.714136 * cr
    b = y + 1.772 * cb
    return np.stack([r, g, b], axis=-1)


def _guided_filter(src, guide, r, eps):
    """Edge-preserving guided filter (He et al.) via box filters."""
    mean_i = _box(guide, r)
    mean_p = _box(src, r)
    corr_i = _box(guide * guide, r)
    corr_ip = _box(guide * src, r)
    var_i = corr_i - mean_i * mean_i
    cov_ip = corr_ip - mean_i * mean_p
    a = cov_ip / (var_i + eps)
    b = mean_p - a * mean_i
    mean_a = _box(a, r)
    mean_b = _box(b, r)
    return mean_a * guide + mean_b


# ---------------------------------------------------------------------------
# Enlargement: single-pass Lanczos with anti-ringing + highlight hybrid
# ---------------------------------------------------------------------------

def _resample_axis(a, scale, support, highlight=None):
    """Resample along axis=1. a: (N, M) -> (N, round(M*scale)).

    Lanczos-a kernel with a soft anti-ringing limiter; when `highlight` is
    provided it is a float mask in the OUTPUT domain used to blend toward
    Lanczos2 at extreme highlights (C8 section 7)."""
    if abs(scale - 1.0) < 1e-6:
        return a
    n, m = a.shape
    out_m = max(1, int(round(m * scale)))
    j = np.arange(out_m, dtype=np.float64)
    src = (j + 0.5) / scale - 0.5
    i0 = np.floor(src).astype(np.int64)
    frac = src - i0
    taps = np.arange(-support + 1, support + 1, dtype=np.int64)
    idx = i0[:, None] + taps[None, :]
    idx = np.clip(idx, 0, m - 1)
    x = frac[:, None] - taps[None, :]
    w = np.sinc(x) * np.sinc(x / support)
    w /= w.sum(axis=1, keepdims=True)
    w = w.astype(np.float32)

    gathered = a[:, idx]  # (n, out_m, taps)
    out = np.einsum("nok,ok->no", gathered, w)

    if highlight is not None and support >= 3:
        # Hybrid: blend with Lanczos2 output inside the highlight mask.
        x2 = frac[:, None] - taps[None, :]
        w2 = np.sinc(x2) * np.sinc(x2 / 2.0)
        w2 /= w2.sum(axis=1, keepdims=True)
        w2 = w2.astype(np.float32)
        out2 = np.einsum("nok,ok->no", gathered, w2)
        hl = np.clip(highlight, 0.0, 1.0)
        out = (1.0 - hl) * out + hl * out2

    # Anti-ringing limiter: soft compression beyond the local source extrema.
    local_min = gathered.min(axis=2)
    local_max = gathered.max(axis=2)
    delta = 2.0 / 255.0
    over = out - local_max
    under = local_min - out
    out = np.where(
        over > 0,
        local_max + delta * (1.0 - np.exp(-over / delta)),
        out,
    )
    out = np.where(
        under > 0,
        local_min - delta * (1.0 - np.exp(-under / delta)),
        out,
    )
    return out.astype(np.float32)


def _resize_linear_axis(a, scale):
    """Cheap 2-tap linear resample along axis=1 (for masks)."""
    if abs(scale - 1.0) < 1e-6:
        return a
    n, m = a.shape
    out_m = max(1, int(round(m * scale)))
    j = np.arange(out_m, dtype=np.float64)
    src = np.clip((j + 0.5) / scale - 0.5, 0, m - 1.001)
    i0 = np.floor(src).astype(np.int64)
    f = (src - i0).astype(np.float32)
    i1 = np.clip(i0 + 1, 0, m - 1)
    return (1.0 - f)[None, :] * a[:, i0] + f[None, :] * a[:, i1]


def _resample2d(a, scale, support, highlight=None):
    """Separable resample. `highlight` is a source-domain mask that is
    resized per axis so the hybrid applies in output space."""
    hl_x = None
    if highlight is not None:
        hl_x = _resize_linear_axis(highlight, scale)
    tmp = _resample_axis(a, scale, support, hl_x)
    tmp = tmp.T
    hl_y = None
    if highlight is not None:
        hl_y = _resize_linear_axis(hl_x.T, scale)
    out = _resample_axis(tmp, scale, support, hl_y)
    return out.T


def _upscale_channel(channel, scale, support, highlight=None):
    return _resample2d(channel, scale, support, highlight)


# ---------------------------------------------------------------------------
# Deterministic dither (emergency only, banding QC gated)
# ---------------------------------------------------------------------------

def _deterministic_noise(shape, seed_text, rms):
    h = hashlib.sha256(seed_text.encode("utf-8")).digest()
    need = int(np.prod(shape))
    blocks = (need + len(h) - 1) // len(h)
    raw = (h * blocks)[: need]
    arr = np.frombuffer(raw, dtype=np.uint8).astype(np.float32) / 255.0
    arr = arr.reshape(shape)
    return (arr - arr.mean()) * (rms / max(arr.std(), 1e-9))


# ---------------------------------------------------------------------------
# Main stage
# ---------------------------------------------------------------------------

def _finish_rgb(rgb, preset, scale, standalone, seed_extra):
    """rgb: uint8 HxWx3. Returns (out_uint8, qc_report, passed)."""
    p = PRESETS[preset]
    h, w = rgb.shape[:2]

    # Clamp enlargement to the single-encode delivery ceiling.
    long_edge = max(h, w)
    if scale is not None and scale > 1.0:
        if int(round(long_edge * scale)) > MAX_DELIVERY_EDGE:
            scale = max(1.0, MAX_DELIVERY_EDGE / float(long_edge))
    else:
        scale = 1.0

    img = rgb.astype(np.float32) / 255.0
    y, cb, cr = _rgb_to_ycbcr(img)

    y_before = y.copy()
    cb_before = cb.copy()
    cr_before = cr.copy()

    # ---- JPEG-aware cleanup (standalone inputs only) ---------------------
    # Chroma reconstruction + selective deblock + mosquito attenuation run
    # BEFORE the masks are consumed, per C8's ordering. The in-pipeline
    # entry path (pre-JPEG buffer) skips these entirely.
    if standalone:
        # 8x8 grid luma coordinates (JPEG block phase starts at 0,0).
        grid_x = np.arange(w) % 8 == 0
        grid_y = np.arange(h) % 8 == 0

        # Selective 1-D deblocking (vertical boundaries first).
        for axis, size, grid in (("x", w, grid_x), ("y", h, grid_y)):
            if axis == "x":
                work = y
            else:
                work = y.T
            b = np.arange(1, size)[grid[1:]]  # boundary positions
            if b.size:
                bm2 = np.clip(b - 2, 0, size - 1)
                bm1 = np.clip(b - 1, 0, size - 1)
                bp1 = np.clip(b + 1, 0, size - 1)
                bp2 = np.clip(b + 2, 0, size - 1)
                d = np.abs(work[:, b] - work[:, bm1])
                di = (
                    np.abs(work[:, bm1] - work[:, bm2])
                    + np.abs(work[:, bm2] - work[:, np.clip(b - 3, 0, size - 1)])
                    + np.abs(work[:, bp1] - work[:, b])
                    + np.abs(work[:, bp2] - work[:, bp1])
                ) * 0.25
                strong = (d > 2.2 * di + 0.006) & (di < 0.004)
                # Flat-only: skip real structural edges and textured regions.
                local_std = np.abs(work[:, bp1] - work[:, bm1])
                strong &= local_std < 0.012
                t = 0.5 * p["deblock_amt"] * d * strong.astype(np.float32)
                work[:, bm2] += t * 0.25
                work[:, bm1] += t
                work[:, b] -= t
                work[:, bp1] -= t * 0.25
            if axis == "x":
                y = work
            else:
                y = work.T

        # Mosquito / ringing attenuation: high-frequency residual that hugs
        # strong edges is compression residue, not sensor grain.
        gm = _grad_mag(y)
        strong_edge = gm > 0.07
        edge_band = _dilate(strong_edge.astype(np.float32), 3)
        r_y = y - _gauss(y, 0.7)
        weight = edge_band * np.clip(np.abs(r_y) / 0.02, 0.0, 1.0)
        y = y - p["mosquito_luma"] * r_y * weight

        chroma_cleaned = []
        for ch in (cb, cr):
            r_c = ch - _gauss(ch, 0.7)
            chroma_cleaned.append(ch - p["mosquito_chroma"] * r_c * weight)
        cb, cr = chroma_cleaned

    # ---- Shared masks (computed once, reused by every stage) --------------
    gm = _grad_mag(y)
    strong_edge = gm > 0.07
    edge_band = _dilate(strong_edge.astype(np.float32), 2)

    y_sm = _gauss(y, 1.2)

    # Fine band + local variance drive BOTH the noise model and the
    # structural-flatness mask. Flatness is NOISE-AWARE: "flat" means no
    # structure ABOVE the noise floor -- a grainy mid-luma wall is flat,
    # and a variance-only detector (which reads grain as texture) misses
    # exactly the owner's worst-case region.
    l0 = _gauss(y, 0.6)
    l1 = _gauss(y, 1.2)
    h0 = y - l0
    h1 = l0 - l1
    var_h0 = _box(h0 * h0, 3) - _box(h0, 3) ** 2

    # Per-luminance noise floor (C8 section 3): MAD of the fine band over
    # the LOWEST-VARIANCE (noise-dominated) pixels, per luma bin.
    bins = 16
    bin_idx = np.clip((y * bins).astype(np.int32), 0, bins - 1)
    noise_bool = var_h0 < float(np.quantile(var_h0, 0.25))
    sigma_n = np.zeros(bins, dtype=np.float32)
    for k in range(bins):
        sel = noise_bool & (bin_idx == k)
        if sel.sum() > 8:
            vals = h0[sel]
            med_k = float(np.median(vals))
            sigma_n[k] = 1.4826 * float(np.median(np.abs(vals - med_k)))
    valid = sigma_n > 0
    if valid.any():
        xs = np.nonzero(valid)[0].astype(np.float32)
        ys = sigma_n[valid].astype(np.float32)
        all_x = np.arange(bins, dtype=np.float32)
        sigma_n = np.interp(all_x, xs, ys, left=ys[0], right=ys[-1])
    else:
        sigma_n = np.full(bins, float(np.std(h0)), dtype=np.float32)
    sigma_n = np.maximum(sigma_n, 1e-3)
    sigma_n_img = sigma_n[bin_idx]

    # 8x headroom: after a q92 decode the fine band is dominated by
    # quantization grain with variance ~2x the MAD-based noise floor, so a
    # tighter headroom misclassifies grainy walls as textured and leaves the
    # owner's worst-case region untouched. Structure at >8x noise energy is
    # real texture and keeps its sharpen.
    flat_float = np.clip(
        (8.0 * sigma_n_img ** 2 - var_h0) / (8.0 * sigma_n_img ** 2 + 1e-12),
        0.0,
        1.0,
    )
    flat_float = _box(flat_float, 2)

    shadow = np.clip((0.34 - y_sm) / 0.22, 0.0, 1.0)

    chroma_mag = np.sqrt(cb * cb + cr * cr)
    saturated = chroma_mag > 0.10
    max_rgb = np.maximum(np.maximum(img[..., 0], img[..., 1]), img[..., 2])
    clipped = max_rgb > 0.92
    highlight_mask = _box(
        np.clip(saturated.astype(np.float32) + clipped.astype(np.float32), 0, 1), 2
    )
    highlight_edge = highlight_mask * edge_band

    chroma_edge = _grad_mag(cb) + _grad_mag(cr) > 0.03

    # ---- Shadow noise regularization (two-band Wiener with hard floors) ---
    # C8: shrink ONLY the fine band H0 = Y - G_0.6(Y); preserve the mid band
    # H1 = G_0.6(Y) - G_1.2(Y). Removing both bands is how images become waxy.
    # Luma shrink weight: shadow-boosted baseline. The Wiener gain itself
    # separates noise from structure (texture keeps its energy), so no
    # additional flat gating is needed -- gating was exactly what left the
    # owner's grainy lit walls untouched.
    w_shrink = np.clip(
        p["luma_shrink_base"] + (1.0 - p["luma_shrink_base"]) * shadow, 0.0, 1.0
    )
    wiener = np.clip(
        (var_h0 - (sigma_n_img ** 2)) / (var_h0 + 1e-9),
        0.0,
        1.0,
    ) ** p["shadow_shrink"]
    g = np.maximum(wiener, p["shadow_luma_floor"])
    g = 1.0 - w_shrink * (1.0 - g)
    h0 = h0 * g
    y = l1 + h1 + h0

    # Chroma: same idea, stronger floors.
    flat_bool_c = flat_float > 0.5
    chroma_cleaned = []
    for ch in (cb, cr):
        c_sm = _gauss(ch, 0.8)
        c_hf = ch - c_sm
        var_c = _box(c_hf * c_hf, 3) - _box(c_hf, 3) ** 2
        sigma_c = (
            float(np.std(c_hf[flat_bool_c]))
            if flat_bool_c.sum() > 256
            else float(np.std(c_hf))
        )
        wiener_c = np.clip(
            (var_c - sigma_c ** 2) / (var_c + 1e-9), 0.0, 1.0
        ) ** p["shadow_shrink"]
        g_c = np.maximum(wiener_c, p["shadow_chroma_floor"])
        w_c = np.clip(0.9 * shadow + 1.0 * flat_float, 0.0, 1.0)
        g_c = 1.0 - w_c * (1.0 - g_c)
        chroma_cleaned.append(c_sm + c_hf * g_c)
    cb, cr = chroma_cleaned

    # ---- Gradient cleanup only where banding already exists --------------
    dy = np.abs(y[:, 1:] - y[:, :-1])
    same_col = np.clip(dy < 1.0 / 510.0, 0.0, 1.0).astype(np.float32)
    same_col = np.concatenate([same_col, same_col[:, -1:]], axis=1)
    same_frac = _box1d(same_col, 6)
    banding_region = np.clip(flat_float * np.clip((same_frac - 0.55) / 0.3, 0, 1), 0, 1)
    y = y + 0.25 * banding_region * (_gauss(y, 0.8) - y)

    # ---- Saturated-edge chroma-width repair -------------------------------
    guided_cb = _guided_filter(cb, y, 2, 1e-3)
    guided_cr = _guided_filter(cr, y, 2, 1e-3)
    guide_w = p["chroma_guided"] * edge_band * np.clip(
        chroma_edge.astype(np.float32) * 2.0, 0.0, 1.0
    )
    cb = cb + guide_w * (guided_cb - cb)
    cr = cr + guide_w * (guided_cr - cr)

    # Tiny directional chroma sharpening, clamped to neighbouring extents.
    sat_edge = highlight_edge
    delta_c = 3.0 / 255.0
    chroma_cleaned = []
    for ch in (cb, cr):
        lo = _erode(ch, 2) - delta_c
        hi = _dilate(ch, 2) + delta_c
        sharp = ch + p["chroma_gain"] * (ch - _gauss(ch, 1.0)) * sat_edge
        chroma_cleaned.append(np.clip(sharp, lo, hi))
    cb, cr = chroma_cleaned

    # ---- Optional single-pass enlargement ----------------------------------
    sharpen_scale = scale
    if scale > 1.0 + 1e-6:
        y = _upscale_channel(y, scale, 3, highlight=highlight_mask)
        cb = _upscale_channel(cb, scale, 2, highlight=None)
        cr = _upscale_channel(cr, scale, 2, highlight=None)
        flat_float = _resize_linear_axis(
            _resize_linear_axis(flat_float, scale).T, scale
        ).T
        edge_band = _resize_linear_axis(
            _resize_linear_axis(edge_band, scale).T, scale
        ).T
        highlight_edge = _resize_linear_axis(
            _resize_linear_axis(highlight_edge, scale).T, scale
        ).T

    # ---- One masked band-limited luma sharpen (output-scale aware) ---------
    f = scale
    s1 = 0.6 * f
    s2 = 1.2 * f
    band = _gauss(y, s1) - _gauss(y, s2)
    halo = _box(highlight_edge, 2)
    sharpen_mask = np.clip(1.0 - flat_float - halo * 0.85, 0.0, 1.0)
    k = p["sharpen_k"] * (1.0 - p["halo_k_scale"] * halo) * sharpen_mask
    y_pre = y.copy()
    y = y + k * band

    # Overshoot limiter (soft, C8 section 12): no excursion beyond the local
    # pre-sharpen extrema except a ~0.5-1.0/255 tolerance.
    tol = 1.0 / 255.0
    y_lo = _erode(y_pre, 2) - tol
    y_hi = _dilate(y_pre, 2) + tol
    over = y - y_hi
    under = y_lo - y
    y = np.where(over > 0, y_hi + tol * (1.0 - np.exp(-over / tol)), y)
    y = np.where(under > 0, y_lo - tol * (1.0 - np.exp(-under / tol)), y)

    # ---- QC pass ------------------------------------------------------------
    qc, passed = _run_qc(
        y_before, y, cb_before, cb, cr_before, cr,
        flat_float, edge_band, shadow, standalone, seed_extra, scale,
    )

    # ---- Emergency deterministic dither if banding QC tripped ---------------
    if not passed and qc.get("banding_worse") and scale > 1.0:
        noise = _deterministic_noise(y.shape, f"qf-dither:{seed_extra}", 0.2 / 255.0)
        y = y + noise * flat_float
        qc, passed = _run_qc(
            y_before, y, cb_before, cb, cr_before, cr,
            flat_float, edge_band, shadow, standalone, seed_extra, scale,
            dithered=True,
        )

    out = np.clip(_ycbcr_to_rgb(y, cb, cr), 0.0, 1.0)
    out_u8 = np.rint(out * 255.0).clip(0, 255).astype(np.uint8)
    return out_u8, qc, passed


def _run_qc(
    y_before, y_after, cb_before, cb_after, cr_before, cr_after,
    flat_mask, edge_band, shadow, standalone, seed_extra, scale, dithered=False,
):
    """C8 section 16 self-QC. Returns (report, passed). All comparisons run
    at the NATIVE size: an upscaled candidate is brought back down first, so
    QC measures pixel quality, not enlargement."""
    if y_after.shape != y_before.shape:
        s = y_before.shape[1] / float(y_after.shape[1])
        y_after = _resample2d(y_after, s, 2)
        cb_after = _resample2d(cb_after, s, 2)
        cr_after = _resample2d(cr_after, s, 2)
        edge_band = _resample2d(edge_band, s, 2)
        flat_mask = _resample2d(flat_mask, s, 2)
    elif flat_mask.shape != y_before.shape:
        s = y_before.shape[1] / float(flat_mask.shape[1])
        flat_mask = _resample2d(flat_mask, s, 2)
    hf_before = y_before - _gauss(y_before, 0.7)
    hf_after = y_after - _gauss(y_after, 0.7)

    region = np.clip(shadow + np.clip(flat_mask, 0, 1), 0.0, 1.0)
    region_w = region.sum()
    if region_w < 256:
        region = np.ones_like(region)

    rms_before = float(np.sqrt(np.mean((hf_before * region) ** 2)))
    rms_after = float(np.sqrt(np.mean((hf_after * region) ** 2)))
    noise_floor_ratio = rms_after / max(rms_before, 1e-9)

    # Flatness increase: RELATIVE variance collapse in flat regions (an
    # absolute floor misfires on legitimately deblocked smooth JPEG areas).
    var_hf_before = _box(hf_before * hf_before, 4)
    var_hf_after = _box(hf_after * hf_after, 4)
    flat_bool = flat_mask > 0.5
    if flat_bool.sum() > 256:
        collapse = (var_hf_after < 0.3 * np.maximum(var_hf_before, 1e-12)) & flat_bool
        flat_before = 0.0
        flat_after = float(np.mean(collapse[flat_bool]))
    else:
        flat_before = flat_after = 0.0
    flatness_delta = flat_after - flat_before

    # Ringing: excursions beyond the local pre-sharpen extrema near edges.
    tol = 1.5 / 255.0
    exceed = (
        (y_after > _dilate(y_before, 2) + tol) | (y_after < _erode(y_before, 2) - tol)
    ).astype(np.float32)
    edge_sum = edge_band.sum()
    ringing = (
        float(np.sum(exceed * edge_band)) / max(edge_sum, 256.0)
    )

    # Banding staircase index in flat regions.
    dy_b = np.abs(y_before[:, 1:] - y_before[:, :-1])
    dy_a = np.abs(y_after[:, 1:] - y_after[:, :-1])
    flat_band = np.clip(flat_mask[:, 1:] + flat_mask[:, :-1], 0, 1) > 0.5
    if flat_band.sum() > 256:
        s_before = float(
            np.mean(dy_b[flat_band] <= 1.0 / 510.0)
            / max(float(np.mean((dy_b[flat_band] > 1.0 / 510.0) & (dy_b[flat_band] < 4.0 / 255.0))), 1e-6)
        )
        s_after = float(
            np.mean(dy_a[flat_band] <= 1.0 / 510.0)
            / max(float(np.mean((dy_a[flat_band] > 1.0 / 510.0) & (dy_a[flat_band] < 4.0 / 255.0))), 1e-6)
        )
    else:
        s_before = s_after = 0.0
    banding_worse = s_after > s_before + QC_BANDING_TOLERANCE

    # Chroma spread near saturated edges.
    sat_band = edge_band > 0.5
    if sat_band.sum() > 256:
        g_c_before = _grad_mag(cb_before) + _grad_mag(cr_before)
        g_c_after = _grad_mag(cb_after) + _grad_mag(cr_after)
        g_y_before = _grad_mag(y_before) + 1e-9
        g_y_after = _grad_mag(y_after) + 1e-9
        rc_before = float(np.mean(g_c_before[sat_band]) / np.mean(g_y_before[sat_band]))
        rc_after = float(np.mean(g_c_after[sat_band]) / np.mean(g_y_after[sat_band]))
    else:
        rc_before = rc_after = 0.0
    chroma_ok = rc_after <= rc_before * 1.15 + 0.02

    # Block-grid score (standalone only).
    b8_ok = True
    if standalone:
        h, w = y_before.shape
        gx_b = np.abs(y_before[:, 1:] - y_before[:, :-1])
        gx_a = np.abs(y_after[:, 1:] - y_after[:, :-1])
        grid = (np.arange(w - 1) % 8 == 7)
        smooth_band = np.clip(flat_mask[:, 1:] + flat_mask[:, :-1], 0, 1) > 1.0
        if smooth_band.sum() > 256 and np.sum(~grid) > 0:
            wgt = smooth_band.astype(np.float32)
            grid_num_b = float(np.sum((gx_b * wgt)[:, grid]) / max(float(np.sum(wgt[:, grid])), 1e-9))
            grid_den_b = float(np.sum((gx_b * wgt)[:, ~grid]) / max(float(np.sum(wgt[:, ~grid])), 1e-9))
            grid_num_a = float(np.sum((gx_a * wgt)[:, grid]) / max(float(np.sum(wgt[:, grid])), 1e-9))
            grid_den_a = float(np.sum((gx_a * wgt)[:, ~grid]) / max(float(np.sum(wgt[:, ~grid])), 1e-9))
            b8_before = grid_num_b / max(grid_den_b, 1e-9)
            b8_after = grid_num_a / max(grid_den_a, 1e-9)
            b8_ok = b8_after <= b8_before * 1.25 + 0.02

    # Fidelity: SSIM on luma at a proxy scale (both arrays are native-sized).
    ssim = _ssim_proxy(y_before, y_after, 1.0)

    passed = (
        ssim >= QC_SSIM_FLOOR
        and noise_floor_ratio >= QC_NOISE_FLOOR_RATIO
        and flatness_delta <= QC_FLATNESS_DELTA
        and ringing <= QC_RINGING_MAX
        and b8_ok
        and not banding_worse
        and chroma_ok
    )

    return {
        "ssim": round(ssim, 4),
        "noise_floor_ratio": round(noise_floor_ratio, 3),
        "flatness_delta": round(flatness_delta, 4),
        "ringing": round(ringing, 4),
        "banding_before": round(s_before, 3),
        "banding_after": round(s_after, 3),
        "banding_worse": banding_worse,
        "chroma_spread_before": round(rc_before, 3),
        "chroma_spread_after": round(rc_after, 3),
        "b8_ok": b8_ok,
        "dithered": dithered,
        "passed": passed,
    }, passed


def _ssim_proxy(a, b, scale):
    """Luma SSIM at a bounded proxy resolution (fast, no exact-size dance)."""
    h, w = a.shape
    target = 800
    if max(h, w) > target:
        s = target / float(max(h, w))
        a = _resample2d(a, s, 2)
        b = _resample2d(b, s, 2)
    a = a.astype(np.float64)
    b = b.astype(np.float64)
    r = 3
    ma = _box(a, r).astype(np.float64)
    mb = _box(b, r).astype(np.float64)
    va = (_box(a * a, r) - ma * ma)
    vb = (_box(b * b, r) - mb * mb)
    vab = (_box(a * b, r) - ma * mb)
    c1 = 1e-4
    c2 = 9e-4
    num = (2 * ma * mb + c1) * (2 * vab + c2)
    den = (ma * ma + mb * mb + c1) * (va + vb + c2)
    return float(np.mean(num / den))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def normalize_quality_finish_settings(settings):
    raw = settings if isinstance(settings, dict) else {}
    sub = raw.get("quality_finish") if isinstance(raw.get("quality_finish"), dict) else raw
    preset = sub.get("preset") if isinstance(sub, dict) else None
    if preset not in PRESETS:
        preset = "standard"
    scale_raw = sub.get("scale") if isinstance(sub, dict) else None
    try:
        scale = float(scale_raw) if scale_raw is not None else None
    except (TypeError, ValueError):
        scale = None
    if scale is not None and not (0.9 <= scale <= 2.0):
        scale = 1.6
    # finish_mode only matters to the sequence branch (worker.py); carried
    # through here so reports stay self-describing.
    finish_mode = str(sub.get("finish_mode", "adaptive")) if isinstance(sub, dict) else "adaptive"
    return {
        "mode": MODE,
        "quality_finish": {"preset": preset, "scale": scale, "finish_mode": finish_mode},
    }


def is_quality_finish(settings):
    return isinstance(settings, dict) and settings.get("mode") == MODE


def apply_quality_finish(
    input_path=None,
    output_path=None,
    image=None,
    settings=None,
    seed_extra="",
    creator_id="",
):
    """Run the finisher. Writes the final single JPEG (Q95 4:4:4) to
    `output_path`. On QC failure the ORIGINAL bytes are shipped unchanged and
    `applied` is False (quality never costs acceptance)."""
    started = time.time()
    settings = normalize_quality_finish_settings(settings)
    sub = settings["quality_finish"]
    preset = sub["preset"]
    scale = sub["scale"]

    exif = None
    standalone = False
    if image is not None:
        src = image
        standalone = False
    else:
        src = Image.open(input_path)
        standalone = (src.format or "").upper() in ("JPEG", "JPG")
        try:
            exif = src.info.get("exif")
            if not exif and hasattr(src, "getexif"):
                got = src.getexif()
                if got:
                    exif = got.tobytes()
        except Exception:
            exif = None

    rgb = np.asarray(src.convert("RGB")).astype(np.uint8)
    out_u8, qc, passed = _finish_rgb(rgb, preset, scale, standalone, seed_extra)

    runtime_ms = int((time.time() - started) * 1000)
    if passed:
        out_img = Image.fromarray(out_u8, mode="RGB")
        save_kwargs = {
            "format": "JPEG",
            "quality": FINAL_JPEG_QUALITY,
            "subsampling": FINAL_JPEG_SUBSAMPLING,
            "optimize": True,
        }
        if exif:
            save_kwargs["exif"] = exif
        out_img.save(output_path, **save_kwargs)
    else:
        if input_path is not None:
            shutil.copyfile(input_path, output_path)
        else:
            Image.fromarray(rgb, mode="RGB").save(
                output_path, format="JPEG", quality=FINAL_JPEG_QUALITY, subsampling=FINAL_JPEG_SUBSAMPLING
            )

    return {
        "applied": passed,
        "mode": MODE,
        "preset": preset,
        "scale": None if scale is None else round(scale, 3),
        "standalone_jpeg": standalone,
        "width": rgb.shape[1],
        "height": rgb.shape[0],
        "output_width": out_u8.shape[1],
        "output_height": out_u8.shape[0],
        "runtime_ms": runtime_ms,
        "qc": qc,
        "encode": {
            "quality": FINAL_JPEG_QUALITY,
            "subsampling": "4:4:4",
            "single_encode": True,
        },
    }
