# C8 MASTER PROMPT — 4D-1A BUILD BRIEF FINAL (CONSOLIDATED, COMMISSION-READY)

Owner shorthand: "5E". Program name: **4D-1a — H1/H2 source transfer**.
This document is the SINGLE authoritative specification. It consolidates v1/v2/v3
and C88's final-pass redlines (`C8_4D_1A_BRIEF_AUDIT_V3.md`). On any conflict with
earlier versions, THIS document wins. C88 has recommended **ACCEPT FOR BUILD**
once these items are recorded; no further architecture review is expected.

Deliverable for THIS prompt: **the build.** Hard rules unchanged: no commits, no
deploys, no Supabase/RunPod actions, no grading by the builder — return an
uncommitted build report for master-engineer verification.

## 0. Mission

Recover detail at delivery: restore mid-band (H1/H2) energy in the remint using
the ORIGINAL as the energy reference — remint-led, phase-preserving by
construction, support-gated, H0 excluded. One sealed variable: transfer ON vs
OFF. α requested = exactly 0.10. This compensates W1 at delivery; it does not
change the already-captured O1→O2 loss.

## 1. Screening round (frozen)

- **24 cells**: six sentinels IMG-5, 6, 7, 8, 9, 11 × seeds `lab-ctla1` /
  `lab-ctla2` × B (transfer OFF) / C (transfer ON) = 12 B/C pairs.
- Sentinel set = screening set: gate 4 computes 6/6 image means and 12/12
  seed-level cells from the round itself.
- Hard subset: IMG-5/6/9/11 × both seeds (8 of 12 pairs).
- Budget: 24 × 23 = 552 privacy + 24 deepclean; vendor 0 during screening.
- All MOCK; operator Flash Max; same per-cell checks as 4D-CAM-1.

### Frozen denominator (evidence `round-4d-cam-1/incumbent-o2-o5-baseline-v3.json`,
SHA-256 `90be734b4c6a45b5077e8691a31e44ea26083a422cb9ab5fecf7c26ff1c2be9c`)

| frozen value | number |
|---|---:|
| B-arm O2→O5 mean, the 12 round cells | **0.098217** |
| hard-subset B mean | **0.106025** |
| G2 operational C ceiling | **0.07366275** (= 0.75 × 0.098217) |
| G3 threshold | **0.07951875** (= 0.75 × 0.106025) |

## 2. Design

### 2.1 Placement

In `ds_remint_v8_8.py`, after the O2 capture (`O2_precamera.png`) and before the
tone-lock block. **O2 is identical within every B/C pair.** New auxiliary
checkpoint `O2_transfer.png` (post-transfer, pre-tone-lock) — the ONE whitelist
addition in `tools/auxiliary_checkpoints.py`. `EXPECTED_CHECKPOINTS`
byte-for-byte unchanged.

### 2.2 Transfer equation

```
B'(x) = g(x) · B_remint(x)

g(x) = 1 + min( α · w(x) · (√(E_src(x)/E_remint(x)) − 1), 0.10 )
       where E_src(x) > E_remint(x) and support passes at x
g(x) = 1 otherwise (never attenuate remint detail in this round)
```

- Source sample values NEVER appear in the output coefficient. Sign preserved
  exactly. α = 0.10 requested, frozen for every cell.
- Caps (model estimates, frozen): `g ≤ 1.10`; post-transfer local band energy
  `E' ≤ min(1.21 × E_remint, E_src)`.
- Applied independently to H1 and H2 (luma only; chroma and H0 untouched).
  Bands = gauss(0.7) − gauss(1.4) and gauss(1.4) − gauss(4.0).

### 2.3 Support gates (per position; ALL must pass)

1. adjacent-scale displacement agreement ≤ 0.25 O2 px;
2. residual post-alignment displacement ≤ 0.50 target-band px;
3. structure-tensor axial orientation difference ≤ 15° (polarity checked by NCC);
4. signed local NCC ≥ 0.80, polarity not reversed;
5. local usable-band SNR ≥ 4 (see §2.4 noise energy);
6. cross-scale persistence: support in BOTH H1 and H2;
7. outside the union strong-edge exclusion (dilation exactly 2 px Euclidean at
   the O2 lattice; mask = union of source and remint edges).

The ROI manifest is NOT shipped to the worker (measurement-only).

### 2.4 Confidence field (final form — support re-masking REQUIRED)

Margins (each clipped to [0,1]): `m_scale = (0.25 − d_scale)/0.25`,
`m_resid = (0.50 − d_resid)/0.50`, `m_orient = (15 − d_angle)/15`,
`m_ncc = (ncc − 0.80)/0.20`, `m_snr = (min(snr,8) − 4)/4`.
`w_raw = min(m_scale, m_resid, m_orient, m_ncc, m_snr)` when cross-scale
persistence passes AND outside the union edge mask; otherwise 0.

**Final weight: `w = clip(gauss_σ3(w_raw), 0, 1) × support_binary`, where
`support_binary` is 1 only where ALL five numeric gates, cross-scale
persistence, and outside-edge-exclusion pass.** Smoothing may NEVER leak
positive weight into pixels that failed any support gate. σ3 smoothing is a
model-estimate threshold (already declared).

### 2.5 Frozen primitives

| primitive | frozen definition |
|---|---|
| R2 | PIL `Image.resize` LANCZOS, RGB uint8 → float64/255, O0 → O2 dims |
| luma | 0.2126 R + 0.7152 G + 0.0722 B |
| gauss | frozen `checkpoint_attribution._gauss` recipe: uint8-quantized input, PIL `GaussianBlur(radius)`, /255, float64 after |
| edge recipe | `_edge_mag` = `np.gradient` magnitude `hypot(gx, gy)` — **NOT Sobel**; p92 threshold, H1 and H2 scales separately, unioned source+remint, 4-connectivity, Euclidean dilation 2 px |
| alignment | computed between remint O2 luma and R2 luma; 3-level pyramid (gauss σ=1, 2× downscale); 32×32 blocks, stride 16 **in each level's own pixels**; coarse accepted displacement ×2 initializes the next-finer search center; ±8 residual search; independent 1-D parabolic refinement through peak ±1 neighbors; subpixel offset clamped to ±0.5; zero offset at boundary peak or non-concave/degenerate fit; bilinear displacement interpolation; tie → first occurrence; reflect borders. Resulting field warps SOURCE H1/H2 bands into remint geometry (band-wise warp, bilinear, reflect; R2 itself never warped) |
| energy window | 15×15 box, stride 3, bilinear-upsampled to full res |
| noise energy | lowest-20% tiles (32×32) by mean squared `_edge_mag`; concatenate their H2 samples; `noise_energy = max((1.4826 × MAD)², 1e-6)` with MAD about the selected-sample median; `SNR = local_band_energy / noise_energy` |
| synthesis | `delta = (H1'−H1)+(H2'−H2)`; `delta_safe = clip(delta, −min(R,G,B), 1−max(R,G,B))`; `out_RGB = RGB + delta_safe`; single uint8 rounding. Channel differences are preserved EXACTLY (including highlights/shadows). Report the fraction of pixels where `delta_safe` was capped |
| cap enforcement | after window-derived correction, clamp corrected gain to `[1.0, 1.10]` (one-sided invariant preserved); recompute final 15×15 window energies; **fail closed** if any valid grid window exceeds `min(1.21×E_remint, E_source)` beyond 1e-9 relative (float64). Single vectorized pass, traversal-independent, no iteration |
| precision | float64 throughout; deterministic serialization (stable key order, fixed numeric formatting, no timestamps) |
| determinism | same-build/same-machine rerun byte-identical (O2 input, R2, `O2_transfer`, O5, report). Cross-machine runs NON-authoritative; noise floor measured at build time, reported, and never relaxes any same-machine hash gate or screening threshold |

All thresholds in §2.5 not inherited from frozen tools are **model estimates**,
frozen as written.

### 2.6 Lab-only flag

`4d1a: boolean` in the remint block, strict. `4d1a: true` with absent or invalid
lab seed ⇒ fail closed (edge 400 / worker error). `4d1a` absent or `false` ⇒
ordinary incumbent behavior, byte-identical. Non-lab jobs: no transfer, no
auxiliary file. Unknown keys, non-boolean values, unrecognized seed/code
combinations fail per the frozen boundary contract.

### 2.7 Report blocks

`engine.transfer_4d_1a`: applied, alpha_requested=0.10, alpha_effective stats,
coverage, mean w, per-gate reject counts, band energy ratios before/after,
capped-delta pixel fraction, cap-enforcement verification result, and **pixel
hashes of the in-memory pre-transfer O2 buffer and the exact R2 buffer**.
Assembled/finalized POST-O5 (hashes recorded at transfer time); includes the
`O2_transfer→O5` diagnostic loss alongside the pre-transfer O2→O5 composite.

## 3. Identity

- Preset id `4d-1a`, label `4D-1A — LAB · H1/H2 source transfer α=0.10`,
  CUSTOM identity, marker `SEQ-4D1A-`, seed-dependent codes exactly like CAM-1.
- Tuple: incumbent camera settings (`optics_psf_scale` absent/1.0) + `4d1a: true`
  + locked seed. α=0.10 and every §2.5 primitive are part of THIS identity.
- Frozen predicates (A/1A/2B/3C) and goldens unchanged; CAM-1 predicates
  unchanged; `validateOpticsPsfScale` untouched.
- Experiment config_set: `["A", "SEQ-4D1A-<ctla1>", "SEQ-4D1A-<ctla2>"]`.

## 4. Build-time proof gates (no cell may run until all pass)

1. `4d1a` absent AND `4d1a: false` each replay byte-identical to the incumbent
   (with and without lab seed, where valid); `4d1a: true` without lab seed fails
   closed; non-boolean/unknown keys rejected.
2. O2 identical within every B/C pair; `O2_transfer.png` exists iff flag on;
   main O0–O5 manifest never gains a file; auxiliary addition cannot alter main
   checkpoint ordering, manifest contents, or O5 pixels.
3. Frozen files zero-diff: `coherent_camera.py`, `checkpoint_attribution.py`,
   `camera_only_replay.py`, `checkpoint_capture.py`, `quality_finish.py`.
4. Identity tests: preset round-trip both seeds; four frozen goldens + CAM-1
   goldens byte-identical.
5. Determinism: same-build/same-machine reruns byte-identical for O2 input, R2,
   `O2_transfer`, O5, and the deterministic report block.
6. Fixtures (beyond v1 reject fixtures):
   - flat/near-flat inputs unchanged;
   - E_src ≤ E_remint is a no-op;
   - equal-energy/different-phase source cannot change remint coefficients;
   - slanted edge retains its zero crossing with no source-side shoulder;
   - confidence-mask boundaries introduce no new extrema;
   - α=0 / flag false / flag absent each byte-identical;
   - NaN, image borders, zero-energy denominators fail safely;
   - **no final `w` > 0 outside complete support after smoothing**;
   - **exact `_edge_mag` recipe equivalence** (np.gradient, not Sobel);
   - **gain never below 1 after cap enforcement**;
   - **final window-energy cap verified (fail-closed at 1e-9 relative)**;
   - **channel-difference preservation holds or capped-delta fraction is
     reported truthfully**;
   - per-gate reject counts truthful.
7. `tsc`, `vite build`, deno checks/tests, Python tests all green.

## 5. Pre-registered acceptance gates (frozen NOW)

1. **Provenance:** 12/12 OR pairs equal; **12/12 O2 pairs equal**; O0/O1/standard
   O2/source-object hash/seed/parameters equal within pairs; all checkpoint
   hashes verified; B codes `SEQ-CFA-*`, C codes the exact `SEQ-4D1A-*` tuple.
   Per-pair B replay delta vs the frozen baseline evidence reported (context).
2. **Primary — pre-transfer O2→O5 composite recovery:**
   `1 − mean(L_C)/mean(L_B) ≥ 0.25`, L = combined transition-loss scalar from
   the COMMON pre-transfer O2 reference to the paired O5; means over the **12
   paired cells** (never per-pair percentages). Operational form:
   **`mean(L_C) ≤ 0.07366275`**. `O2_transfer→O5` reported separately.
3. **Hard subset:** IMG-5/6/9/11 × both seeds, C mean O2→O5 loss
   **≤ 0.07951875** (exact).
4. **Delivered detail:** median O5 EATR gain ≥ 0.04 absolute; median texture-ROI
   HFTR_H1 gain ≥ 8% relative; ≥5/6 sentinel image means move in the predicted
   direction; seed-level counts (x/12) reported explicitly.
5. **Safety:** protected EATR ≥ 0.98 × B in every pair; smooth luma/chroma RMS
   rise ≤ 5%; rho rise ≤ 0.03.
6. **Edge geometry (ESF, absolute, source-relative, candidate-relative):**
   edge support discovered and frozen from the common pre-transfer O2/R2 and
   evaluated at those exact coordinates across B O2, C `O2_transfer`, B O5,
   C O5, R2, R5. Pair median = median over valid matched edges in a pair; round
   median = median of the 12 pair medians. (Tolerances are model estimates.)
   - Width gap = `abs(width_stage − width_reference)` per edge; worsening =
     `gap_C − gap_B`. At `O2_transfer` vs B O2/R2 AND at O5 vs B O5/R5: median
     worsening ≤ +0.25 px; no pair median > +0.50 px.
   - Overshoot: median rise ≤ +0.02 per stage; no pair median > +0.03.
   - Out-of-transition excess energy: relative change per matched edge =
     `(C_excess − B_excess) / max(B_excess, 0.01)` computed BEFORE pair medians;
     median rise ≤ 2% relative per stage; no pair > 5% relative.
   - Second peaks: candidate-created = C peak > 10% with no matched B peak
     within ±0.5 profile px, or a matched B peak crossing from ≤10% to >10%.
     Protected ROIs: ZERO candidate-created second peaks. Globally: incidence
     may rise ≤ +0.25 pp overall and ≤ +1.0 pp in any pair. An
     already-above-threshold B peak: C amplitude may not rise > +0.02 of the
     normalized main response.
   - Minimum valid-edge counts: ≥ 100 matched edges per pair and ≥ 20
     protected-ROI edges wherever a protected second-peak verdict is claimed.
     Below minimum = GATE FAILURE, not a skipped pair; a protected ROI with
     < 20 valid edges fails gate 6 even if another protected ROI passes.
   - Pinned ESF evaluator version hashed; its hash, the edge-support artifact
     hash, valid/invalid counts, and exclusion-reason histogram recorded in the
     round ledger BEFORE candidate inspection.
   - `edge_width_10_90`: report-only, never in any pass/fail statistic.
7. **MOCK detection margin + carrier drift:** all **12/12** C O5 cells within
   ai ≤ 0.45, flux-family ≤ 0.30, deepfake ≤ 0.10 (fixed product screen);
   no C detector component worsens by > +0.02 vs paired B (model estimate); zero
   new family-threshold crossings relative to B across ALL components the pinned
   MOCK emits (list declared before first light); full B→C detector vector and
   family-label changes reported. Evaluator = pinned deployed `grade-image`
   identity hash, recorded per cell, ONE unchanged identity across all 24 cells
   (identity change aborts the round). Full numeric precision as returned by the
   pinned evaluator; no display rounding before eligibility or paired-delta
   comparisons. Missing/unclassified results fail closed.

## 6. Vendor leg (owner prerequisite — no exception)

The owner must freeze, BEFORE the first screening result is viewed: Vendor 2
(TruthScan or Sightengine), the named six sentinels, both vendors' API/model
versions, score-field mapping, retry/error policy, and the vendor combination
rule (lexicographic worst-category; each vendor's median adverse score movement
≤ +0.05; every C sentinel must satisfy the fixed eligibility thresholds at each
required vendor). **Screening may not start without this freeze.** Budget:
6 × B/C × 2 vendors = 24 calls (16 reserve of 40).

## 7. Forbidden

No camera/PSF changes. No finisher, wash, wash-combo, lattice, or ROI-manifest
changes. No frozen-tool or `EXPECTED_CHECKPOINTS` modifications. No commit,
deploy, RunPod/Supabase action, or vendor call by the builder.

## 8. Deliverable

Return `C8_4D_1A_BUILD_REPORT.md` (workspace root, untracked) containing: exact
`git diff` file list and changed-line summary within §2–§3; identity goldens
before/after; full test outputs; baseline/candidate proof hashes; the
determinism and fixture results per §4; a signed declaration: no commit, no
deploy, no RunPod/Supabase action, no grading, no cell run.
