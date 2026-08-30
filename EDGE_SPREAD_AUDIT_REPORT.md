# EDGE-SPREAD SUBSTAGE AUDIT — 4D-CAM-1 CHECKPOINTS

Date: 2026-08-27 · Master engineer · zero vendor grades · buffers: the 34
hash-verified checkpoint dirs already retrieved.

## Question (from C88, pre-registered)

Is the edge-widening seen under `optics_psf_scale` 0.50
(a) true broadening of the edge transition (PSF/resample), or
(b) ringing (overshoot moving 10%/90% crossings) from the scene-modulated sharpen?

## Method

1. **Matched-edge ESF profiles** (`tools/edge_spread_audit.py`): per image, up to
   320 isolated strong edges (p92 gradient), subpixel-aligned by parabolic peak fit,
   normalized to the local step. Per profile: raw 10–90 width, monotonic (PAVA
   isotonic) 10–90 width, overshoot/undershoot (fraction of step), out-of-transition
   excess energy, crossing-candidate count. Stratified by orientation and contrast.
2. **Stage pinning** (`tools/edge_stage_pin.py`): the frozen `edge_width_10_90`
   metric (combined positional bands) recomputed per stage (OR → O2 → O5, plus the
   source-resampled reference R5) on the worst/best pairs, alongside ESF on O5/R5.

## Findings

### A. Camera stage (OR→O2): C ≈ B globally — no broadening

Global medians over ~3,300 matched edges per arm (O2):

| arm | raw 10–90 | mono 10–90 | overshoot | crossings |
|---|---:|---:|---:|---:|
| B (scale 1.00) | 31.11 px | 20.95 px | 0.065 | 6.0 |
| C (scale 0.50) | 31.28 px | 20.97 px | 0.070 | 7.0 |

Halving the PSF radii does **not** widen matched edges at O2: +0.02 px mono width,
+0.005 overshoot, +1 crossing candidate. Also notable: both arms already carry
substantial overshoot at O2 (crossings ≈ 6–7 of the 0.1/0.9 levels) — the incumbent
camera itself rings mildly.

### B. The gate-6 widening is born in the FINISHER stage (O2→O5)

Frozen `edge_width_10_90` (combined bands), per stage:

| case | arm | OR | O2 | O5 | R5 (source) |
|---|---:|---:|---:|---:|---:|
| IMG-8 ctla1 | B | 7.3 | 1.2 | 8.5 | 1.2 |
| IMG-8 ctla1 | C | 7.3 | 2.2 | **23.8** | 1.2 |
| IMG-5 ctla1 | B | 8.5 | 1.4 | 4.3 | 3.9 |
| IMG-5 ctla1 | C | 8.5 | 1.4 | **8.5** | 3.9 |
| IMG-6 ctla1 | B | 6.5 | 22.1 | 6.9 | 7.3 |
| IMG-6 ctla1 | C | 6.5 | 22.1 | 10.1 | 7.3 |
| IMG-7 ctla1 | B | 3.7 | 11.7 | 11.0 | 2.9 |
| IMG-7 ctla1 | C | 3.7 | 3.2 | **12.9** | 2.9 |
| IMG-8 ctla2 | B | 0.4 | 3.4 | 11.8 | 1.2 |
| IMG-8 ctla2 | C | 0.4 | 1.9 | 7.9 | 1.2 |

At O2 the arms are close or C narrower. The large divergences appear at **O2→O5** —
tone-lock histogram match + Quality Finish (strong, S1.25) + sharpen + final encode.
The finisher is adaptive and amplifies small O2 differences nonlinearly.

### C. The frozen edge metric is blur-sensitive (important caveat)

`edge_width_10_90` counts contiguous run-lengths of gradient above the p90 threshold.
Blur lowers gradient magnitude → fewer pixels above threshold → **shorter runs**.
That is why OR (sharp, pre-camera) reads 7.3–8.5 while the camera-blurred O2 reads
1.2–2.2. The metric does not measure geometric edge spread in the blur direction;
it measures "how many strong-gradient pixels survive". C88's instinct that the gate-6
metric needed scrutiny was right, though the mechanism is threshold sensitivity, not
small-denominator inflation.

### D. Matched-edge ESF on delivered O5 — mild real effect only

ESF profiles on O5 (delivered), B vs C:

| case | Δ mono width (C−B) | Δ overshoot (C−B) |
|---|---:|---:|
| IMG-8 ctla1 | +1.38 px | +0.003 |
| IMG-5 ctla1 | +0.94 px | +0.027 |
| IMG-6 ctla1 | +0.11 px | −0.001 |
| IMG-7 ctla1 | −0.83 px | +0.001 |
| IMG-8 ctla2 | +0.84 px | +0.004 |

A small genuine widening + overshoot exists on the worst pairs (IMG-8 ctla1
+1.4 px mono, IMG-5 ctla1 +0.027 overshoot) — a mild ringing/over-sharpen component
is real. But it is ~10× smaller than the gate-6 relative figures suggested.

## Verdict

**Neither pure hypothesis.** The camera-stage PSF change does not broaden matched
edges. The gate-6 "widening" is dominated by (1) the finisher's adaptive sharpen
amplifying small O2 differences nonlinearly, measured through (2) a blur-sensitive
threshold metric that can read over-sharpening as widening. A small real
ringing/over-sharpen component exists on the worst pairs.

## Implications adopted into the 4D-1a brief

1. Edge gates are re-specified in **absolute matched-edge ESF terms** (mono width px,
   overshoot, second-peak check) at BOTH O2 and O5 — `edge_width_10_90` is retained
   as context only, never as a pass/fail gate.
2. The **finisher's adaptive reaction to changed O2 input is a controlled risk**:
   4D-1a must measure finisher behavior explicitly (O2 vs O5 deltas per pair).
3. C88's ringing checks (out-of-transition energy, no second signed peak above 10%
   of main response) are retained as pre-registered gates.
4. Camera radii stay untouched; nothing in this audit authorizes further PSF changes.

## Artifacts

- `deepclean-worker/tools/edge_spread_audit.py`
- `deepclean-worker/tools/edge_stage_pin.py`
- `round-4d-cam-1/edge-spread-audit.json`
- `round-4d-cam-1/edge-stage-pin.json`
