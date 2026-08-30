# C8 MASTER PROMPT — 4D-1A BUILD BRIEF v2 (H1/H2 SOURCE TRANSFER)

Owner shorthand: "5E". Program name: **4D-1a**.
Supersedes: `C8_MASTER_PROMPT_4D_1A_BUILD_BRIEF.md` (v1).
Amended per C88's audit `C8_4D_1A_BRIEF_AUDIT.md` (verdict: AMEND BEFORE BUILD) and
the master-engineer review `C8_4D_1A_BRIEF_AUDIT_REVIEW.md`. Every amendment is
incorporated below; all model-estimate thresholds are labeled.

Deliverable for THIS prompt: **audit response only.** No code, no commits, no
deploys, no Supabase/RunPod actions, no grading. Build is commissioned separately
after this audit is accepted.

## 0. Mission (wording amended)

Recover detail at delivery: restore mid-band (H1/H2) energy in the remint using
the ORIGINAL as the energy reference — **remint-led, phase-preserving by
construction, support-gated, H0 excluded**. This compensates W1 at delivery; it
does NOT reduce the already-captured O1→O2 loss itself. One sealed variable:
transfer ON vs OFF, with every algorithm constant frozen (α requested = exactly
0.10).

## 1. Edge-audit findings (attribution caution amended)

1. Camera PSF does NOT broaden matched edges at O2 (C ≈ B, mono width +0.02 px).
2. Gate-6 widening was born in the composite O2→O5 stage (tone-lock + Quality
   Finish + sharpen + encode). Which substage inside that composite is causal is a
   **model estimate** until an internal substage pin proves it — the brief makes
   no substage attribution claims.
3. `edge_width_10_90` is blur-sensitive; it is report-only everywhere, never a
   pass/fail gate. Edge gates use matched-edge ESF (absolute px, mono fit).
4. Extrapolating finisher behavior beyond the five stage-pinned cases is a model
   estimate; the round measures every pair.

## 2. Design (equation amended — genuine phase-preserving energy matching)

### 2.1 Placement (unchanged)

In `ds_remint_v8_8.py`, after the O2 capture (`O2_precamera.png`) and before the
tone-lock block. **O2 is identical within every B/C pair** (hard provenance).
New auxiliary checkpoint `O2_transfer.png` (post-transfer, pre-tone-lock) via the
auxiliary whitelist — the ONE whitelist addition. `EXPECTED_CHECKPOINTS`
byte-for-byte unchanged.

### 2.2 Transfer equation (REPLACED)

The v1 coefficient-interpolation form is withdrawn. It imported source-coefficient
spatial variation and did not guarantee phase preservation. The transfer is now a
**one-sided remint-coefficient energy scaling**:

```
B'(x) = g(x) · B_remint(x)

g(x) = 1 + min( α · w(x) · (√(E_src(x)/E_remint(x)) − 1), 0.10 )
       where E_src(x) > E_remint(x), support passes, x outside exclusion
g(x) = 1 otherwise   (never attenuate remint detail in this round)
```

- Source sample values NEVER appear in the output coefficient. Sign is preserved
  exactly. Zero crossings cannot move from source coefficients (there are none).
- `α = 0.10` requested, frozen for every cell. Local caps below reduce the
  effective dose but the request never varies.
- Caps (model estimates, frozen): `g ≤ 1.10`; post-transfer local band energy
  `E' ≤ min(1.21 × E_remint, E_src)`.
- `w(x)`: confidence margin field from the support gates, smoothed (gauss σ = 3 px
  at O2 lattice), then re-zeroed inside the dilated strong-edge exclusion so
  smoothing cannot leak transfer across boundaries.
- Applied independently to H1 and H2 bands (luma only; chroma and H0 untouched).
  Bands = gauss(0.7) − gauss(1.4) and gauss(1.4) − gauss(4.0) — the program's HFTR
  definitions.

### 2.3 Support gates (strengthened)

Per position, ALL must pass (thresholds are model estimates unless noted):

1. adjacent-scale displacement agreement ≤ 0.25 O2 px;
2. residual post-alignment displacement ≤ 0.50 target-band px;
3. structure-tensor axial orientation difference ≤ 15° (polarity checked
   separately by NCC);
4. signed local NCC ≥ 0.80, polarity not reversed;
5. local usable-band SNR ≥ 4 relative to flat-region noise energy (below this,
   support is off — NCC/orientation/energy ratios are unstable in near-flat
   regions);
6. cross-scale persistence: support in BOTH H1 and H2;
7. strong-edge exclusion from the UNION of remint and aligned-source multiscale
   edge masks (a source-only or remint-only seam is exactly where transfer is
   unsafe); dilation = max(2 px, 2 × (4 × effective_psf_g of the final light
   pass)) = **2 px at the O2 lattice** (final light pass base_psf_g = 0.25 →
   4×0.25 = 1.0 → 2×1.0 = 2.0).

The ROI manifest is NOT shipped to the worker (measurement-only).

### 2.4 Frozen deterministic primitives (new appendix — all frozen)

| primitive | frozen definition |
|---|---|
| R2 construction | PIL `Image.resize` LANCZOS, RGB uint8 → float64/255, from O0 to O2 dims |
| luma | 0.2126 R + 0.7152 G + 0.0722 B |
| gauss | PIL `ImageFilter.GaussianBlur(radius=r)` on uint8/255, float64 |
| alignment | 3-level block pyramid, normalized cross-correlation, no RNG |
| energy window | 15×15 box (stride 3), bilinear-upsampled to full res |
| w smoothing | gauss σ = 3 px |
| NCC | Pearson over the 15×15 window, ε = 1e-9, argmax tie → first occurrence |
| border mode | reflect |
| precision | float64 throughout; report-block reductions defined elementwise-then-mean |
| serialization | stable key order, fixed numeric formatting, no timestamps |
| determinism | same-build/same-machine rerun byte-identical (O2 in, R2, O2_transfer, O5, report). Cross-machine runs are NON-authoritative for hash comparison; an identical-config cross-machine noise floor is measured at build time, never silently assumed |

### 2.5 Lab-only flag (semantics amended)

- `4d1a: boolean` in the remint block, strict.
- **`4d1a: true` with absent or invalid lab seed ⇒ fail closed** (edge 400 /
  worker error), mirroring `optics_psf_scale`.
- **`4d1a` absent or `false` ⇒ ordinary incumbent behavior, byte-identical**
  (with or without lab seed). Non-lab jobs: no transfer, no auxiliary file.
- Unknown keys, non-boolean values, unrecognized seed/code combinations fail per
  the frozen boundary contract.

### 2.6 Report blocks

- `engine.transfer_4d_1a`: applied, alpha_requested=0.10, alpha_effective stats,
  coverage, mean w, per-gate reject counts, band energy ratios before/after,
  **pixel hashes of the in-memory pre-transfer O2 buffer and the exact R2 buffer**.
- `engine.transfer_4d_1a` includes the deterministic O2_transfer→O5 diagnostic
  (see §5.1 G2 note) alongside the pre-transfer O2→O5 composite measurement.

## 3. Identity (α and all constants under the one candidate identity)

- Preset id `4d-1a`, label `4D-1A — LAB · H1/H2 source transfer α≤0.10`, CUSTOM
  identity, marker `SEQ-4D1A-`, seed-dependent codes exactly like CAM-1.
- Tuple: incumbent camera settings (`optics_psf_scale` absent/1.0) + `4d1a: true`
  + locked seed. α=0.10 and every §2.4 primitive are part of THIS identity.
- Frozen predicates (A / 1A / 2B / 3C) and their goldens unchanged; CAM-1
  predicates unchanged; `validateOpticsPsfScale` untouched.
- Experiment config_set: `["A", "SEQ-4D1A-<ctla1>", "SEQ-4D1A-<ctla2>"]`.

## 4. Build-time proof gates (amended; no cell may run until all pass)

1. `4d1a` absent AND `4d1a: false` each replay byte-identical to the incumbent
   (both with and without lab seed, where valid).
2. `4d1a: true` without lab seed fails closed; non-boolean/unknown keys rejected.
3. O2 identical within every B/C pair; `O2_transfer.png` exists iff flag on;
   main O0–O5 manifest never gains a file; auxiliary addition cannot alter main
   checkpoint ordering, manifest contents, or O5 pixels.
4. Frozen files zero-diff: `coherent_camera.py`, `checkpoint_attribution.py`,
   `camera_only_replay.py`, `checkpoint_capture.py`, `quality_finish.py`.
5. Identity tests: preset round-trip both seeds; four frozen goldens + CAM-1
   goldens byte-identical.
6. Determinism: same-build/same-machine reruns byte-identical for O2 input, R2,
   `O2_transfer`, O5, and the deterministic report block.
7. Fixture proofs (beyond the v1 reject fixtures): flat/near-flat inputs
   unchanged; E_src ≤ E_remint is a no-op; equal-energy/different-phase source
   cannot change remint coefficients; slanted edge retains its zero crossing with
   no source-side shoulder; confidence-mask boundaries introduce no new extrema;
   α=0 / flag false / flag absent each byte-identical; NaN, image borders, and
   zero-energy denominators fail safely; per-gate reject counts truthful.
8. `tsc`, `vite build`, deno checks/tests, Python tests all green.

## 5. Screening round (MOCK, after proof gates)

- 32 cells: IMG-5, 6, 9, 11 + IMG-1, 4, 8, 10 × `lab-ctla1`/`lab-ctla2` ×
  B (transfer OFF) / C (transfer ON). All MOCK; 736 privacy + 32 deepclean;
  vendor 0.

### 5.1 Pre-registered acceptance gates (frozen NOW)

1. **Provenance:** 16/16 OR pairs equal; **16/16 O2 pairs equal**; O0/O1/standard
   O2/source-object hash/seed/parameters equal within pairs; all checkpoint hashes
   verified; B codes `SEQ-CFA-*`, C codes the exact `SEQ-4D1A-*` tuple.
2. **Primary — pre-transfer O2→O5 composite recovery:**
   `1 − mean(L_C) / mean(L_B) ≥ 0.25`, where each L is the combined
   transition-loss scalar from the COMMON pre-transfer O2 reference to the paired
   O5 (means over the 17 pair cells; NEVER the mean of per-pair percentages).
   Frozen denominator from the incumbent B cells already retrieved
   (`round-4d-cam-1/incumbent-o2-o5-baseline.json`): **B mean = 0.119253** —
   well-conditioned (≥ 0.02 denominator floor). The `O2_transfer→O5` loss is
   reported separately as a diagnostic.
3. **Hard subset:** IMG-5/6/9/11 × both seeds, C mean O2→O5 loss
   ≤ **0.0795** (= 0.75 × frozen B hard-subset mean **0.106025**; audit value
   0.07951875). Same frozen arithmetic rule.
4. **Delivered detail:** median O5 EATR gain ≥ 0.04 absolute; median texture-ROI
   HFTR_H1 gain ≥ 8% relative; ≥5/6 sentinel image means move in the predicted
   direction; seed-level counts (x/12) reported explicitly.
5. **Safety:** protected EATR ≥ 0.98 × B in every pair; smooth luma/chroma RMS
   rise ≤ 5%; rho rise ≤ 0.03.
6. **Edge geometry (ESF, absolute, source-relative, candidate-relative):**
   edge support is DISCOVERED AND FROZEN from the common pre-transfer O2/R2 and
   evaluated at those exact coordinates across B O2, C `O2_transfer`, B O5, C O5,
   R2, R5. Per pair, matched-edge deltas → pair medians → round median of the
   16 pair medians. (All tolerances are model estimates.)
   - At `O2_transfer` vs B O2/R2 AND at O5 vs B O5/R5: median source-relative
     monotonic-width-gap worsening ≤ +0.25 px; no pair median > +0.50 px.
   - Median overshoot rise ≤ +0.02 per stage; no pair median > +0.03.
   - Median out-of-transition excess-energy rise ≤ 2% relative per stage; no pair
     > 5% relative.
   - Protected ROIs: ZERO candidate-created second signed peaks above 10% of the
     main response.
   - Globally: candidate-created second-peak incidence may rise by ≤ +0.25 pp
     overall and ≤ +1.0 pp in any pair. (Inherited incumbent ringing is measured
     in B and is NOT a failure; only new/amplified candidate behavior is gated.)
   - `edge_width_10_90`: report-only, never in any pass/fail statistic.
   - Edge counts and invalid-profile exclusions reported per pair.
7. **MOCK detection margin + carrier drift:** 16/16 C O5 cells within
   ai ≤ 0.45, flux-family ≤ 0.30, deepfake ≤ 0.10 (fixed product screen); no C
   detector component worsens by > +0.02 vs paired B (model estimate); **zero new
   family-threshold crossings relative to B** using the already-frozen MOCK family
   definitions; the complete B→C detector vector and any family-label change are
   reported, not just the three aggregate axes.

### 5.2 Vendor leg — frozen BEFORE round first light (not after)

The owner must freeze, before any cell runs: the six sentinel identities
(IMG-5/6/7/8/9/11), **Vendor 2** (TruthScan or Sightengine), both vendors'
API/model versions, score-field mapping, retry/error policy, and the vendor
combination rule (carry-over from 4D-CAM-1 gate 8: lexicographic worst-category,
each vendor's median adverse score movement ≤ +0.05). If the owner does not
freeze Vendor 2 in time, the screening round still runs, but the vendor leg
cannot start and the C arm cannot be promoted regardless of screening results.
Vendor budget: 6 sentinels × B/C × 2 vendors = 24 calls (16 reserve of 40).

## 6. Forbidden (unchanged)

No camera/PSF changes. No finisher, wash, wash-combo, lattice, or ROI-manifest
changes. No frozen-tool or `EXPECTED_CHECKPOINTS` modifications. No
commit/deploy/RunPod/Supabase action. No vendor calls.

## 7. Audit questions for you

1. Does the `g(x)` equation satisfy your phase-preservation requirement in full?
   Any remaining way source spatial variation enters the output?
2. Are the frozen primitives in §2.4 complete and implementable as written, and
   are the caps (1.10 / 1.21×) consistent with α=0.10 as you intended?
3. Confirm the frozen denominator arithmetic (§5.1 G2/G3) with the published
   B means (0.119253 / 0.106025).
4. Any gap left in §5.1 G6/G7 wording that a grader could exploit?
5. Mark every threshold you cannot verify as a model estimate, with your value.
6. Deliver `C8_4D_1A_BRIEF_AUDIT_V2.md` (workspace root, untracked):
   accept/amend, reasoning per section, no code.
