# C8 MASTER PROMPT — 4D-1A BUILD BRIEF v3 (H1/H2 SOURCE TRANSFER)

Owner shorthand: "5E". Program name: **4D-1a**.
Supersedes: v2. Amended per C88's second-pass audit `C8_4D_1A_BRIEF_AUDIT_V2.md`.
This v3 is a **targeted correction release**: population, frozen denominators,
completed primitive specification, exact gate-6/gate-7 semantics, and the vendor
freeze rule. Everything in v2 not restated below stands.

Deliverable for THIS prompt: **audit response only.** No code, commits, deploys,
Supabase/RunPod actions, or grading.

## 1. Screening population (CHANGED — fixes both v2 blockers)

- **24 cells**: the SIX sentinels IMG-5, 6, 7, 8, 9, 11 × seeds `lab-ctla1` /
  `lab-ctla2` × B (transfer OFF) / C (transfer ON). 12 B/C pairs.
- Sentinel set ⊂ screening set by construction: gate 4 computes 6/6 image means
  AND 12/12 seed-level cells from the round itself.
- Budget: 24 × 23 = 552 privacy + 24 deepclean; vendor 0 during screening.
- Hard subset unchanged: IMG-5/6/9/11 × both seeds (8 of the 12 pairs).
- All 12 pairs have exact legacy incumbent baselines (no missing cells, no
  unrelated cells).

## 2. Frozen denominator (REPLACED — population-exact)

Evidence: `round-4d-cam-1/incumbent-o2-o5-baseline-v3.json`
SHA-256: `90be734b4c6a45b5077e8691a31e44ea26083a422cb9ab5fecf7c26ff1c2be9c`
(contains per-cell B job ids, O2/O5 pixel hashes, per-cell loss values, the exact
formula, and the population list).

| frozen value | number |
|---|---:|
| B-arm O2→O5 mean, the 12 round cells | **0.098217** (≥ 0.02 floor — well-conditioned) |
| hard-subset B mean (8 cells) | **0.106025** |
| G3 operational threshold | **0.07951875** (exact product; no rounding ambiguity) |

- G2 formula: `1 − mean(L_C) / mean(L_B) ≥ 0.25`, where each L is the combined
  transition-loss scalar from the COMMON pre-transfer O2 reference to the paired
  O5; means over the **12 paired cells** (never per-pair percentages).
- `O2_transfer→O5` loss reported separately as a diagnostic.

## 3. Completed deterministic primitives (ADDITIONS to §2.4)

**Confidence field (frozen formula):**
`m_scale = clip((0.25 − d_scale)/0.25, 0, 1)`,
`m_resid = clip((0.50 − d_resid)/0.50, 0, 1)`,
`m_orient = clip((15 − d_angle)/15, 0, 1)`,
`m_ncc = clip((ncc − 0.80)/0.20, 0, 1)`,
`m_snr = clip((min(snr, 8) − 4)/4, 0, 1)`.
`w_raw = min(m_scale, m_resid, m_orient, m_ncc, m_snr)` when cross-scale
persistence passes AND the pixel is outside the union edge mask; otherwise 0.
Then `w = gauss_σ3(w_raw)`, re-zeroed inside the dilated exclusion.

**Alignment geometry:** 3-level pyramid (gauss σ=1, 2× downscale); finest block
32 px, stride 16; search radius ±8 px per level; integer search + quadratic
subpixel refinement; bilinear displacement interpolation; tie → first occurrence;
reflect borders.

**Aligned-source construction:** source BANDS warped after band decomposition
(band-wise warp, bilinear, reflect borders). R2 itself is never warped.

**Noise estimate:** flat-region noise energy = MAD of the R2 luma H2 band over
the lowest-20%-edge-energy 32×32 tiles (per image); zero-noise fallback `1e-6`.

**Strong-edge mask:** Sobel magnitude (`_edge_mag` recipe), threshold p92
(edge-audit constant) at the H1 and H2 scales independently, unioned across
source and remint, 4-connectivity, Euclidean dilation (distance transform) with
radius exactly 2 px at the O2 lattice.

**Band synthesis:** `luma' = luma + (H1' − H1) + (H2' − H2)` in float64; then
`out_RGB = clip(RGB + (luma' − luma), 0, 1)` — the SAME luma delta added to all
three channels (chroma preserved; hue unchanged in this representation); single
clip; round to uint8. This is the complete reconstruction; no other gamut or
color operation is applied by the transfer.

**Numeric path:** gaussian filters implemented exactly as the frozen
`checkpoint_attribution._gauss` recipe (uint8-quantized input, PIL
GaussianBlur(radius), /255, float64 thereafter). Quantization of the filter
input is thereby part of the frozen recipe, not an ambiguity. All energy/NCC
arithmetic float64.

**Energy-cap enforcement:** single deterministic vectorized pass. After computing
`g` and `B'`, recompute post-transfer 15×15 window energies (stride 3, bilinear
upsample); where `E'_win > min(1.21 × E_win, E_src_win)`, scale `g(x)` by
`sqrt(target/E'_win)` from the window grid; recompute `B'` once with the
corrected `g`. No iteration, traversal-independent.

**Preset label:** `4D-1A — LAB · H1/H2 source transfer α=0.10` (exact requested
value; only local execution is capped downward).

**Report timing:** `engine.transfer_4d_1a` is assembled/finalized POST-O5, while
the in-memory O2 and R2 hashes are recorded at transfer time.

All thresholds in this section that are not inherited program constants are
**model estimates**, frozen as written.

## 4. Gate 6 exact semantics (ADDITIONS)

- Width gap = `abs(width_stage − width_reference)` per matched edge; worsening =
  `gap_C − gap_B` (source-relative).
- Edge support coordinates and inclusion/exclusion reasons are frozen and hashed
  BEFORE `O2_transfer` or C O5 is inspected.
- Pair median = median over valid matched edges within one image/seed pair;
  round median = median of the 12 pair medians.
- Minimum valid-edge counts (model estimates): ≥ 100 matched edges per pair and
  ≥ 20 protected-ROI edges wherever a protected second-peak verdict is claimed.
  Falling below a minimum is a GATE FAILURE, not a skipped pair.
- Excess-energy relative change denominator floor: `max(B_excess, 0.01)`
  (excess as fraction of normalized step); paired change computed before medians.
- Candidate-created second peak: a C peak > 10% with no matched B peak within
  ±0.5 profile px, or a matched B peak crossing from ≤10% to >10%.
- Already-above-threshold B peaks: C amplitude may not rise by more than 0.02 of
  the normalized main response.
- Profile smoothing, extrema separation, contrast floor, invalid-profile rules,
  and the incidence denominator are frozen in the pinned ESF evaluator version
  used by the round (evaluator code hashed before first light).
- `edge_width_10_90` remains report-only, never in a pass/fail statistic.

## 5. Gate 7 exact semantics (ADDITIONS)

- The MOCK evaluator is pinned by the deployed `grade-image` function identity
  hash at round time (same discipline as engine_version).
- Ordered component list = the three mission axes (ai, flux-family, deepfake)
  plus every additional component/family label the pinned MOCK emits. The
  zero-new-family-threshold-crossing rule applies to ALL emitted components,
  with the applied list declared in the round ledger before first light. If the
  pinned MOCK emits no family labels, the rule applies to the three axes and is
  declared as such.
- Score precision before thresholding, missing/error behavior: fail closed — an
  unavailable required component or unclassified result FAILS gate 7; it is
  never omitted.
- The +0.02 paired-worsening margin is a model estimate; the three product
  thresholds are fixed mission requirements.

## 6. Determinism additions

- Cross-machine noise-floor result is REPORTED; it never relaxes any same-machine
  hash gate.
- All gate metrics are computed on ONE machine from the hash-verified
  checkpoints (as in 4D-CAM-1); no B/C pair cell is compared across machines.

## 7. Vendor freeze (RULE CHANGED — no exception)

The owner must freeze — **before the first screening result is viewed** —
Vendor 2 (TruthScan or Sightengine), the named six sentinels, both vendors'
API/model versions, score-field mapping, retry/error policy, and the vendor
combination rule (lexicographic worst-category; each vendor's median adverse
score movement ≤ +0.05; every C sentinel must satisfy the fixed eligibility
thresholds at each required vendor). Screening may not start without this
freeze. Budget for the leg: 6 × B/C × 2 vendors = 24 calls (16 reserve of 40).

## 8. Audit questions for you

1. Confirm the population change (24 cells, sentinels-only) and the frozen
   denominator pair (0.098217 / 0.07951875) with evidence hash
   `90be734b…2be9c`.
2. Confirm §3 primitives are complete for two independent builders; list any
   remaining ambiguity with your proposed freeze value.
3. Confirm §4/§5 leave no grader discretion; if any remains, name it.
4. Deliver `C8_4D_1A_BRIEF_AUDIT_V3.md` (workspace root, untracked):
   accept/amend, reasoning per section, no code.
