"""Quality Finish — standalone non-generative selective-restoration ISP (v2).

Two-step architecture (owner decision, Aug 2026): the remint stages
(V8.8/V8.9 coherent camera pipeline) stay frozen and untouched. This module
is a completely separate sequence that runs AFTER a naturalized file has
been delivered and restores perceived quality without any generative model.

v2 (consultant C8 second iteration, filtered): the noise field is now
optimized for the DESTINATION resolution, not for preservation of the
source-resolution noise field. The objectionable grain in sky/walls lived
in the mid band H1 we previously preserved fully, enlarged by the 1.6x
interpolation into coarse correlated texture (measured rho1 ~0.7+).

  decode -> JPEG-aware cleanup (chroma guide / selective 8x8 deblock /
  mosquito attenuation, standalone JPEG inputs only)
  -> shared masks + FOUR-band decomposition (B / H2 / H1 / H0)
  -> texture-confidence map (structure anisotropy + H1/H2 cross-scale
     support + H2 energy): real material texture keeps its bands, noise
     does not
  -> region-conditioned H0 + H1 suppression BEFORE enlargement
     (sky/walls/cone interiors get C8's table; texture preserved;
     B and H2 always intact; luminance keeps a small SNR weight)
  -> weak gradient cleanup only where banding is already present
  -> saturated-edge chroma-width repair (guided + micro-sharpen, clamped)
  -> dual-kernel enlargement: Lanczos3 for structure, Mitchell for smooth
     regions, feathered by texture confidence; Lanczos2 chroma
  -> destination-scale residual QC: lag-1 autocorrelation, residual RMS,
     H1/H0 ratio -- if the residual became coarse, one light smooth-region
     correction (max 2 passes)
  -> SNR-gated mid-band sharpen (k~3: sharpen structure, never noise)
     with fail-soft gain reduction + overshoot limiter
  -> v3: ALWAYS-ON gradient-masked shaped dither immediately before 8-bit
     quantization (luma ~0.35 LSB RMS / chroma ~0.15 LSB RMS, deterministic
     blue-noise-like tile) + chroma gradient decontouring + a case-B guard
     (local surface reconstruction only when the float buffer itself
     carries quantization staircases)
  -> single final JPEG Q97 4:4:4 with EXIF preserved + delivery-chain
     self-check (dimensions + sampling factors parsed from the JPEG SOF
     marker) and a float/8-bit/JPEG banding-origin diagnostic in the report

Deterministic throughout (no RNG; the only pseudo-random source is a
sha256-seeded dither that stays off unless banding QC trips). Pure numpy/PIL.
Hard self-QC rail: SSIM >= 0.90 and anti-plastic residual floors; failures
ship the input bytes unchanged (quality never costs acceptance).
"""

import hashlib
import io
import math
import shutil
import time
from pathlib import Path

import numpy as np
from PIL import Image

MODE = "quality-finish"

PRESETS = {
    # C8 v2 gains: h0_smooth/h1_smooth are the fine/mid band RETENTION in
    # smooth regions (sky, painted walls, cone interiors). Texture confidence
    # raises retention toward 1.0; B and H2 are always preserved.
    "conservative": {
        "deblock_amt": 0.12,
        "mosquito_luma": 0.08,
        "mosquito_chroma": 0.20,
        "h0_smooth": 0.70,
        "h1_smooth": 0.75,
        "shadow_chroma_floor": 0.80,
        "chroma_guided": 0.45,
        "chroma_gain": 0.04,
        "sharpen_k": 0.05,
        "snr_k": 3.0,
        "halo_k_scale": 0.20,
        "dither_luma": 0.30 / 255.0,
        "dither_chroma": 0.12 / 255.0,
        "decorr_max_passes": 6,
        "decorr_gain": 0.7,
    },
    "standard": {
        "deblock_amt": 0.22,
        "mosquito_luma": 0.15,
        "mosquito_chroma": 0.35,
        "h0_smooth": 0.45,
        "h1_smooth": 0.45,
        "shadow_chroma_floor": 0.60,
        "chroma_guided": 0.65,
        "chroma_gain": 0.08,
        "sharpen_k": 0.09,
        "snr_k": 3.0,
        "halo_k_scale": 0.28,
        "dither_luma": 0.35 / 255.0,
        "dither_chroma": 0.15 / 255.0,
        "decorr_max_passes": 6,
        "decorr_gain": 0.7,
    },
    "strong": {
        "deblock_amt": 0.38,
        "mosquito_luma": 0.25,
        "mosquito_chroma": 0.50,
        "h0_smooth": 0.35,
        "h1_smooth": 0.35,
        "shadow_chroma_floor": 0.50,
        "chroma_guided": 0.85,
        "chroma_gain": 0.12,
        "sharpen_k": 0.12,
        "snr_k": 3.0,
        "halo_k_scale": 0.30,
        "dither_luma": 0.40 / 255.0,
        "dither_chroma": 0.20 / 255.0,
        "decorr_max_passes": 6,
        "decorr_gain": 0.7,
    },
    # Fidelity HD (C8 v4): for the pre-JPEG stage-1 handoff at delivery
    # resolution. Texture retention rides the tex map toward 1.0; smooth
    # regions keep a light suppression floor; decorrelation is capped at
    # 2 passes (six spatial predictions is a detail killer); sharpen stays
    # below 0.6x standard. No upscale is expected (stage 1 already sits at
    # the delivery lattice), and no JPEG-deblock path runs (buffer handoff).
    "fidelity": {
        "deblock_amt": 0.05,
        "mosquito_luma": 0.04,
        "mosquito_chroma": 0.10,
        "h0_smooth": 0.60,
        "h1_smooth": 0.65,
        "shadow_chroma_floor": 0.70,
        "chroma_guided": 0.55,
        "chroma_gain": 0.06,
        "sharpen_k": 0.05,
        "snr_k": 3.0,
        "halo_k_scale": 0.22,
        "dither_luma": 0.30 / 255.0,
        "dither_chroma": 0.12 / 255.0,
        "decorr_max_passes": 2,
        "decorr_gain": 0.6,
    },
}

# Hard self-QC rails (C8 v2). Failure -> applied=False (ship input unchanged).
QC_SSIM_FLOOR = 0.90
QC_RESIDUAL_RMS_MIN = 0.15 / 255.0  # anti-plastic floor at destination scale
QC_RHO1_MAX = 0.40                  # lag-1 autocorrelation ceiling, smooth regions
                                    # (C8 v3 sky-specific target: <0.30 preferred;
                                    #  the dither stage whitens the residual)
QC_FLATNESS_DELTA = 0.08
QC_RINGING_MAX = 0.06
QC_BANDING_TOLERANCE = 0.08

# Fidelity reference gate (C8 v4): the finisher may hold the ORIGINAL source
# as its fidelity target. Texture-detail transfer is the "360p" detector —
# detail-band energy in the output vs the source. Below the floor the finish
# is rejected and the stage-1 buffer ships instead.
REF_TDR_FLOOR = 0.60
REF_TDR_WARN = 0.75

# Mobile Clean material branch (C8 v5): rendered walls etc. are large
# smooth-material surfaces whose residual should read almost invisible at
# mobile scale, while coherent material structure is preserved. The branch
# auto-triggers on coverage + severity; no user knob.
WALL_COVERAGE_MIN = 0.06
WALL_RMS_TRIGGER = 0.48 / 255.0
WALL_CNF_TRIGGER = 0.30
WALL_RMS_BRIGHT = 0.32 / 255.0
WALL_RMS_DARK = 0.55 / 255.0
WALL_CHROMA_RMS = 0.08 / 255.0
WALL_DITHER_Y = 0.13 / 255.0
WALL_DITHER_C = 0.04 / 255.0

# V6 Final Polish (C8 v6): à-trous coefficient shrinkage. g_min per scale
# (small unsupported coefficients get gain -> g_min; large ones -> 1); tau
# is the soft-shrink knee in luma units (LSB-ish).
POLISH_G_MIN = (0.40, 0.55, 0.75)
POLISH_TAU = (0.004, 0.007, 0.010)
POLISH_P = 2.0
ATROUS_KERNEL = np.array([1.0, 4.0, 6.0, 4.0, 1.0], dtype=np.float32) / 16.0

# Final encode policy (C8 v3): Q97 preserves low-amplitude gradient variation
# and deliberate dither disproportionately better in large smooth skies.
FINAL_JPEG_QUALITY = 97
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

def _kernel_weights(frac, taps, support, kernel):
    x = frac[:, None] - taps[None, :]
    if kernel == "mitchell":
        b, c = 1.0 / 3.0, 1.0 / 3.0
        ax = np.abs(x)
        w = np.where(
            ax < 1,
            (12 - 9 * b - 6 * c) * ax ** 3 + (-18 + 12 * b + 6 * c) * ax ** 2 + (6 - 2 * b),
            np.where(
                ax < 2,
                (-b - 6 * c) * ax ** 3 + (6 * b + 30 * c) * ax ** 2 + (-12 * b - 48 * c) * ax + (8 * b + 24 * c),
                0.0,
            ),
        ) / 6.0
    else:
        w = np.sinc(x) * np.sinc(x / support)
    w /= w.sum(axis=1, keepdims=True)
    return w.astype(np.float32)


def _resample_axis(a, scale, support, highlight=None, kernel="lanczos"):
    """Resample along axis=1. a: (N, M) -> (N, round(M*scale)).

    Lanczos-a or Mitchell-Netravali kernel with a soft anti-ringing limiter;
    when `highlight` is provided it is a float mask in the OUTPUT domain used
to blend toward Lanczos2 at extreme highlights (C8 section 7)."""
    if abs(scale - 1.0) < 1e-6:
        return a
    n, m = a.shape
    out_m = max(1, int(round(m * scale)))
    j = np.arange(out_m, dtype=np.float64)
    src = (j + 0.5) / scale - 0.5
    i0 = np.floor(src).astype(np.int64)
    frac = src - i0
    taps = np.arange(-support + 1, support + 1, dtype=np.int64)
    if kernel == "mitchell":
        taps = np.arange(-1, 3, dtype=np.int64)
    idx = i0[:, None] + taps[None, :]
    idx = np.clip(idx, 0, m - 1)
    w = _kernel_weights(frac, taps, support, kernel)

    gathered = a[:, idx]  # (n, out_m, taps)
    out = np.einsum("nok,ok->no", gathered, w)

    if highlight is not None and support >= 3:
        # Hybrid: blend with Lanczos2 output inside the highlight mask.
        w2 = _kernel_weights(frac, taps, 2, "lanczos")
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


def _resample2d(a, scale, support, highlight=None, kernel="lanczos"):
    """Separable resample. `highlight` is a source-domain mask that is
    resized per axis so the hybrid applies in output space."""
    hl_x = None
    if highlight is not None:
        hl_x = _resize_linear_axis(highlight, scale)
    tmp = _resample_axis(a, scale, support, hl_x, kernel)
    tmp = tmp.T
    hl_y = None
    if highlight is not None:
        hl_y = _resize_linear_axis(hl_x.T, scale)
    out = _resample_axis(tmp, scale, support, hl_y, kernel)
    return out.T


def _upscale_channel(channel, scale, support, highlight=None, kernel="lanczos"):
    return _resample2d(channel, scale, support, highlight, kernel)


def _resize_mask(mask, scale):
    """Linear resize of a float mask to the output domain."""
    if abs(scale - 1.0) < 1e-6:
        return mask
    return _resize_linear_axis(_resize_linear_axis(mask, scale).T, scale).T


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


def _lag1(residual, mask):
    """Max absolute lag-1 autocorrelation of a detrended residual inside a
    soft mask. Coarse correlated grain (the v2 failure mode) reads 0.5+."""
    m = np.clip(mask, 0.0, 1.0)
    mh = m[:, :-1] * m[:, 1:]
    mv = m[:-1, :] * m[1:, :]
    num_h = float(np.sum(residual[:, :-1] * residual[:, 1:] * mh))
    den_h = float(np.sum((residual[:, :-1] ** 2) * mh))
    num_v = float(np.sum(residual[:-1, :] * residual[1:, :] * mv))
    den_v = float(np.sum((residual[:-1, :] ** 2) * mv))
    rho_h = num_h / max(den_h, 1e-12)
    rho_v = num_v / max(den_v, 1e-12)
    return max(abs(rho_h), abs(rho_v))


def _residual_rms(a, mask):
    """RMS of the detrended residual inside a soft mask (destination scale)."""
    r = a - _gauss(a, 0.8)
    m = np.clip(mask, 0.0, 1.0)
    if float(m.sum()) < 256.0:
        m = np.ones_like(m)
    return float(np.sqrt(np.sum((r * m) ** 2) / max(float(np.sum(m)), 1.0)))


# ---------------------------------------------------------------------------
# Main stage
# ---------------------------------------------------------------------------

def _finish_rgb(rgb, preset, scale, standalone, seed_extra, dither=True, return_float=False,
                gradient_alpha=1.0, overrides=None, material_clean=True,
                reference_rgb=None, polish_enabled=True, wall_dither_boost=0.0):
    """rgb: uint8 HxWx3. Returns (out, qc_report, passed); `out` is uint8
    unless return_float=True (pre-quantization float RGB, for experiments).
    dither=False leaves the gradient dither stage out (variant generation).
    gradient_alpha blends the smooth-gradient branch down (fail-soft ladder);
    overrides carries the user's clamped pro-tuning multipliers."""
    p = dict(PRESETS[preset])
    # Pro tuning overrides (clamped by normalize_quality_finish_settings):
    # dither/sharpen scale the preset amplitudes; smoothness scales the
    # sky/wall SUPPRESSION depth (1 = preset, <1 keeps more, >1 suppresses
    # harder).
    ov = overrides if isinstance(overrides, dict) else {}
    if isinstance(ov.get("dither"), (int, float)):
        p["dither_luma"] *= float(ov["dither"])
        p["dither_chroma"] *= float(ov["dither"])
    if isinstance(ov.get("sharpen"), (int, float)):
        p["sharpen_k"] *= float(ov["sharpen"])
    if isinstance(ov.get("smoothness"), (int, float)):
        sm = float(ov["smoothness"])
        for _k in ("h0_smooth", "h1_smooth"):
            p[_k] = min(1.0, max(0.05, 1.0 - (1.0 - p[_k]) * sm))
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

    # ---- Shared masks + four-band decomposition ----------------------------
    gm = _grad_mag(y)
    strong_edge = gm > 0.07
    edge_band = _dilate(strong_edge.astype(np.float32), 2)

    y_sm = _gauss(y, 1.2)

    # Four-band decomposition (C8 v2): B carries the illumination base, H2
    # the large-scale structure, H1 the mid band, H0 the fine band. B and H2
    # are preserved fully; H0/H1 get region-conditioned gains below.
    l2 = _gauss(y, 2.4)
    l1 = _gauss(y, 1.2)
    l0 = _gauss(y, 0.6)
    h2 = l1 - l2
    h1 = l0 - l1
    h0 = y - l0
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

    # Noise-aware structural smoothness S: no structure ABOVE the noise
    # floor. 8x headroom absorbs the q92 quantization grain (variance ~2x
    # the MAD-based floor) so grainy lit walls classify as smooth.
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

    # ---- Texture confidence T (C8 v2) --------------------------------------
    # Real material texture has cross-scale support: H1 energy backed by
    # H2/structural features. Noise has H0/H1 energy without H2 support.
    gx = np.zeros_like(y)
    gy = np.zeros_like(y)
    gx[:, 1:-1] = (y[:, 2:] - y[:, :-2]) * 0.5
    gy[1:-1, :] = (y[2:, :] - y[:-2, :]) * 0.5
    gxx = _box(gx * gx, 4)
    gyy = _box(gy * gy, 4)
    gxy = _box(gx * gy, 4)
    anisotropy = np.sqrt((gxx - gyy) ** 2 + 4 * gxy * gxy) / (gxx + gyy + 1e-9)
    e_h2 = np.sqrt(_box(h2 * h2, 4))
    e_h1 = np.sqrt(_box(h1 * h1, 4))
    cross = _box(np.abs(h1) * np.abs(h2), 4) / (e_h1 * e_h2 + 1e-9)
    e_h2_n = np.clip(e_h2 / (4.0 * sigma_n_img + 1e-9), 0.0, 1.0)
    tex = np.clip(0.4 * anisotropy + 0.35 * cross + 0.25 * e_h2_n, 0.0, 1.0)
    tex = _box(tex, 2)
    tex = np.clip(tex + 0.5 * edge_band, 0.0, 1.0)

    # Smooth-gradient mask: noise-aware smoothness minus real texture.
    # Used by the case-B guard, chroma decontouring, and the dither stage.
    grad_mask_native = np.clip(flat_float * (1.0 - 0.5 * tex), 0.0, 1.0)

    # ---- Region-conditioned H0/H1 suppression (BEFORE enlargement) ---------
    # C8 v2: the visible defect is the mid band enlarged into correlated
    # texture. Smooth regions get the preset's retention (sky/walls/cone
    # interiors); texture confidence raises retention toward 1.0; luminance
    # keeps a small SNR weight without being its own class.
    w_region = np.clip(0.3 * shadow + 0.7 * flat_float, 0.0, 1.0)
    a0 = p["h0_smooth"] + tex * (1.0 - p["h0_smooth"])
    a1 = p["h1_smooth"] + tex * (1.0 - p["h1_smooth"])
    g0 = 1.0 - gradient_alpha * w_region * (1.0 - a0)
    g1 = 1.0 - gradient_alpha * w_region * (1.0 - a1)
    h0 = h0 * g0
    h1 = h1 * g1
    y = l2 + h2 + h1 + h0

    # Case-B guard (C8 v3): only when the FLOAT buffer itself already
    # carries 1-LSB staircases (standalone JPEG inputs), reconstruct the
    # smooth surface with an edge-aware base. Case A (clean float, banded
    # 8-bit) is handled downstream by the dither stage.
    staircase_reconstructed = False
    if _staircase_index(y, grad_mask_native) > 2.0:
        recon = _guided_filter(y, y, 8, 1e-3)
        y = y + 0.6 * gradient_alpha * grad_mask_native * (recon - y)
        staircase_reconstructed = True

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
        ) ** 0.7
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
    y = y + 0.25 * gradient_alpha * banding_region * (_gauss(y, 0.8) - y)

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

    # Chroma gradient decontouring (C8 v3): stronger low-frequency chroma
    # smoothing in smooth-gradient regions only -- twilight skies band in
    # Cb/Cr, and luma dither cannot fix a chroma staircase.
    cb = cb + 0.6 * gradient_alpha * grad_mask_native * (_guided_filter(cb, y, 4, 2e-3) - cb)
    cr = cr + 0.6 * gradient_alpha * grad_mask_native * (_guided_filter(cr, y, 4, 2e-3) - cr)

    # ---- Mobile Clean material branch (C8 v5) ------------------------------
    # Rendered walls: preserve coherent structure + low-frequency colour,
    # aggressively shrink the UNSTRUCTURED residual (the old-phone grain),
    # and shrink chroma speckle hard. Auto-triggers on coverage + severity.
    material = _material_smooth_confidence(y, cb, cr, flat_float, tex, edge_band)
    p_struct = _cross_scale_persistence(y)
    material_native = material
    wall_applied = False
    wall_would_trigger = False
    wall_rms_before = 0.0
    wall_cnf_before = 0.0
    if float(np.mean(material > 0.5)) >= WALL_COVERAGE_MIN:
        wall_rms_before = _masked_rms(y - _gauss(y, 0.7), material)
        wall_cnf_before = _cnf(y, material)
        wall_would_trigger = (
            wall_rms_before > WALL_RMS_TRIGGER or wall_cnf_before > WALL_CNF_TRIGGER
        )
        if material_clean and wall_would_trigger:
            wall_applied = True
            base_y = _guided_filter(y, y, 8, 1e-3)
            base_cb = _guided_filter(cb, y, 12, 1e-3)
            base_cr = _guided_filter(cr, y, 12, 1e-3)
            resid = y - base_y
            resid_struct = p_struct * resid
            resid_noise = (1.0 - p_struct) * resid
            rms_n = _masked_rms(resid_noise, material)
            bright = (y > 0.5).astype(np.float32)
            # C8 v6 source-relative target: measure the ORIGINAL source's
            # residual in the SAME domain (one reference resize -> same
            # fine-residual decomposition -> same material ROI), then cap
            # the output at ~1.15-1.20x of that. Pristine sources stay
            # pristine; naturally noisy sources keep a little character.
            src_sigma = None
            if reference_rgb is not None:
                try:
                    ref = reference_rgb.astype(np.float32) / 255.0
                    if ref.shape[1] != y.shape[1] or ref.shape[0] != y.shape[0]:
                        ref = (
                            np.asarray(
                                Image.fromarray(reference_rgb, mode="RGB").resize(
                                    (y.shape[1], y.shape[0]), Image.Resampling.LANCZOS
                                )
                            ).astype(np.float32)
                            / 255.0
                        )
                    src_y = 0.299 * ref[..., 0] + 0.587 * ref[..., 1] + 0.114 * ref[..., 2]
                    src_sigma = _masked_rms(src_y - _gauss(src_y, 0.7), material)
                except Exception:
                    src_sigma = None
            if src_sigma is not None and src_sigma > 0:
                target = np.where(
                    bright,
                    np.clip(1.15 * src_sigma, 0.25 / 255.0, 0.40 / 255.0),
                    np.clip(1.20 * src_sigma, 0.35 / 255.0, 0.60 / 255.0),
                ).astype(np.float32)
            else:
                target = bright * WALL_RMS_BRIGHT + (1.0 - bright) * WALL_RMS_DARK
            target_field = _box(target, 8)
            gain = np.clip(target_field / max(rms_n, 1e-4), 0.0, 1.0)
            y = base_y + resid_struct + resid_noise * (material * gain + (1.0 - material))

            def _clean_material_chroma(ch, base_c):
                r = ch - base_c
                rn = (1.0 - p_struct) * r
                rms_c = _masked_rms(rn, material)
                gain_c = np.clip(WALL_CHROMA_RMS / max(rms_c, 1e-4), 0.0, 1.0)
                return base_c + p_struct * r + rn * (material * gain_c + (1.0 - material))

            cb = _clean_material_chroma(cb, base_cb)
            cr = _clean_material_chroma(cr, base_cr)

    # ---- Optional dual-kernel enlargement (C8 v2) --------------------------
    # Structure gets Lanczos3, smooth regions get Mitchell, feathered by the
    # texture-confidence map -- the interpolator itself must not convert
    # source noise into crisp correlated texture in sky/walls.
    tex_out = tex
    if scale > 1.0 + 1e-6:
        y3 = _upscale_channel(y, scale, 3, highlight=highlight_mask)
        ym = _upscale_channel(y, scale, 2, highlight=highlight_mask, kernel="mitchell")
        tex_out = _resize_mask(tex, scale)
        y = tex_out * y3 + (1.0 - tex_out) * ym
        cb = _upscale_channel(cb, scale, 2, highlight=None)
        cr = _upscale_channel(cr, scale, 2, highlight=None)
        flat_float = _resize_mask(flat_float, scale)
        edge_band = _resize_mask(edge_band, scale)
        highlight_edge = _resize_mask(highlight_edge, scale)
        sigma_n_img = _resize_mask(sigma_n_img, scale)
        material = _resize_mask(material, scale)
        p_struct = _resize_mask(p_struct, scale)

    # ---- Destination-scale residual decorrelation (C8 v2) ------------------
    # Interpolated noise is a spatially correlated field (rho1 ~0.5+) after
    # the 1.6x resample. Linearly suppressing the band CANNOT change its
    # autocorrelation (rho is scale-invariant), so subtract the lag-1
    # 4-neighbour prediction of the fine residual in smooth regions until
    # rho1 is back under the ceiling (max 3 passes, texture untouched).
    for _pass in range(int(p.get("decorr_max_passes", 6))):
        residual_dst = y - _gauss(y, 0.8)
        rho = _lag1(residual_dst, flat_float)
        if rho <= QC_RHO1_MAX:
            break
        pred = 0.25 * (
            np.roll(residual_dst, 1, axis=1)
            + np.roll(residual_dst, -1, axis=1)
            + np.roll(residual_dst, 1, axis=0)
            + np.roll(residual_dst, -1, axis=0)
        )
        y = y - float(p.get("decorr_gain", 0.7)) * gradient_alpha * flat_float * pred

    # ---- SNR-gated band-limited sharpen (C8 v2) -----------------------------
    # Sharpen structure, never noise: gain is gated by a local signal-to-
    # noise test on the sharpening band itself (k ~ 3), on top of the
    # structure/tex mask and the halo protection.
    f = scale
    s1 = 0.7 * f
    s2 = 1.4 * f
    band = _gauss(y, s1) - _gauss(y, s2)
    halo = _box(highlight_edge, 2)
    struct = np.clip(0.35 + 0.65 * tex_out - flat_float * 0.6 - halo * 0.85, 0.0, 1.0)
    if wall_applied:
        # C8 v5: sharpen coherent structure only, never the cleaned wall
        # residual; cap the gain on smooth material.
        struct = struct * np.clip(1.0 - 0.6 * material * (1.0 - p_struct), 0.0, 1.0)
    sigma_band = np.maximum(sigma_n_img, 1e-3) * 0.35
    snr_gate = np.clip(
        (np.abs(band) - p["snr_k"] * sigma_band) / (np.abs(band) + 1e-9), 0.0, 1.0
    )

    def _apply_sharpen(base_y, k_mult):
        k = p["sharpen_k"] * k_mult * struct * snr_gate * (1.0 - p["halo_k_scale"] * halo)
        sharp_y = base_y + k * band
        tol = 1.0 / 255.0
        lo = _erode(base_y, 2) - tol
        hi = _dilate(base_y, 2) + tol
        over = sharp_y - hi
        under = lo - sharp_y
        sharp_y = np.where(over > 0, hi + tol * (1.0 - np.exp(-over / tol)), sharp_y)
        sharp_y = np.where(under > 0, lo - tol * (1.0 - np.exp(-under / tol)), sharp_y)
        return sharp_y

    y_pre = y.copy()
    y = _apply_sharpen(y_pre, 1.0)

    # ---- QC pass (fail-soft: halve the sharpen gain once if ringing trips) -
    qc, passed = _run_qc(
        y_before, y, cb_before, cb, cr_before, cr,
        flat_float, edge_band, shadow, standalone, seed_extra, scale,
    )
    if not passed and qc.get("ringing") is not None and qc.get("ringing") > QC_RINGING_MAX:
        y = _apply_sharpen(y_pre, 0.5)
        qc, passed = _run_qc(
            y_before, y, cb_before, cb, cr_before, cr,
            flat_float, edge_band, shadow, standalone, seed_extra, scale,
            sharpen_retry=True,
        )

    # ---- V6 Final Polish (C8 v6) -------------------------------------------
    # À-trous coefficient shrinkage AFTER sharpening and BEFORE dither:
    # remove unsupported residual amplitude inside smooth-material regions
    # only. Structure, sky, brick and foliage are untouched by design.
    polish_report = {"applied": False}
    if polish_enabled and material_clean and float(np.mean(material > 0.1)) > 0.01:
        y, cb, cr, polish_report = _final_polish(y, cb, cr, material, p_struct)

    # ---- Always-on gradient-masked shaped dither (C8 v3) -------------------
    # Immediately before 8-bit quantization: sub-visible deterministic
    # shaped noise breaks 1-LSB staircase contours in smooth gradients.
    # Nothing image-altering follows except quantization and JPEG encoding.
    if dither:
        grad_mask_out = np.clip(flat_float * (1.0 - 0.5 * tex_out), 0.0, 1.0)
        # C8 v5: split wall and sky dither. Walls get a low baseline
        # (0.15 Y / 0.05 C LSB) so dither never reads as grain; the sky's
        # proven gradient dither is untouched.
        amp_y = (
            grad_mask_out * p["dither_luma"] * np.clip(1.0 - material, 0.0, 1.0)
            + material * (WALL_DITHER_Y + wall_dither_boost)
        )
        amp_c = (
            grad_mask_out * p["dither_chroma"] * np.clip(1.0 - material, 0.0, 1.0)
            + material * (WALL_DITHER_C + 0.3 * wall_dither_boost)
        )
        dith_y = _tiled_noise(y.shape, 64, f"qf-dither-y:{seed_extra}")
        dith_cb = _tiled_noise(cb.shape, 64, f"qf-dither-cb:{seed_extra}")
        dith_cr = _tiled_noise(cr.shape, 64, f"qf-dither-cr:{seed_extra}")
        y = y + gradient_alpha * amp_y * dith_y
        cb = cb + gradient_alpha * amp_c * dith_cb
        cr = cr + gradient_alpha * amp_c * dith_cr
        qc, passed = _run_qc(
            y_before, y, cb_before, cb, cr_before, cr,
            flat_float, edge_band, shadow, standalone, seed_extra, scale,
            dithered=True,
        )

    # ---- Banding-origin diagnostic (C8 v3 three-point test) ----------------
    # Classify where the staircase is born: float buffer, 8-bit rounding,
    # or the JPEG encoder. Recorded in the report for every job.
    grad_mask_diag = np.clip(flat_float * (1.0 - 0.5 * tex_out), 0.0, 1.0)
    frac_float = _small_step_fraction(y, grad_mask_diag)
    y8 = np.rint(y * 255.0) / 255.0
    frac_8bit = _small_step_fraction(y8, grad_mask_diag)
    out_rgb = np.clip(_ycbcr_to_rgb(y, cb, cr), 0.0, 1.0)
    out_u8 = np.rint(out_rgb * 255.0).clip(0, 255).astype(np.uint8)
    probe = io.BytesIO()
    Image.fromarray(out_u8, mode="RGB").save(
        probe, format="JPEG", quality=FINAL_JPEG_QUALITY, subsampling=FINAL_JPEG_SUBSAMPLING
    )
    probe.seek(0)
    dec = np.asarray(Image.open(probe).convert("RGB")).astype(np.float32) / 255.0
    y_jpg = 0.299 * dec[..., 0] + 0.587 * dec[..., 1] + 0.114 * dec[..., 2]
    frac_jpeg = _small_step_fraction(y_jpg, grad_mask_diag)
    staircase_index_jpeg = _staircase_index(y_jpg, grad_mask_diag)
    if staircase_reconstructed:
        banding_origin = "pre_existing_float"
    elif frac_8bit > frac_float * 1.5 + 0.005:
        banding_origin = "quantization"
    elif frac_jpeg > frac_8bit * 1.3 + 0.005:
        banding_origin = "jpeg"
    else:
        banding_origin = "none"
    qc["banding_origin"] = banding_origin
    qc["staircase_index_jpeg"] = round(staircase_index_jpeg, 3)
    qc["step_fraction_float"] = round(frac_float, 5)
    qc["step_fraction_8bit"] = round(frac_8bit, 5)
    qc["step_fraction_jpeg"] = round(frac_jpeg, 5)
    qc["staircase_reconstructed"] = staircase_reconstructed
    qc["gradient_alpha"] = round(gradient_alpha, 3)
    qc["final_polish"] = polish_report

    # ---- Material-branch QC (C8 v5) ----------------------------------------
    # Report the wall metrics that matter (RMS, CNF, correlation length,
    # rho1, H1/H0) so the old-phone grain is measurable per image.
    material_diag = material if material.shape == y.shape else material_native
    if material_diag.shape != y.shape:
        material_diag = _resize_mask(material_diag, y.shape[1] / float(material_diag.shape[1]))
    wall_res = y - _gauss(y, 0.7)
    qc["material_wall"] = {
        "coverage": round(float(np.mean(material_diag > 0.5)), 3),
        "applied": wall_applied,
        "enabled": material_clean,
        "would_trigger": wall_would_trigger,
        "reason": (
            "applied"
            if wall_applied
            else "disabled_by_user"
            if wall_would_trigger and not material_clean
            else "below_threshold_or_no_material"
        ),
        "rms_before": round(wall_rms_before * 255.0, 3),
        "cnf_before": round(wall_cnf_before, 3),
        "rms_after": round(_masked_rms(wall_res, material_diag) * 255.0, 3),
        "cnf_after": round(_cnf(y, material_diag), 3),
        "correlation_length_px": _correlation_length(wall_res, material_diag),
        "rho1": round(_lag1(wall_res, material_diag), 3),
        "h1h0": round(
            _masked_rms(_gauss(y, 0.7) - _gauss(y, 1.6), material_diag)
            / max(_masked_rms(wall_res, material_diag), 1e-9),
            3,
        ),
    }

    out = out_rgb if return_float else out_u8
    return out, qc, passed


def _tiled_noise(shape, size, seed_text):
    """Deterministic shaped-noise tile (C8 v3): white noise -> low-frequency
    suppression -> gentle Nyquist rolloff. Energy concentrated ~0.15-0.40
    cyc/px so JPEG does not erase it. Unit RMS."""
    digest = hashlib.sha256(seed_text.encode("utf-8")).digest()
    rng = np.random.default_rng(int.from_bytes(digest[:8], "big"))
    tile = rng.normal(0.0, 1.0, (size, size)).astype(np.float32)
    lp = _box(tile, max(1, size // 12))
    tile = tile - lp
    tile = _box(tile, 1)
    tile = tile / max(float(np.std(tile)), 1e-9)
    hh, ww = shape
    rep_h = (hh + size - 1) // size
    rep_w = (ww + size - 1) // size
    return np.tile(tile, (rep_h, rep_w))[:hh, :ww].astype(np.float32)


def _small_step_fraction(a, mask):
    """Fraction of horizontal deltas at NEAR-EXACT 1-LSB steps (a staircase
    signature). A continuous ramp gives ~0, an 8-bit staircase gives
    ~0.05+, sensor noise gives ~0.01-0.03. Used for the case-B guard and
    the banding-origin diagnostic."""
    dy = np.abs(a[:, 1:] - a[:, :-1])
    m = np.clip(mask[:, 1:] + mask[:, :-1], 0.0, 1.0) > 0.5
    if m.sum() < 256:
        return 0.0
    step = np.abs(dy - 1.0 / 255.0) < 1.0 / 1020.0
    return float(np.mean(step[m]))


def _staircase_index(a, mask):
    """Coherence-based staircase index: P(|dY| <= 1/510) / P(1/510 < |dY| < 4/255).
    A real quantization staircase reads 5-20; noisy/natural content reads <1."""
    dy = np.abs(a[:, 1:] - a[:, :-1])
    m = np.clip(mask[:, 1:] + mask[:, :-1], 0.0, 1.0) > 0.5
    if m.sum() < 256:
        return 0.0
    same = float(np.mean(dy[m] <= 1.0 / 510.0))
    small = float(np.mean((dy[m] > 1.0 / 510.0) & (dy[m] < 4.0 / 255.0)))
    return same / max(small, 1e-6)


def _jpeg_delivery_info(path):
    """Parse a JPEG's SOF marker: dimensions and component sampling factors.
    Delivery-chain self-check (C8 v3): the shipped file must stay 4:4:4 at
    the advertised size."""
    with open(path, "rb") as fh:
        data = fh.read()
    i = 2
    while i < len(data) - 12:
        if data[i] != 0xFF:
            i += 1
            continue
        marker = data[i + 1]
        if marker in (0xC0, 0xC1, 0xC2, 0xC3):
            height = int.from_bytes(data[i + 5:i + 7], "big")
            width = int.from_bytes(data[i + 7:i + 9], "big")
            ncomp = data[i + 9]
            samples = [data[i + 11 + c * 3] for c in range(min(ncomp, 3))]
            is_444 = ncomp >= 3 and all(s == 0x11 for s in samples)
            return {
                "width": width,
                "height": height,
                "sampling": "4:4:4" if is_444 else "subsampled",
                "sampling_bytes": [hex(s) for s in samples],
            }
        if marker in (0xD8, 0xD9, 0x01) or 0xD0 <= marker <= 0xD7:
            i += 2
            continue
        length = int.from_bytes(data[i + 2:i + 4], "big")
        i += 2 + length
    return None


def _cross_scale_persistence(y):
    """C8 v5 cross-scale persistence: coherent surface structure survives
    multiple Gaussian scales with aligned orientation; noise/speckle does
    not (its gradient orientation is random across scales). Returns
    P_structure in [0,1] (1 = keep as structure, 0 = noise)."""
    eps = 1e-6

    def grads(a):
        gx = np.zeros_like(a)
        gy = np.zeros_like(a)
        gx[:, 1:-1] = (a[:, 2:] - a[:, :-2]) * 0.5
        gy[1:-1, :] = (a[2:, :] - a[:-2, :]) * 0.5
        return gx, gy

    s1 = _gauss(y, 0.7)
    s2 = _gauss(y, 1.4)
    s3 = _gauss(y, 2.4)
    gx1, gy1 = grads(s1)
    gx2, gy2 = grads(s2)
    gx3, gy3 = grads(s3)
    m1 = np.sqrt(gx1 * gx1 + gy1 * gy1)
    m2 = np.sqrt(gx2 * gx2 + gy2 * gy2)
    m3 = np.sqrt(gx3 * gx3 + gy3 * gy3)
    p12 = np.minimum(m1, 1.6 * m2) / (np.maximum(m1, 1.6 * m2) + eps)
    p23 = np.minimum(m2, 1.2 * m3) / (np.maximum(m2, 1.2 * m3) + eps)
    c12 = np.clip((gx1 * gx2 + gy1 * gy2) / (m1 * m2 + eps), 0.0, 1.0)
    c23 = np.clip((gx2 * gx3 + gy2 * gy3) / (m2 * m3 + eps), 0.0, 1.0)
    return _box(np.clip(p12 * p23 * c12 * c23, 0.0, 1.0), 2)


def _atrous_filter(a, hole):
    """One undecimated à-trous scale: separable B3-spline [1,4,6,4,1]/16
    convolution with `hole` zeros between taps. No downsampling."""
    k = ATROUS_KERNEL
    b = k[2] * a
    b += k[1] * (np.roll(a, hole, axis=1) + np.roll(a, -hole, axis=1))
    b += k[0] * (np.roll(a, 2 * hole, axis=1) + np.roll(a, -2 * hole, axis=1))
    c = k[2] * b
    c += k[1] * (np.roll(b, hole, axis=0) + np.roll(b, -hole, axis=0))
    c += k[0] * (np.roll(b, 2 * hole, axis=0) + np.roll(b, -2 * hole, axis=0))
    return c


def _final_polish(y, cb, cr, material, p_struct):
    """C8 v6 Final Polish: shrink UNSUPPORTED wavelet coefficients inside
    smooth-material regions only. Coherent structure (persistence -> 1)
    stays; sky/brick/foliage are untouched (material -> 0). Soft shrinkage,
    never threshold deletion. Returns (y, cb, cr, report)."""
    coeffs_y = []
    coarse_y = y
    for s in range(3):
        nxt = _atrous_filter(coarse_y, 1 << s)
        coeffs_y.append(coarse_y - nxt)
        coarse_y = nxt
    coarse_cb = cb
    coarse_cr = cr
    coeffs_cb = []
    coeffs_cr = []
    for s in range(3):
        ncb = _atrous_filter(coarse_cb, 1 << s)
        coeffs_cb.append(coarse_cb - ncb)
        coarse_cb = ncb
        ncr = _atrous_filter(coarse_cr, 1 << s)
        coeffs_cr.append(coarse_cr - ncr)
        coarse_cr = ncr
    p_levels = (p_struct, _box(p_struct, 2), _box(p_struct, 4))
    w = np.clip(material, 0.0, 1.0)
    mean_gains = []
    rec_y = coarse_y
    rec_cb = coarse_cb
    rec_cr = coarse_cr
    for s in range(3):
        wj = coeffs_y[s]
        abs_w = np.abs(wj)
        g = POLISH_G_MIN[s] + (1.0 - POLISH_G_MIN[s]) * (
            abs_w ** POLISH_P / (abs_w ** POLISH_P + POLISH_TAU[s] ** POLISH_P)
        )
        g_eff = p_levels[s] + (1.0 - p_levels[s]) * g
        # Hard brick/structure guard: high persistence never shrinks hard.
        g_eff = np.where(p_levels[s] > 0.75, np.maximum(g_eff, 0.9), g_eff)
        # Spatial emphasis: shrink only inside the smooth-material regions.
        g_eff = 1.0 - w * (1.0 - g_eff)
        rec_y = rec_y + wj * g_eff
        rec_cb = rec_cb + coeffs_cb[s] * g_eff
        rec_cr = rec_cr + coeffs_cr[s] * g_eff
        sel = material > 0.5
        if float(sel.sum()) > 256:
            mean_gains.append(round(float(np.mean(g_eff[sel])), 3))
        else:
            mean_gains.append(1.0)
    return rec_y, rec_cb, rec_cr, {
        "applied": True,
        "coverage": round(float(np.mean(material > 0.5)), 3),
        "mean_gain_per_scale": mean_gains,
    }


def _material_smooth_confidence(y, cb, cr, flat_float, tex, edge_band):
    """C8 v5 smooth-material confidence: large architectural surfaces with
    coherent low-frequency illumination/chroma variation but almost no
    legitimate incoherent high/mid-frequency energy. Rendered walls = high;
    brick/foliage/masonry = low."""
    g_y = _grad_mag(y)
    g_c = _grad_mag(cb) + _grad_mag(cr)
    low_edge = (g_y < 0.02).astype(np.float32)
    # Structured-energy criterion: the H2 band DETRENDED of its own local
    # mean, so a wall's illumination ramp does not count as structure.
    h2_band = _gauss(y, 1.2) - _gauss(y, 2.4)
    h2_local = h2_band - _box(h2_band, 8)
    low_h2 = (_box(h2_local * h2_local, 4) < 0.004 ** 2).astype(np.float32)
    low_hf_chroma = (_box(g_c * g_c, 4) < 0.0004).astype(np.float32)
    # Hard gates + box smoothing: cores of large qualifying surfaces reach
    # ~1.0, edges feather out -- not a soft product capped below 0.5.
    # Texture is gated, not multiplied: real walls sit at tex ~0.2-0.3
    # (noise-only), brick/foliage at 0.5+.
    flat_ok = (flat_float > 0.35).astype(np.float32)
    tex_ok = (tex < 0.45).astype(np.float32)
    cand = (
        flat_ok
        * tex_ok
        * low_edge
        * low_h2
        * low_hf_chroma
        * np.clip(1.0 - edge_band, 0.0, 1.0)
    )
    cand = _box(cand, 6)
    # A wall carries a meaningful low-frequency illumination field; a blank
    # void does not. Soft weight so near-uniform walls keep partial
    # confidence instead of being excluded entirely.
    base = _gauss(y, 8)
    illum_var = _box((base - _box(base, 24)) ** 2, 8)
    illum_w = np.clip((illum_var - 1e-6) / 1e-5, 0.0, 1.0)
    return np.clip(_box(cand * illum_w, 4), 0.0, 1.0)


def _cnf(a, mask):
    """C8 v5 coarse-noise fraction: energy in the coarse residual band
    (~0.03-0.15 cyc/px) over the full residual band (~0.03-0.45 cyc/px).
    Same RMS can be premium (fine) or dirty (coarse); CNF separates them."""
    band_coarse = _gauss(a, 3.0) - _gauss(a, 7.0)
    band_all = a - _gauss(a, 7.0)
    e_c = _masked_rms(band_coarse, mask) ** 2
    e_a = _masked_rms(band_all, mask) ** 2
    return float(e_c / max(e_a, 1e-9))


def _correlation_length(a, mask):
    """C8 v5 correlation length: first lag (px) where the horizontal
    autocorrelation of the residual drops below 1/e. Premium walls collapse
    toward pixel scale; coarse old-phone grain persists 2-4px."""
    m = mask > 0.5
    if m.sum() < 4096:
        return 1
    x = a - float(np.mean(a[m]))
    var = float(np.mean(x[m] ** 2))
    if var < 1e-12:
        return 1
    for lag in range(1, 5):
        mm = m[:, lag:] & m[:, :-lag]
        if mm.sum() < 1024:
            continue
        r = float(np.mean((x[:, lag:] * x[:, :-lag])[mm])) / var
        if r < (1.0 / np.e):
            return lag
    return 4


def _masked_rms(a, mask):
    """RMS of a band inside a soft mask."""
    m = np.clip(mask, 0.0, 1.0)
    if float(m.sum()) < 256.0:
        m = np.ones_like(m)
    return float(np.sqrt(np.sum((a * m) ** 2) / max(float(np.sum(m)), 1.0)))


def _run_qc(
    y_before, y_after, cb_before, cb_after, cr_before, cr_after,
    flat_mask, edge_band, shadow, standalone, seed_extra, scale,
    dithered=False, sharpen_retry=False,
):
    """C8 v2 self-QC. Returns (report, passed).

    Destination-scale metrics first (residual autocorrelation, residual RMS,
    H1/H0 ratio) -- they catch the coarse correlated grain the v1 QC could
    not see. Pixel-fidelity metrics then run at NATIVE size (an upscaled
    candidate is brought back down first)."""
    # Destination-scale noise metrics on the DELIVERED resolution.
    l0_d = _gauss(y_after, 0.8)
    l1_d = _gauss(y_after, 1.6)
    h0_d = y_after - l0_d
    h1_d = l0_d - l1_d
    rho1 = _lag1(h0_d, flat_mask)
    residual_rms = _masked_rms(h0_d, flat_mask)
    h1h0_ratio = _masked_rms(h1_d, flat_mask) / max(_masked_rms(h0_d, flat_mask), 1e-9)

    # Per-ROI gradient QC (C8 v4): a 3x3 tile grid over the destination-scale
    # flat mask so reports show WHERE the sky measures clean or rough, not
    # just the global average. Report-only; the global gate is unchanged.
    roi_list = []
    try:
        if float(np.mean(flat_mask > 0.5)) >= 0.01:
            hm, wm = flat_mask.shape
            for ty in range(3):
                for tx in range(3):
                    y0, y1 = ty * hm // 3, (ty + 1) * hm // 3
                    x0, x1 = tx * wm // 3, (tx + 1) * wm // 3
                    tile = (flat_mask[y0:y1, x0:x1] > 0.5).astype(np.float32)
                    if float(tile.sum()) < 256:
                        continue
                    h0_t = h0_d[y0:y1, x0:x1]
                    yq_t = np.rint(y_after[y0:y1, x0:x1] * 255.0) / 255.0
                    dy_t = np.abs(yq_t[:, 1:] - yq_t[:, :-1])
                    tband = np.clip(tile[:, 1:] + tile[:, :-1], 0, 1) > 0.5
                    s_t = 0.0
                    if float(tband.sum()) > 256:
                        s_t = float(
                            np.mean(dy_t[tband] <= 1.0 / 510.0)
                            / max(
                                float(np.mean((dy_t[tband] > 1.0 / 510.0) & (dy_t[tband] < 4.0 / 255.0))),
                                1e-6,
                            )
                        )
                    roi_list.append(
                        {
                            "tile": f"{tx},{ty}",
                            "coverage": round(float(np.mean(tile)), 3),
                            "rho1": round(_lag1(h0_t, tile), 3),
                            "residual_rms": round(_masked_rms(h0_t, tile) * 255.0, 3),
                            "banding": round(s_t, 3),
                        }
                    )
        roi_list.sort(key=lambda r: -r["coverage"])
        roi_list = roi_list[:6]
    except Exception:
        roi_list = []

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

    # Flatness increase: RELATIVE variance collapse in flat regions. v2
    # deliberately suppresses smooth regions hard, so only NEAR-TOTAL
    # collapse (0.08x) is suspicious (waxy plastic surfaces).
    var_hf_before = _box(hf_before * hf_before, 4)
    var_hf_after = _box(hf_after * hf_after, 4)
    flat_bool = flat_mask > 0.5
    if flat_bool.sum() > 256:
        collapse = (var_hf_after < 0.08 * np.maximum(var_hf_before, 1e-12)) & flat_bool
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

    # Banding staircase index in flat regions, measured on the QUANTIZED
    # (8-bit) result -- staircases form at rounding, not in float.
    yq_before = np.rint(y_before * 255.0) / 255.0
    yq_after = np.rint(y_after * 255.0) / 255.0
    dy_b = np.abs(yq_before[:, 1:] - yq_before[:, :-1])
    dy_a = np.abs(yq_after[:, 1:] - yq_after[:, :-1])
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

    # v3 gate: SSIM hard rail + destination-scale noise quality (fine,
    # weakly-correlated residual above the anti-plastic floor) + no ringing /
    # blocking / chroma regressions. banding_worse is REPORTED but no longer
    # gated: v3's always-on shaped dither proactively prevents quantization
    # staircases, and comparing a deliberately smoothed sky against a noisy
    # input trips the old reactive metric by design.
    passed = (
        ssim >= QC_SSIM_FLOOR
        and rho1 <= QC_RHO1_MAX
        and residual_rms >= QC_RESIDUAL_RMS_MIN
        and flatness_delta <= QC_FLATNESS_DELTA
        and ringing <= QC_RINGING_MAX
        and b8_ok
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
        "sharpen_retry": sharpen_retry,
        "rho1": round(rho1, 4),
        "residual_rms": round(residual_rms * 255.0, 3),
        "h1h0_ratio": round(h1h0_ratio, 3),
        "gradient_rois": roi_list,
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


def _reference_metrics(out_u8, reference):
    """Fidelity metrics against the ORIGINAL source (C8 v4). The source is
    resampled ONCE to the delivery lattice with Lanczos3, then compared to
    the finished output: two-scale SSIM, texture-detail transfer ratio
    (detail band ~0.08-0.35 cyc/px — the "360p" detector), and an edge
    acutance ratio (a first-order edge-width proxy). Never raises."""
    try:
        if isinstance(reference, (str, Path)):
            ref_u8 = np.asarray(Image.open(reference).convert("RGB")).astype(np.uint8)
        else:
            arr = np.asarray(reference)
            if arr.ndim == 3 and arr.shape[2] >= 3:
                ref_u8 = arr[..., :3].astype(np.uint8)
            else:
                ref_u8 = np.stack([arr.astype(np.uint8)] * 3, axis=-1)
        ref = ref_u8.astype(np.float32) / 255.0
        out = out_u8.astype(np.float32) / 255.0
        oh, ow = out_u8.shape[:2]
        if ref.shape[1] != ow or ref.shape[0] != oh:
            ref_resized = Image.fromarray(ref_u8, mode="RGB").resize(
                (ow, oh), Image.Resampling.LANCZOS
            )
            ref = np.asarray(ref_resized).astype(np.float32) / 255.0
        y_out = 0.299 * out[..., 0] + 0.587 * out[..., 1] + 0.114 * out[..., 2]
        y_ref = 0.299 * ref[..., 0] + 0.587 * ref[..., 1] + 0.114 * ref[..., 2]
        ms_ssim = 0.5 * _ssim_proxy(y_ref, y_out, 1.0)
        half_out = _resample2d(y_out, 0.5, 2)
        half_ref = _resample2d(y_ref, 0.5, 2)
        ms_ssim += 0.5 * _ssim_proxy(half_ref, half_out, 1.0)
        d_out = _gauss(y_out, 1.0) - _gauss(y_out, 3.0)
        d_ref = _gauss(y_ref, 1.0) - _gauss(y_ref, 3.0)
        e_out = float(np.mean(d_out * d_out))
        e_ref = float(np.mean(d_ref * d_ref))
        tdr = min(2.0, e_out / max(e_ref, 1e-9))
        g_out = _grad_mag(y_out)
        g_ref = _grad_mag(y_ref)
        edge = _dilate((g_ref > 0.04).astype(np.float32), 2)
        if float(edge.sum()) > 512:
            ar = float(
                np.mean(g_out[edge > 0.5]) / max(float(np.mean(g_ref[edge > 0.5])), 1e-9)
            )
        else:
            ar = 1.0
        width_ratio = min(2.0, 1.0 / max(ar, 0.05))
        return {
            "ms_ssim": round(ms_ssim, 4),
            "texture_detail_transfer": round(tdr, 3),
            "edge_acutance_ratio": round(ar, 3),
            "edge_width_ratio_est": round(width_ratio, 3),
        }
    except Exception:
        return None


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
    # User overrides (Slash UI "Pro tuning"): multipliers over the preset's
    # own calibrated gains, clamped so no combination leaves the envelope.
    ov_raw = sub.get("overrides") if isinstance(sub, dict) else None
    overrides = {
        "dither": _clamp_override(ov_raw, "dither", 0.0, 1.5, 1.0),
        "smoothness": _clamp_override(ov_raw, "smoothness", 0.5, 1.5, 1.0),
        "sharpen": _clamp_override(ov_raw, "sharpen", 0.0, 1.5, 1.0),
    }
    # Wall smoothing (Mobile Clean) toggle: default ON; OFF keeps the
    # branch fully inert while still MEASURING it (A/B test mode).
    material_clean = bool(sub.get("material_clean", True)) if isinstance(sub, dict) else True
    return {
        "mode": MODE,
        "quality_finish": {
            "preset": preset,
            "scale": scale,
            "finish_mode": finish_mode,
            "overrides": overrides,
            "material_clean": material_clean,
        },
    }


def _clamp_override(ov, key, lo, hi, default):
    """Clamp a user override to the calibrated envelope (NaN/type-safe)."""
    try:
        v = float(ov.get(key)) if isinstance(ov, dict) else None
    except (TypeError, ValueError):
        v = None
    if v is None or v != v:
        return default
    return min(hi, max(lo, v))


def is_quality_finish(settings):
    return isinstance(settings, dict) and settings.get("mode") == MODE


def apply_quality_finish(
    input_path=None,
    output_path=None,
    image=None,
    settings=None,
    seed_extra="",
    creator_id="",
    reference=None,
):
    """Run the finisher. Writes the final single JPEG (Q97 4:4:4) to
    `output_path`. On QC failure the ORIGINAL bytes are shipped unchanged and
    `applied` is False (quality never costs acceptance) -- except gradient-
    axis failures, which first retry with the gradient branch blended down
    (fail-soft alpha ladder, alpha 0.75 -> 0.5 -> 0.25 -> 0)."""
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

    rgb = (
        np.asarray(src).astype(np.uint8)
        if isinstance(src, np.ndarray)
        else np.asarray(src.convert("RGB")).astype(np.uint8)
    )
    overrides = sub.get("overrides") if isinstance(sub.get("overrides"), dict) else None
    material_clean = bool(sub.get("material_clean", True))
    # The original source (when available) drives the V6 source-relative
    # cleanup targets and the structure guard retries.
    reference_rgb = None
    if reference is not None:
        try:
            if isinstance(reference, (str, Path)):
                reference_rgb = np.asarray(Image.open(reference).convert("RGB")).astype(np.uint8)
            else:
                arr = np.asarray(reference)
                if arr.ndim == 3 and arr.shape[2] >= 3:
                    reference_rgb = arr[..., :3].astype(np.uint8)
        except Exception:
            reference_rgb = None
    out_u8, qc, passed = _finish_rgb(
        rgb, preset, scale, standalone, seed_extra, overrides=overrides,
        material_clean=material_clean, reference_rgb=reference_rgb,
    )
    ladder_attempts = 1
    # Fail-soft alpha ladder (C8 v4): when QC fails on a GRADIENT-axis
    # metric (rho1 / flatness collapse / banding), retry with the gradient
    # branch blended down: alpha = 0.75 -> 0.5 -> 0.25 -> 0. Texture-region
    # processing stays at full strength; only the smooth-gradient treatment
    # backs off. Non-gradient failures (SSIM, ringing, chroma, block grid)
    # fall through to the original-bytes path unchanged.
    gradient_axis = (
        float(qc.get("rho1", 0.0)) > QC_RHO1_MAX
        or float(qc.get("flatness_delta", 0.0)) > QC_FLATNESS_DELTA
        or bool(qc.get("banding_worse"))
    )
    alpha = 1.0
    while not passed and gradient_axis and alpha > 0.05:
        alpha = round(alpha - 0.25, 2)
        ladder_attempts += 1
        out_u8, qc, passed = _finish_rgb(
            rgb,
            preset,
            scale,
            standalone,
            seed_extra,
            gradient_alpha=alpha,
            overrides=overrides,
            material_clean=material_clean,
            reference_rgb=reference_rgb,
        )
        gradient_axis = (
            float(qc.get("rho1", 0.0)) > QC_RHO1_MAX
            or float(qc.get("flatness_delta", 0.0)) > QC_FLATNESS_DELTA
            or bool(qc.get("banding_worse"))
        )
    qc["gradient_ladder_attempts"] = ladder_attempts

    # V6 structure guard: if Final Polish ran but the original-reference
    # texture transfer dropped below 0.95, retry once with polish disabled.
    # Structure always wins over polish.
    if (
        passed
        and reference_rgb is not None
        and bool(qc.get("final_polish", {}).get("applied"))
        and float(qc.get("reference", {}).get("texture_detail_transfer", 1.0)) < 0.95
    ):
        out_u8, qc, passed = _finish_rgb(
            rgb,
            preset,
            scale,
            standalone,
            seed_extra,
            overrides=overrides,
            material_clean=material_clean,
            reference_rgb=reference_rgb,
            polish_enabled=False,
        )
        qc["final_polish"]["retried_disabled"] = True

    # V6 dither escalation: raise wall dither only when the DECODED JPEG
    # staircase proves the low baseline insufficient (never pre-emptively).
    if (
        passed
        and bool(qc.get("material_wall", {}).get("applied"))
        and float(qc.get("staircase_index_jpeg", 0.0)) > 0.7
    ):
        out_u8, qc, passed = _finish_rgb(
            rgb,
            preset,
            scale,
            standalone,
            seed_extra,
            overrides=overrides,
            material_clean=material_clean,
            reference_rgb=reference_rgb,
            wall_dither_boost=0.05 / 255.0,
        )
        qc["material_wall"]["dither_boosted"] = True

    # Fidelity reference (C8 v4): when the ORIGINAL source is available,
    # measure the output against it (not against the stage-1 intermediate).
    # texture_detail_transfer < 0.75 warns; < 0.60 rejects the finish and
    # ships the input bytes (the stage-1 buffer in chained mode).
    if reference is not None:
        ref_metrics = _reference_metrics(out_u8, reference)
        if ref_metrics is not None:
            qc["reference"] = ref_metrics
            tdr = ref_metrics["texture_detail_transfer"]
            if tdr < REF_TDR_WARN:
                qc["reference_warn"] = "texture_detail_transfer_below_0.75"
            if tdr < REF_TDR_FLOOR:
                passed = False
                qc["reference_fail"] = "texture_detail_transfer_below_0.60"

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

    # Delivery-chain self-check (C8 v3): parse the shipped JPEG's own SOF
    # marker so size + sampling factors are proven, not assumed.
    delivery_check = _jpeg_delivery_info(output_path)

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
        "delivery_check": delivery_check,
        "overrides": {k: round(float(v), 3) for k, v in sub.get("overrides", {}).items()}
        if isinstance(sub.get("overrides"), dict)
        else {},
        "encode": {
            "quality": FINAL_JPEG_QUALITY,
            "subsampling": "4:4:4",
            "single_encode": True,
        },
    }
