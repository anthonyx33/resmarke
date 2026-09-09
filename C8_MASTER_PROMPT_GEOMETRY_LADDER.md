# C8 MASTER PROMPT — GEOMETRY LADDER v4.4 (conservative shift-aware margin, 2026-09-09)

Role: C88 builder-architect. Build the frozen geometry-ladder module and the
eight preset definitions below. No detector changes, no wash/camera changes.

## 0. Why this exists (measured)

S1-slim proved the incumbent plain LANCZOS resample is detection-neutral
(median gain 5e-7) on six cells. It did NOT test transform-based
resampling. Owner hypothesis (REGISTERED, not accepted): resize combined
with tilt / micro-warp disrupts detector pixel-scale features. This
commission tests that hypothesis. Note: many detectors resize internally
and tolerate small transforms — gains may be modest; the ladder measures
exactly how much.

## 1. Geometry block (frozen schema, 4 fields)

```
geometry: {
  resampleMode: "bypass" | "affine",
  resizeTarget: 1250 | 1000 | 800,
  tiltDegrees:  0.0 | 0.6 | 1.2,
  microWarp:    "none" | "shift" | "shift_squash",
}
```

`resampleMode` is the discriminator that separates the alias control from
the identity-pass control. Absent `geometry` block = legacy behaviour;
Config A's settings code must remain `SEQ-CFA-*`.

Output dimensions are ALWAYS the legacy aspect-preserving dims whose long
edge is `min(source_long_edge, resizeTarget)` — never upscaled, never
changed by geometry. If a request carries both legacy `output_target` and
`geometry.resizeTarget` with different values, REJECT the request.

## 2. Eight ladder presets (frozen; eight unique tuples)

| Preset | Role | resampleMode | R | T | W |
|---|---|---|---|---|---|
| geom-r0 | alias control — module NOT invoked; output byte-identical to Config A | bypass | 1250 | 0.0 | none |
| geom-x0 | identity-pass control — module invoked with identity matrix | affine | 1250 | 0.0 | none |
| geom-r1 | resize L2 | affine | 1000 | 0.0 | none |
| geom-r2 | resize L3 | affine | 800 | 0.0 | none |
| geom-r3 | tilt L2 | affine | 1250 | 0.6 | none |
| geom-r4 | tilt L3 | affine | 1250 | 1.2 | none |
| geom-r5 | warp L2 | affine | 1250 | 0.0 | shift |
| geom-r6 | warp L3 | affine | 1250 | 0.0 | shift_squash |

## 3. Frozen transform contract (numeric)

Backend pinned: **`opencv-python-headless==4.10.0.84`** (add to
`deepclean-worker/requirements.txt`). Geometry = exactly ONE
`cv2.warpAffine` call per arm, `INTER_LANCZOS4`, `WARP_INVERSE_MAP`,
8-bit RGB in/out. The initial legacy resize uses the existing Pillow
LANCZOS path unchanged and runs BEFORE the module. Stage order frozen:
wash → legacy resize → geometry module → camera → finish.

All matrices below are the INVERSE maps (destination→source) passed to
warpAffine with `WARP_INVERSE_MAP`. Coordinates: OpenCV pixel-centre
convention; `c = ((w−1)/2, (h−1)/2)`.

1. **geom-x0 (identity):** `M_inv = [[1,0,0],[0,1,0]]`, border
   `BORDER_REPLICATE`, output (w,h).
2. **geom-r5 (shift):** `M_inv = [[1,0,0.5],[0,1,0.3]]`,
   `BORDER_REPLICATE`, output (w,h). (Destination (x,y) samples source
   (x+0.5, y+0.3).)
3. **geom-r6 (squash + shift, ONE composed call):** squash about the
   centre (x-scale `a = 0.988`) applied FIRST, then the same +0.5/+0.3
   sampling offset as r5 applied in SOURCE space (the shift is NOT
   scaled):
   `M_inv = [[1/a, 0, cx − cx/a + 0.5], [0, 1, 0.3]]`,
   border `BORDER_REPLICATE`, output (w,h). Expanded per-coordinate:
   `x_src = cx + (x_dst − cx)/a + 0.5`, `y_src = y_dst + 0.3`.
4. **geom-r3 / geom-r4 (tilt, ONE composed call):** with
   `R = [[cosθ, sinθ], [−sinθ, cosθ]]` — positive θ rotates the image
   counter-clockwise AS DISPLAYED (y-axis down) — kernel support
   `L = 4` (Lanczos4). **Overscan scale (exact L-px source-space margin;
   margin in the SOURCE denominator):**
   ```
   sx = ((w−1)·cosθ + (h−1)·sinθ) / (w−1−2L)
   sy = ((w−1)·sinθ + (h−1)·cosθ) / (h−1−2L)
   s  = max(sx, sy)
   s  = max(s, 1.0)          # θ = 0 degenerates to identity
   s  = s × (1 + 1e-4)       # frozen floating-point safety margin
   ```
   If `(w−1−2L) ≤ 0` or `(h−1−2L) ≤ 0` (tiny images): REJECT the request
   (validation error; cell skipped and recorded). With `s` frozen above,
   every destination pixel's Lanczos support lies strictly inside the
   source — zero border contribution, verified by the analytic mask gate.
   `M_inv = Rᵀ·(p_dst − c)/s + c`, border `BORDER_CONSTANT` (0,0,0),
   output (w,h).
   **Explicit branch:** the overscan formula applies ONLY when
   `tiltDegrees > 0`. For θ = 0 the tilt step is skipped entirely and
   `s = 1.0` is used — no degenerate limit of the margin formula is
   invoked.
   Expanded 2×3 coefficients (with `Rᵀ = [[cosθ, −sinθ], [sinθ, cosθ]]`):
   ```
   a11 = cosθ/s        a12 = −sinθ/s
   a21 = sinθ/s        a22 =  cosθ/s
   tx  = cx·(1 − cosθ/s) + cy·sinθ/s
   ty  = cy·(1 − cosθ/s) − cx·sinθ/s
   M_inv = [[a11, a12, tx], [a21, a22, ty]]
   ```
   Unit tests pin these matrices numerically for SQUARE (1250×1250),
   LANDSCAPE (1250×703), and PORTRAIT (703×1250) at θ∈{0.6,1.2}, assert
   the analytic coverage gate, and assert the computed minimum
   source-coordinate margin ≥ L for each fixture.
5. **General construction rule for EVERY permitted tuple, including
   J1–J3 (frozen NOW, before any Phase A result):**
   - Forward linear part (applied to content in this order): rotation
     first, then anisotropic squash: `A = S·R`, with
     `S = diag(a, 1)` (a = 0.988 iff microWarp = shift_squash, else 1)
     and `R` as frozen above (identity iff θ = 0).
   - Shift translation `t = (0.5, 0.3)` iff microWarp ∈ {shift,
     shift_squash}, else (0, 0), applied LAST in the forward mapping
     (`forward = T(−t)·A`), so the executed inverse map is
     `p_src = A⁻¹·(p_dst − c)/s + c + t`.
   - **Border/scale regime by tilt presence:** if `tiltDegrees > 0` →
     `BORDER_CONSTANT` (0,0,0) and the overscan scale guarantees zero
     border contribution; if `tiltDegrees = 0` → `s = 1`,
     `BORDER_REPLICATE`, replicated strips gated per §7.
   - **General margin formula (tilt regime, ANY permitted tuple
     including J1–J3; v4.4 conservative shift-aware construction —
     SUPERSEDES the v4.3 per-corner formula):**
     ```
     B = Rᵀ · diag(1/a, 1)              # float64; a = 0.988 iff squash else 1
     t = (0.5, 0.3) iff shift else (0, 0)
     half = ((w−1)/2, (h−1)/2)
     den_x = half.x − L − |t.x|
     den_y = half.y − L − |t.y|
     for each of the four corners p_k ∈ {(±half.x, ±half.y)}:
         v_k = B · p_k
     s = max(1.0, max_k |v_k.x|/den_x, max_k |v_k.y|/den_y) × (1 + 1e-4)
     ```
     Reject if `den_x ≤ 0` or `den_y ≤ 0`. WHY v4.4: the source-space
     shift `t` is NOT divided by `s` in the executed inverse
     `p_src = B·(p_dst − c)/s + c + t`; the v4.3 form
     `s ≥ |B·p_k + t| / (half − L)` treated `t` as if it were scaled by
     1/s, so it UNDER-SCALES when t ≠ 0. Measured on the permitted
     800/1000 resize caps (portrait joints), the v4.3 form yields
     source margins 3.9891 / 3.9945 / 3.9966 / 3.9974 px — below L —
     while the v4.4 form holds margin ≥ 4.022 px on all 36 joint
     fixtures. (The v4.2 analytic formula yielded 3.883–3.958 px on
     landscape fixtures — also superseded.) The v4.4 form is
     conservative (|v_k| + |t| triangle bound), sufficient for the
     zero-border guarantee.
     For a=1 and t=(0,0), `den = half − L` and `v_k = B·p_k`, which
     reduces EXACTLY to the single-feature tilt formula the Phase A
     build implements — **the eight Phase-A arms are numerically
     unchanged** (their pinned matrices reproduce within 1e-12
     tolerance; that is numerical equivalence, not byte equality); for
     θ=0 the replicate regime (s=1) is used and this formula is not
     invoked. Phase B matrix fixtures must assert margin ≥ L for the
     tilt joints on ALL THREE resize caps — square
     (1250×1250, 1000×1000, 800×800), landscape
     (1250×703, 1000×562, 800×450), and portrait
     (703×1250, 562×1000, 450×800) — at θ ∈ {0.6, 1.2} ×
     {shift, shift_squash} = 36 fixtures, plus a clean 255 diagnostic
     mask per fixture.
   - ONE `cv2.warpAffine` call per arm in all cases, `INTER_LANCZOS4`,
     `WARP_INVERSE_MAP`, matrix inverted with `cv2.invertAffineTransform`
     on float64. The Phase B addendum may only select tuples and codes —
     never invent pixel semantics.

Determinism: no RNG anywhere. Byte-determinism is claimed only for the
same build on the same machine / pinned container runtime; cross-machine
byte equality is not claimed.

## 4. Settings identity and boundary validation (frozen)

- Canonical camelCase: `resampleMode, resizeTarget, tiltDegrees,
  microWarp`; wire format snake_case: `resample_mode, resize_target,
  tilt_degrees, micro_warp` (same convention as other blocks).
- Exact tuple allow-list (the eight tuples in §2) validated at BOTH
  boundaries (`create-deepclean-job` whitelist AND worker settings
  validation). Arbitrary angles/scales/modes/partial/conflicting blocks
  are rejected.
- Settings codes: `SEQ-G0-…`, `SEQ-GX0-…`, `SEQ-G1-…` … `SEQ-G6-…`
  (seeded `lab-ctla1` AND unseeded goldens). **Goldens are canonical in
  the TypeScript settingsIdentity tests; Python consumes pinned vector
  fixtures and must not implement a second identity algorithm.**
- Phase B joint tuples (see §8) are added by a SECOND C88 BUILD that
  extends both allowlists, preset IDs, and identity predicates — a text
  addendum alone cannot change deployed boundaries.

## 5. Controls (build gate vs operator gate — separate)

- **Build gate (offline, same machine/pinned container):** on pinned
  post-wash fixtures, Config A before/after the patch and `geom-r0` are
  byte-identical; module determinism (run twice → identical); geometry
  invariants (output dims, analytic coverage mask gate below, matrix
  unit tests); `geom-x0` differs from `geom-r0` only by the
  interpolation pass.
- **Operator gate (live):** the leg runs a SAME-BUILD Config A arm
  alongside `geom-r0`. Control = **byte equality of delivered files**
  (equal bytes ⇒ the grade cache serves identical grades, so no separate
  grade-equality demand is made; two fresh vendor evaluations of
  different bytes are NOT assumed to be numerically identical).

## 6. Operator legs (two phases)

**Phase A:** Config A (live) + geom-r0, geom-x0, geom-r1…r6 =
**9 arms × 11 images = 99 cells**, seed `lab-ctla1`, regular /relab runs
(no corpus registration). Every delivered file downloaded + SHA-256
pinned; every delivered file graded detection-only with REAL g1; verbatim
ledger; C2PA deny-list; fresh tab, cap 10000. Standing Rule R2: owner may
extend freely.

**Phase B (second build, SAME-BUILD controls):** the second C88 build adds
J1–J3 (allowlists, preset IDs, identity predicates, codes) → master
verification → deployment. The Phase B operator leg includes, on the
second build:

- live Config A (same-build incumbent);
- `geom-r0` (byte-equality control);
- the winning Phase A arm (same-build head-to-head);
- J1–J3.

That is **up to 6 arms × 11 images = up to 66 cells**; byte-identical
pairs use the established cache / verbatim-duplicate rule. Total across
both phases: up to **165 cells**.

## 7. Quality eligibility (GL-Q) — executable recipe

Reference per arm: the SOURCE image passed through the IDENTICAL geometry
module of that arm (geometry-matched reference at delivered dims) — no
wash/camera/finish. Compute the frozen metric recipe
`tools/round_remint_1_01_validate.metric_record` (delivered vs reference).

- **ROI transform (axis-aligned boxes, not polygons):** each normalized
  ROI box's FOUR corners are mapped through the arm's forward affine
  (source→destination, same matrix chain as §3), re-normalized to [0,1],
  and the GL-Q box = the **axis-aligned bounding box** of those four
  points, clipped to [0,1]. GL-Q boxes are plain `[x0,y0,x1,y1]` slices,
  consumable by `metric_record` unchanged. The extra non-ROI pixels
  inside the bbox are accepted; each box's area ratio (bbox area /
  original ROI area) is recorded.
- **Required-ROI validity (fail-closed per class):** for an arm to be
  quality-eligible, EVERY image must retain at least one valid
  `texture` box AND at least one valid `protected` box after the
  transform (zero-area and fully-out-of-window boxes are invalid). Any
  image missing either class → arm quality-ineligible. (This prevents
  `metric_record` empty-list/NaN results.)
- **Geometry-integrity gates vs the UNWARPED source (fail-closed):**
  - Retained-content: `s ≤ 1.05` hard bound per arm, and the retained
    source-area fraction (computed from the transform) ≥ **0.90** —
    calibrated aspect-safely so geom-r4 passes at all corpus sizes
    (r4 ≈ 0.9405 at 800², 0.9474 at 1250², and 0.9086 on the 1250×703 /
    703×1250 rectangular fixtures). A 0.94 floor pre-rejects r4 on
    rectangular inputs by construction and is retired.
  - Protected-ROI clipping: no transformed protected-ROI bbox corner may
    fall outside [0,1]; any clipping → arm quality-ineligible.
  - ROI inflation: bbox area / original ROI area ≤ 1.5 for every box.
  - Replicated-border width (r5/r6 and any θ=0 joint arm only): defined
    as the **kernel-affected strip** — the set of output-pixel columns
    and rows whose full Lanczos4 support touches the border extension,
    measured unambiguously by warping an all-255 uint8 mask through the
    EXACT arm matrix/flags with a CONSTANT-ZERO border (diagnostic only;
    production still uses BORDER_REPLICATE) and recording the maximum
    run of values < 255 per edge. Frozen thresholds: r5 ≤ 6 px
    horizontal / 6 px vertical; r6 ≤ 14 px horizontal / 6 px vertical.
    `BORDER_REPLICATE` IS border synthesis — it is an accepted treatment
    only within these frozen widths, named and gated as such, and the
    measured strips are excluded from protected-ROI evaluation. The
    measured strip widths are reported verbatim in the build report.
- **Coverage gate (analytic, not pixel counting):** warp an all-255
  uint8 mask through the EXACT arm matrix, flags, and border policy,
  measured IMMEDIATELY on the geometry module output (before camera/
  finish). For tilt arms the mask output must be 255 everywhere (zero
  border contribution — guaranteed analytically by `s` with the
  denominator-formula margin and safety factor). r5/r6 are exempt from
  the zero-border gate but are gated by the replicated-border width
  rule above.
- **Exact JSON paths** (per `metric_record` return structure):
  `metrics.global.h1_energy_ratio`,
  `metrics.texture_residual.luma_rms_255`,
  `metrics.texture_residual.chroma_rms_255`,
  `metrics.protected_eatr_absolute_min`.
- **Aggregation:** H1 and luma/chroma RMS aggregate as cohort MEANS;
  protected EATR aggregates as the cohort MINIMUM.
- **Eligibility (vs the live Config A arm computed with the same recipe):**
  - mean(H1) ≥ 0.80 × ConfigA-mean(H1)
  - mean(luma RMS) ≤ 1.10 × ConfigA-mean(luma RMS)
  - mean(chroma RMS) ≤ 1.10 × ConfigA-mean(chroma RMS)
  - min(EATR) ≥ 0.95 × ConfigA-min(EATR)
- **Config A is the incumbent baseline and is NOT an eligible selection
  candidate** (it defines its own thresholds). Eligibility applies to the
  eight geometry arms only. AR2's A0-geometry edge gates are NOT reused
  for geometry arms.

## 8. Frozen decision rule (two phases, quality first)

1. **Control:** `geom-r0` delivered files must be byte-identical to the
   same-build live Config A arm files. Drift → ladder invalid, stop.
2. **Ranking:** among quality-eligible arms, rank by number of v3-passing
   images (AI ≤ 0.45, flux ≤ 0.30, deepfake ≤ 0.10); tiebreak 1 = lower
   cohort median AI; tiebreak 2 = lower cohort mean `luma_rms_255`.
3. **Feature comparisons (frozen pairings):**
   - R: geom-x0 vs geom-r1 vs geom-r2
   - T: geom-x0 vs geom-r3 vs geom-r4
   - W: geom-x0 vs geom-r5 vs geom-r6
   "Best" per feature = the level with the most v3 passes among
   quality-eligible arms in its pairing (tiebreak lower median AI).
4. **If geom-x0 is quality-ineligible:** the three feature ladders are
   NOT rated; J computation is void; Phase B is SKIPPED; report and pivot
   (wash-policy ladder next).
5. **Joint computation (mechanical, from Phase A):**
   - J1 = `{affine, bestR, bestT, bestW}`.
   - J2 = J1 with tilt one level toward L1 if bestT ≠ L1; else J1 with
     warp one level toward L1 if bestW ≠ L1; else omitted.
   - J3 = J1 with warp one level toward L1 if bestW ≠ L1; else omitted.
   Duplicates are dropped. Phase B runs REGARDLESS of whether any Phase
   A arm beat Config A.
6. **Final winner (SAME-BUILD Phase B candidate set only):** rank only
   the arms physically rerun on the second build — live Config A
   (baseline, not selectable), the rerun Phase A winner, and J1–J3 —
   with the §8.2 rule. All other Phase A arms become report-only after
   the Phase A winner is selected; their old-build results are NOT
   imported into the final ranking. The winner must STRICTLY beat the
   Phase B live Config A pass count to open the promotion path;
   otherwise report and pivot (wash-policy ladder next). Promotion
   additionally requires a BLINDED visual check of the winner's
   before/after pairs (reviewer does not know which arm is which).
7. **Non-amplification:** per image and per axis
   {ai_probability, flux_family, deepfake_probability}, for the winner
   and J1–J3: `arm_value − og_value ≤ +0.01`. Any exceedance beyond
   tolerance on any image → non-amplification FAIL (reported; promotion
   not eligible).
8. **Falsification scope:** "no arm beats Config A" falsifies the tested
   cells (Phase A eight arms; Phase B joints if run) — NOT the geometry
   hypothesis generally.

## 9. Build deliverables

1. Worker geometry module per §3, active only for `resampleMode: affine`
   presets; `bypass` is a no-op; all legacy presets bit-identical to
   before (zero-diff regression tests).
2. `requirements.txt`: pin `opencv-python-headless==4.10.0.84`.
3. UI: eight presets selectable with codes shown.
4. settingsIdentity + both boundary validators per §4; seeded + unseeded
   code goldens canonical in TypeScript tests; Python contract tests
   consume pinned vectors (no second identity implementation).
5. Python contract tests: determinism, geometry invariants, analytic
   coverage mask gate, pinned matrix fixtures for square (1250×1250),
   landscape (1250×703), and portrait (703×1250) at tilt θ∈{0.6,1.2},
   margin ≥ L assertions, identity-pass semantics, Config A zero-diff.
6. `C8_GEOMETRY_LADDER_BUILD_REPORT.md`.

Do not run the leg. Build + report only.
