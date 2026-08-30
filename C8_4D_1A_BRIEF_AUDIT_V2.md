# C8 Second-Pass Audit — 4D-1a Build Brief v2

Date: 2026-08-27  
Audited inputs: `C8_MASTER_PROMPT_4D_1A_BUILD_BRIEF_V2.md`, `C8_4D_1A_BRIEF_AUDIT_REVIEW.md`, and `round-4d-cam-1/incumbent-o2-o5-baseline.json`  
Scope: Audit only; no build, grading, deployment, vendor call, or operational action

## Verdict

**AMEND BEFORE BUILD — narrow v3 required.** V2 accepts the five original blockers in substance, and the corrected architecture is suitable for commissioning after the issues below are closed. It is not yet commission-ready because:

1. The frozen all-image denominator contains 17 legacy B cells from a different image/seed population, while the v2 round has 16 B/C pairs. Gate 2 also incorrectly says “means over 17 pair cells.”
2. Frozen sentinel IMG-7 is not one of the eight screening images, so the ≥5/6 sentinel screen and the stated later B/C vendor leg cannot be produced from the 32-cell round.
3. The phase-preserving equation is correct at coefficient level, but `w`, alignment geometry, noise estimation, edge-mask thresholds, aligned-source construction, band synthesis, gamut/clipping, and the actual energy-cap enforcement remain under-specified.
4. ESF gate 6 still needs exact source-gap, excess-energy denominator, second-peak matching, edge-count, and empty-ROI semantics to prevent grader discretion.
5. Vendor 2 remains unfrozen. V2 says both “before round first light” and that screening may proceed without the freeze; those positions conflict.

These are specification corrections. They do not reverse the accepted energy-only architecture or require a broader experiment.

## 1. Equation and source-spatial-variation audit

### Disposition: ACCEPT WITH IMPLEMENTATION CLARIFICATION

The new equation satisfies the core phase-preservation requirement at the individual band-coefficient level:

`B'(x) = g(x) · B_remint(x)`, with positive `g(x)` and no additive source coefficient.

The source cannot contribute its coefficient sign, zero crossing, or phase directly. The one-sided rule also prevents this recovery round from attenuating remint band energy.

Source spatial variation still enters the result through:

- the local source-energy envelope `E_src(x)`;
- the source-conditioned alignment confidence and `w(x)`;
- the union edge exclusion; and
- any spatial variation introduced by cap enforcement.

That is consistent with “source supplies target energy only,” but it means the output is not source-independent. A positive spatially varying gain preserves each individual band zero crossing, yet summing modified H1/H2 back into the base image can still move the composite luma ESF crossings or extrema. Gate 6 is therefore still necessary.

### Caps

The `g ≤ 1.10` amplitude cap and `E' ≤ 1.21 × E_remint` energy cap are mathematically consistent because `1.10² = 1.21`. Both remain **model-estimate thresholds**; no supplied transfer result verifies them.

The cap must be evaluated on the recomputed post-transfer 15×15 window energy, not inferred pointwise from `g`. With a spatially varying gain, overlapping windows can otherwise exceed the stated cap. The brief must freeze whether cap enforcement is a single deterministic rescale or an iterative procedure. I recommend a single deterministic final-window rescale with one fixed traversal-independent vectorized pass; this is a **model estimate** intended to preserve determinism.

## 2. Frozen-primitives audit

### Disposition: AMEND

Section 2.4 is materially stronger than v1 but is not complete enough for two independent builders to produce the same arm.

### Missing definitions that must be frozen

1. **Confidence field:** “confidence margin from the support gates” has no formula. Freeze the exact map from each gate margin into `w_raw` and the combination operator.
2. **Alignment geometry:** freeze block size, stride/overlap, search radius at each pyramid level, pyramid reduction kernel, integer/subpixel search, displacement interpolation, and rejection at ties/borders.
3. **Aligned-source construction:** state whether R2 is warped before band decomposition or source bands are warped afterward; freeze warp interpolation and its border behavior.
4. **Noise estimate:** define “flat-region noise energy,” its source image, selection percentile/mask, per-image versus global scope, and zero-noise fallback.
5. **Strong-edge mask:** freeze gradient operator, scales, threshold/hysteresis, connectivity, and whether dilation is Euclidean, square, or disk.
6. **Band synthesis:** state exactly how modified H1/H2 return to `final_image`. The expected form is the remint luma plus the two band deltas, followed by one frozen range/gamut operation; that reconstruction is not currently written.
7. **Chroma preservation:** specify the color representation and how a changed luma is recombined with unchanged chroma. Adding a luma delta to gamma-encoded RGB and clipping channels can change chroma.
8. **Numeric path:** “PIL GaussianBlur on uint8/255, float64” is ambiguous. Filtering uint8 and then converting is quantized; converting first conflicts with a claim of float64 throughout unless the exact supported PIL mode and internal precision are fixed. Likewise, PIL's actual border behavior must agree with the declared reflect mode.
9. **Energy-cap application:** define the local-energy recomputation, overlapping-window handling, and order-independent enforcement.

### Recommended confidence definition

The following is a **model estimate** that makes the current “confidence margin” language deterministic without adding a learned router:

- Normalize passing margins as `m_scale=(0.25-d_scale)/0.25`, `m_resid=(0.50-d_resid)/0.50`, `m_orient=(15-d_angle)/15`, `m_ncc=(ncc-0.80)/0.20`, and `m_snr=(snr-4)/4`, each clipped to `[0,1]`.
- Let `w_raw` be the minimum of those five margins when cross-scale persistence passes and the pixel is outside the union edge mask; otherwise zero.
- Smooth with the frozen Gaussian radius/σ 3 O2 px and re-zero inside the exclusion.

The SNR saturation at 8, minimum combination, and smoothing scale 3 are **model-estimate thresholds**. If the engineer chooses a different mapping, it must be frozen in v3 before implementation; it cannot be left to the builder.

For the missing edge threshold, a reasonable **model-estimate value** is the same p92 gradient threshold used by the edge audit, computed independently at the frozen H1 and H2 scales and unioned across source/remint, with no result-dependent tuning.

### Primitive threshold labeling

The 15×15 energy/NCC window, stride 3, smoothing scale 3 px, SNR 4, NCC epsilon `1e-9`, and any new alignment/search constants are **model estimates** unless they are identified as inherited, replay-proven program constants. V3 should label them accordingly.

The preset label should say `α=0.10`, not `α≤0.10`, because the requested experimental value is exact and only local execution is capped downward.

## 3. Frozen-denominator audit

### Arithmetic verification

The JSON arithmetic is correct for the cells it contains:

- 17-cell mean recomputes to `0.119252941176471`.
- The eight hard-subset cells recompute to `0.106025000000000`.
- `0.75 × 0.106025 = 0.07951875`.
- Evidence-file SHA-256: `5f9fbf3f9d21a76ba961efba545d835a575bea3d41ad204e91fa28574e23c542`.

### Population mismatch — blocking

V2 screens 16 pairs: IMG-1/4/5/6/8/9/10/11, each at ctla1 and ctla2. The denominator JSON is missing:

- IMG-1 / `lab-ctla2`
- IMG-4 / `lab-ctla2`
- IMG-10 / `lab-ctla2`

It instead contains four cells outside the v2 screen:

- IMG-2 / `lab-ctla1`
- IMG-3 / `lab-ctla1`
- IMG-7 / `lab-ctla1`
- IMG-7 / `lab-ctla2`

Consequently, `0.119253` is not a paired incumbent denominator for the proposed 16 C cells. Comparing a 16-cell C mean with a differently composed 17-cell B mean violates the sealed paired design.

### Required correction

Before first light, either:

1. publish the exact B mean for the same 16 image/seed cells in v2; or
2. change the screening population and cell count so B and C use the exact same frozen population.

Option 1 is preferred because it preserves the approved 32-cell round. Gate 2 must then say “means over the 16 paired cells.” The denominator floor 0.02 is a **model-estimate threshold** and can be applied to the corrected 16-cell mean.

The hard-subset denominator is population-matched and accepted. Freeze its operational threshold at one value. I recommend the exact `0.07951875` or a declared six-decimal value `0.079519`; writing `0.0795` as though it equals the exact product creates avoidable ambiguity.

The replacement baseline evidence should also record the metric/tool version or hash, input checkpoint hashes, exact pair list, transition-loss formula, and its own manifest hash. The current JSON proves arithmetic but not provenance by itself.

## 4. Screening-set and sentinel audit

### Disposition: AMEND — blocking

V2's eight screening images are IMG-1/4/5/6/8/9/10/11. Gate 4 and §5.2 freeze six sentinels as IMG-5/6/**7**/8/9/11. IMG-7 has no C screening cell, so:

- the ≥5/6 sentinel-image direction gate cannot be computed from the 32 cells;
- the promised seed-level `x/12` count cannot be produced; and
- a 24-call B/C vendor leg on those six sentinels lacks screened IMG-7 candidate outputs.

Freeze six sentinels that are all in the eight-image screen, or replace one screening image with IMG-7 and recompute the exact matched 16-cell denominator. The choice must be made before candidate output is viewed. This is a design-set decision, not a result-driven substitution.

## 5. Gate 6 and gate 7 exploit audit

### Gate 6 — remaining definitions

The source-relative, common-support, candidate-relative structure is accepted. Add these exact definitions:

- Width gap is `abs(width_stage − width_reference)` per matched edge; worsening is `gap_C − gap_B`.
- Edge support coordinates and inclusion/exclusion reasons are frozen and hashed before `O2_transfer` or C O5 is inspected.
- “Pair median” is the median over valid matched edges within one image/seed pair; “round median” is the median of 16 pair medians.
- A minimum valid-edge count is required. **Model-estimate value:** at least 100 valid matched edges per pair and at least 20 protected-ROI edges where a protected second-peak verdict is claimed. Falling below the count is a gate failure, not a skipped pair.
- Excess-energy relative change needs a denominator floor. **Model-estimate value:** denominator `max(B_excess, 0.01)` when excess energy is expressed as fraction of normalized step; compute paired change before medians.
- Define a candidate-created second peak as a C peak above 10% that has no matched B peak within ±0.5 profile px, or a matched B peak that crosses from ≤10% to >10%. The ±0.5-px match tolerance is a **model estimate**.
- Define whether “amplified” incumbent peaks below/above the threshold are gated. **Model-estimate recommendation:** for an already-above-threshold B peak, C amplitude may not rise by more than 0.02 of the normalized main response.
- Freeze profile smoothing, extrema separation, contrast floor, invalid-profile rules, and incidence denominator in the ESF evaluator version used by the round.

Without minimum counts and empty-ROI semantics, a grader could pass a problematic pair by excluding hard profiles or declaring no protected sample.

### Gate 7 — remaining definitions

Freeze and hash the MOCK evaluator/model version, ordered component list, family-label taxonomy, family alert thresholds, score precision before thresholding, and missing/error behavior. The correct failure semantics are fail closed: an unavailable required component or unclassified family fails gate 7 rather than being omitted.

The +0.02 paired worsening margin remains a **model estimate**. The three product thresholds are fixed mission requirements and are not model estimates.

## 6. Determinism and proof-gate disposition

### Disposition: ACCEPT AFTER §2 COMPLETION

Flag semantics, absent/false replay, same-machine identity, auxiliary separation, fixture expansion, and cross-machine non-authority are accepted. The proof gates cannot be final until the missing §2 primitives are frozen.

Also require the cross-machine noise-floor result to be reported, not used to relax any same-machine hash gate. No candidate cell may switch machine relative to its paired B cell. This is a control requirement, not a new quality threshold.

`engine.transfer_4d_1a` cannot know `O2_transfer→O5` at the moment transfer executes unless the report is finalized after O5. V3 should state that the report block is assembled/finalized post-O5 while preserving the hashes recorded at transfer time.

## 7. Vendor freeze

### Disposition: OWNER ACTION REQUIRED BEFORE FIRST LIGHT

I do not select or contact Vendor 2 in this audit. The owner must freeze TruthScan or Sightengine, the named six sentinels, API/model versions, score mapping, retry/error policy, and combination rule before the first screening result is viewed.

V2 currently says this must happen “before round first light,” then permits screening without it. Remove the exception. Allowing Vendor 2 to be chosen after MOCK results preserves post-result selection freedom on the lexicographically primary outcome, even if promotion remains blocked meanwhile.

The real-vendor gate should also state explicitly that every C sentinel must satisfy the applicable fixed eligibility thresholds at each required vendor, in addition to the carry-over median adverse-movement rule. If the vendors expose different fields, freeze the mapping before first light.

## Section-by-section disposition

- **§0 Mission — ACCEPT.** Delivery compensation is stated correctly.
- **§1 Edge findings — ACCEPT.** Composite attribution and model-estimate caution are correct.
- **§2.1 Placement — ACCEPT.** Standard O2 identity remains a strong free provenance check.
- **§2.2 Equation — ACCEPT CONCEPT; AMEND EXECUTION.** Positive remint-only scaling is phase-preserving at band level; freeze reconstruction and cap enforcement.
- **§2.3–2.4 Gates/primitives — AMEND.** Several builders' degrees of freedom remain.
- **§2.5 Flag — ACCEPT.** The prior contradiction is closed.
- **§2.6 Reporting — AMEND TIMING WORDING.** Finalize post-O5.
- **§3 Identity — AMEND LABEL.** Use exact `α=0.10` and incorporate the completed primitive specification.
- **§4 Proof — ACCEPT AFTER §2 IS FROZEN.** Add no relaxation based on cross-machine noise.
- **§5.1 G1 — ACCEPT; define “OR.”** Explicit O0/O1/O2 equality is correct.
- **§5.1 G2 — AMEND.** Replace the mismatched 17-cell denominator with the exact 16-pair incumbent population.
- **§5.1 G3 — ACCEPT ARITHMETIC; AMEND PRECISION.** Freeze `0.07951875` or one declared rounded value.
- **§5.1 G4 — AMEND.** Sentinel IMG-7 is absent from the screen.
- **§5.1 G5 — ACCEPT.**
- **§5.1 G6 — AMEND DEFINITIONS.** The intended safety policy is accepted.
- **§5.1 G7 — ACCEPT POLICY; AMEND EVALUATOR FREEZE.**
- **§5.2 — BLOCKED ON OWNER FREEZE.** Remove the post-first-light exception.
- **§6 Forbidden — ACCEPT.**

## Final recommendation

Do not commission v2 verbatim. Issue a short v3 that:

1. freezes the exact 16-pair B denominator and corrects “17” to “16”;
2. makes the sentinel set a subset of the screening set;
3. completes the deterministic energy/alignment/reconstruction specification;
4. closes the ESF and MOCK evaluator definitions; and
5. records the owner's Vendor 2 freeze before first light.

After those targeted corrections, the architecture and 32-cell experiment should be accepted without reopening the camera, wash, finisher, lattice, ROI, or budget decisions.
