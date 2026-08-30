# C8 Optimization Audit Response

Date: 2026-08-27  
Role: Expert consultant  
Scope: Professional opinion and recommendations only; no grading or operational action

## Basis and confidence

This audit treats the measurements in the master brief as the complete evidentiary record. I did not independently reproduce the pipelines, inspect raw metric traces, or query real vendors.

- **Evidence** means the conclusion follows directly from the supplied numbers.
- **Model estimate** means a mechanism, threshold, risk, or expected product effect cannot be verified from the supplied numbers and is therefore professional judgment.

## Executive opinion

**Evidence:** Rejecting camera-radius ×0.50 was correct. It missed four magnitude gates, improved the retention metrics only modestly, and moved edge-width fidelity in the wrong direction. The safety results are useful: protected EATR, smooth-region RMS, and rho do not indicate a destructive candidate. They do not rescue a candidate that failed the primary quality objectives.

**Recommendation (model estimate):** Keep V12.3 restored. Proceed with 4D-1a as a tightly support-gated diagnostic, but do not treat source transfer as intrinsically safe: the original may contain the carrier that the wash is intended to break. The transfer should preserve remint geometry and phase wherever possible, with the original supplying target detail energy or only a confidence-projected residual. Run an edge-spread/ringing diagnostic before any further camera-radius change. Do not change the 1250-pixel ceiling globally until lattice and codec effects have been isolated.

**Recommendation (model estimate):** The most important distinction is between **product risk** and **measured fidelity loss**. W2 is the highest product risk because detection eligibility is lexicographically primary. W1 remains the largest measured image-quality loss and the correct target for the next zero-vendor experiment.

## 1. Weakness ranking W1–W5

### Recommended product-risk ranking

1. **W2 — wash re-stamp**
2. **W1 — O1→O2 camera plus resample loss**
3. **W3 — 1250-pixel stage-1 ceiling**
4. **W5 — codec compounding**
5. **W4 — camera dose and edge-widening risk**

### Rationale

**W2 first — Evidence:** The wash is the only proven carrier-breaker, yet two fingerprint-swap failures occurred and outcomes were strongly content-dependent. Detection eligibility is the primary product condition, so a re-stamp defeats the product even when visual quality is excellent. The oracle result across three configurations also establishes that candidate diversity is valuable and that one static route is inadequate.

**W2 first — Model estimate:** The expected business harm of a re-stamp is greater than the harm of a moderate retention loss because the former makes an output ineligible. Its exact frequency and severity cannot be estimated from the aggregates supplied.

**W1 second — Evidence:** O1→O2 has mean transition loss 0.1764 and is primary in 23 of 32 jobs. The ×0.50 radius experiment recovered only 5.7% of camera-only loss and 0.0142 median O5 EATR, so camera radius alone is not a sufficient remedy.

**W3 third — Evidence:** The cumulative figures are consistent with a serious resolution bottleneck, especially when high-resolution inputs are reduced before later processing. However, the supplied results do not isolate the 1250-pixel ceiling from resampling, camera filtering, sharpening, and codec loss.

**W3 third — Model estimate:** The ceiling probably amplifies W1 by collapsing source-frequency content before the finisher can use it. Its independent effect may be smaller than the current ranking implies; only a sealed lattice comparison can determine that.

**W5 fourth — Evidence:** q97 preserved more source-relative EATR than q92 in 32/32 jobs, so the direction is unusually consistent. The reported magnitude is small, which argues for removing avoidable JPEG handoffs but not for treating codec as the dominant loss.

**W5 fourth — Model estimate:** A float/RGB handoff is a low-risk improvement because it removes a repeated irreversible operation. It is unlikely by itself to close the W1 gap.

**W4 fifth — Evidence:** The tested radius change is rejected and the incumbent is restored; therefore this candidate is not a current shipping weakness. Its edge-width result is still a serious warning for future camera work.

**W4 fifth — Model estimate:** If the ×0.50 path or a similar sharpen/PSF change is reconsidered, W4 should temporarily move above W3 and W5 until ringing is explained. The several 100–600% edge-width regressions are too large to regard as benign without profile-level inspection.

## 2. 4D-1a: mid-band source transfer

### Recommendation

**Recommendation (model estimate):** H1/H2 is the right first frequency range to test against W1, but raw source coefficients should not be added unconditionally. Use a remint-preserving, confidence-weighted transfer in which local alignment, orientation, phase/polarity, and cross-scale agreement jointly define support. Alpha 0.10 should be a ceiling, not a uniform dose.

**Recommendation (model estimate):** H0 exclusion is correct. It reduces the chance of importing source noise, codec residue, synthetic microtexture, or a fine-scale carrier. It does not prove that H1/H2 is carrier-free.

### Required support and agreement gates

The following are **model estimates** intended as pre-registered engineering gates, not as new production presets:

1. **Local alignment:** estimate displacement on a pyramid and require the H1/H2 displacement to agree across adjacent scales. Reject support where motion is ambiguous, occluded, saturated, or locally non-rigid. A conservative starting requirement is less than 0.5 target-band pixel residual displacement and less than 0.25-pixel disagreement between adjacent scales.
2. **Orientation agreement:** use structure-tensor or steerable-band orientation, not gradient magnitude alone. Require a signed orientation difference no greater than 15 degrees on edge-like support.
3. **Phase and polarity agreement:** require positive signed correlation and no polarity reversal. A local signed normalized correlation of at least 0.80 is a defensible starting screen. Reject coefficients that create a second phase peak beside the remint edge.
4. **Cross-scale persistence:** accept a feature only when compatible support exists at both H1 and H2. An isolated response at one band is more likely to be noise, ringing, or registration error.
5. **Protected-edge exclusion:** exclude the frozen protected ROI and dilate the exclusion around strong product edges by at least the larger of two pixels or twice the measured effective PSF support. Feather the transfer confidence outside that exclusion; do not feather raw pixels across an edge.
6. **Energy cap:** cap added local band energy at the aligned source-band energy and reject any region whose transfer creates a new local maximum or secondary edge. This is more protective than a global alpha alone.
7. **Mask-boundary control:** process the full frame and apply smoothly varying confidence masks. Metrics may be cropped afterward; filtering or transfer should not be performed independently inside an ROI crop.

### Preferred architecture

**Model estimate:** The safest architecture is **phase-preserving energy matching**:

- Align source and remint locally.
- Derive a source target-energy map for H1/H2 only where agreement gates pass.
- Increase the remint's own H1/H2 coefficients toward that target while retaining the remint coefficient phase and orientation.
- Permit a small projected source residual only when it is collinear with the remint coefficient and survives the full agreement gate.

**Model estimate:** This attacks the measured loss without copying a complete source residual. It should reduce double edges because geometry remains remint-led. It may also reduce the chance of restoring a source carrier and must eventually be tested with real vendors.

If 4D-1a copies source phase directly, a zero-vendor quality pass must authorize only a later vendor leg—not product adoption.

## 3. Edge widening

### Mechanistic explanation

**Evidence:** Edge-ratio retention improved while the edge-width gap worsened by 8.3%, with 10 of 17 pairs worse. The candidate also remained safe on protected EATR, smooth RMS, and rho. This combination shows that an energy-based sharpness gain did not translate into better edge geometry.

**Model estimate:** Halving the PSF radii while leaving the scene-modulated sharpening behavior effectively calibrated to the incumbent can create a peaked composite modulation transfer function. The sharpen stage then acts on an already narrower or higher-energy transition and produces overshoot, undershoot, or a low-amplitude shoulder. That raises edge energy and can improve an edge ratio, while the 10% and 90% crossings move outward or become ambiguous. Resampling phase and nonlinear clipping/tone mapping can strengthen the effect.

The 100–600% cases may include genuine severe ringing, but they may also be ratio instability when the source or incumbent gap is near zero, a low-contrast edge has uncertain crossings, or the profile has multiple 10%/90% crossings. That interpretation is a **model estimate** until absolute widths and edge profiles are inspected.

### Next confirming measurement

**Recommendation (model estimate):** Before any code or radius change, run a substage edge-spread audit on the existing fixed-rung outputs and any already-available intermediate buffers:

- Match the same isolated edges at O1, post-resample, post-PSF, post-sharpen, and O2.
- Register edge-normal profiles to subpixel phase and stratify by orientation, contrast, and nearby texture.
- Report absolute 10–90 width in pixels and cycles per picture height, not only percentage gap closure.
- Measure peak overshoot, peak undershoot, energy outside the monotonic transition, number of crossing candidates, and MTF50/MTF90 from a monotonic fitted edge-spread function.
- Compute width twice: once on the raw profile and once after a monotonic/isotonic fit.

Confirmation rule (**model estimate**): the sharpen interaction is confirmed if the candidate's monotonic fitted width is no worse than incumbent while raw width, overshoot/undershoot, and out-of-transition energy increase. If both raw and fitted widths worsen before sharpening, the resample/PSF composition—not merely ringing—is broadening the edge. If widening appears only after sharpening, the scene-modulated sharpen is the attributed stage.

## 4. Wash re-stamp mitigation architecture

### Recommendation

**Recommendation (model estimate):** Use a fail-closed, content-routed candidate architecture with mandatory post-wash and post-finisher checks. Do not rely on one static wash configuration, and do not repair a failed wash by compositing unwashed source regions back into the output.

The recommended decision flow is:

1. **Content/probe routing:** route from observable content and probe behavior, because the supplied same-source outcomes show that source identity is not a sufficient predictor.
2. **Small approved candidate set:** generate a bounded set of already-approved wash paths. Candidate diversity is supported by the oracle result; this recommendation does not introduce a new wash combination.
3. **MOCK rejection first:** reject any candidate that fails the frozen detection screen or shows a fingerprint-family swap. Rank only the survivors.
4. **Regional diagnosis, not regional carrier bypass:** use crops and regions to locate visual damage or suspicious detector sensitivity. If regional repair is required, blend only between candidates that have each received the mandatory carrier-breaking wash. Never paste raw source or an unwashed region into a cleared candidate.
5. **Post-wash re-check:** check O1 globally and on stable crops under the normal delivery resize/codec transforms. This catches fragile candidates whose apparent clearance depends on one exact encoding.
6. **Post-finisher re-check:** eligibility must be established on O5, because later detail transfer, sharpening, resampling, or codec can change vendor scores. O1 clearance is necessary but not sufficient.
7. **Lexicographic selection:** among eligible candidates, choose by protected-edge fidelity, texture retention, naturalness, and smooth-region safety. If none is eligible, abstain or reroute; do not choose the least-bad flagged image.

**Evidence:** The need for routing and candidate diversity follows from the content-dependent outcomes and the three-configuration oracle. The need to re-check O5 is not established by the supplied vendor data.

**Model estimate:** Regional detector probes and encoding perturbations should be treated as robustness screens, not substitutes for final real-vendor eligibility. The 40-call cap remains fully compatible with this architecture because MOCK screening should eliminate most candidates before the real-vendor leg.

## 5. The 1250-pixel lattice

### Recommendation

**Recommendation (model estimate):** Keep 1250 pixels as the controlled incumbent for now. Do not infer from the cumulative retention numbers that native-resolution finishing will recover lost source detail. A native finisher can avoid another lattice loss and can improve edge placement, but it cannot reconstruct detail that the 1250-pixel representation no longer contains without synthesis or source guidance.

The float/RGB handoff should be isolated first because it removes a known irreversible handoff while keeping geometry and lattice fixed. A later lattice experiment should move only the finisher grid, with wash output, seed, camera parameters, sharpening, and codec held fixed.

### Evidence required to change the ceiling

I would change the production lattice only after a sealed paired test shows all of the following:

- No detection-eligibility regression at final O5 on the real-vendor leg.
- At least 25% reduction in the attributable O1→O2/lattice loss.
- Median O5 EATR gain of at least 0.04 and median texture HFTR_H1 gain of at least 8% relative.
- At least 10% closure of the absolute edge-width gap to source, without a new overshoot or secondary-edge failure.
- No protected EATR regression beyond 2%; smooth luma/chroma RMS rises no more than 5%; rho rises no more than 0.03.
- A blinded preference for the native result on sharpness and naturalness, with no increase in halos, plastic texture, or fabricated product seams.

The numeric gates reuse the existing frozen quality criteria. The blinded-preference requirement and the expectation that native finishing may help are **model estimates**. Zero-vendor evidence can screen a lattice candidate in, but cannot establish production eligibility.

## 6. One next experiment: 4D-1a sealed screening

### Design

**Recommendation (model estimate):** Run one eight-image, two-seed sealed A/B experiment: incumbent versus support-gated H1/H2 phase-preserving transfer at the already-approved alpha ceiling of 0.10. Use IMG-5, IMG-6, IMG-9, and IMG-11 as the known hard subset, plus four predeclared morphology-diverse images (recommended: IMG-1, IMG-4, IMG-8, and IMG-10). This produces 16 paired observations and uses zero vendor calls.

The only changed variable is H1/H2 transfer on/off. Source object, wash output, seed, lattice, camera, sharpen, finisher, codec, and frozen ROIs remain identical. H0 remains excluded. Support-gate parameters and masks are frozen before any candidate output is measured.

### Pre-registered gates

Pass requires every gate below; no post-hoc threshold changes:

1. **Provenance:** 16/16 pairs verify identical non-transfer inputs and parameters; baseline replay matches its recorded output at the accepted reproducibility tolerance.
2. **MOCK detection safety:** 16/16 candidates satisfy ai ≤0.45, flux-family ≤0.30, and deepfake ≤0.10, and no paired detector component worsens by more than 0.02. Applying the real-vendor numerical limits to MOCK and the 0.02 non-inferiority margin are **model estimates**; they are deliberately conservative screening rules, not proof of vendor eligibility.
3. **Primary retention:** mean O1→O2 transition-loss reduction is at least 25% versus paired incumbent.
4. **Hard subset:** mean O1→O2 transition loss for IMG-5/6/9/11 across both seeds is at most 0.1561.
5. **Delivered detail:** median paired O5 EATR gain is at least 0.04 and median texture HFTR_H1 gain is at least 8% relative.
6. **Protected and smooth safety:** no protected pair regresses by more than 2%; mean smooth luma and chroma RMS each rise no more than 5%; mean rho rises no more than 0.03.
7. **Edge geometry:** median absolute edge-width gap closes by at least 10%; at least 14/16 pairs are non-worse; no pair's absolute width gap worsens by more than 25%.
8. **Ghost/ringing safety:** median out-of-transition edge energy rises no more than 2% relative and no protected edge gains a second signed profile peak above 10% of the main edge response. These two thresholds are **model estimates** designed to catch the failure mode that EATR/HFTR can reward.

A pass authorizes the normal later real-vendor leg; it does not establish product eligibility. A failure on MOCK detection or protected/edge geometry is terminal even if aggregate EATR/HFTR improves.

## 7. Measurement-recipe audit

### 7.1 Transition loss

**Evidence:** Geometry-matched references and per-transition measurement are strong choices. Taking only negative deltas also matches the stated purpose: locating destructive stages.

**Potential concern (model estimate):** `max(loss_EATR, loss_HFTR_H1)` is a worst-axis statistic. It discards whether both axes degrade together, ignores improvements on the other axis, and can be dominated by whichever metric has greater noise or dynamic range. Calling a stage “PRIMARY” in 23/32 jobs is meaningful only if EATR and HFTR_H1 have comparable repeatability and scaling.

**Recommendation (model estimate):** Keep the frozen scalar for gate continuity, but always report beside it the paired two-component vector, the joint-loss rate, median, interquartile range, and a paired bootstrap confidence interval. Explain the missing 33rd chain in the 23/32 comparison. Do not use the maximum alone to choose an architecture.

### 7.2 EATR and HFTR_H1

**Evidence:** The opposing edge-ratio and edge-width results demonstrate that retention energy is not equivalent to faithful geometry.

**Potential concern (model estimate):** EATR can reward overshoot and ringing. HFTR_H1 can reward noise, codec texture, aliasing, or sharpen residue unless retained energy is required to be coherent with the aligned source. Fixed pixel-frequency bands are also not comparable across 800-, 1024-, 1080-, 1600-, and 2048-pixel images unless they are normalized to image scale or physical resampling scale.

**Recommendation (model estimate):** Report source-coherent cross-power or signed band correlation in addition to raw retained energy. Normalize band definitions in cycles per picture height and disclose the analysis grid. Separate luma and chroma results where 4:2:0 codec effects are relevant. Continue to use EATR/HFTR for sensitivity, but never allow them to overrule edge geometry or visible artifact gates.

### 7.3 `edge_width_10_90`

**Evidence:** The metric caught a defect that the energy ratios missed, so it is indispensable.

**Potential concern (model estimate):** A 10–90 width assumes an isolated, sufficiently contrasted, approximately monotonic edge. Ringing creates multiple crossings; low-contrast or textured edges make crossings unstable. Percentage “gap closure” can explode when the source-to-incumbent gap is near zero. The reported 100–600% regressions therefore require absolute-pixel profiles before their magnitude is interpreted.

**Recommendation (model estimate):** Retain the raw metric, add a monotonic fitted width, and report absolute width, contrast, edge orientation, overshoot, undershoot, crossing count, and denominator floor. Define gap closure on absolute distance to source and mark near-zero denominators as indeterminate rather than enormous percentages.

### 7.4 ROI crops

**Evidence:** Freezing independently authored protected, smooth, and texture regions before round output is viewed is strong protection against post-hoc selection. Role-specific gates are also more informative than one full-frame average.

**Potential concern (model estimate):** Axis-aligned boxes are measurement supports, not semantic masks. A protected box intentionally contains an edge and may include background; texture and smooth boxes may contain lighting gradients or small contaminating structures. Filtering a crop independently introduces boundary conditions that do not exist in the full-frame product. A single regional average can also hide a localized halo.

**Recommendation (model estimate):** Always process the full frame, then crop for measurement. Erode measurement support by the largest operator/filter radius, keep edge pixels for protected-edge metrics but separate subject-side and background-side profiles, and report per-ROI values before aggregation. Validate smooth and texture support with local gradient/variance maps without moving the frozen boxes. Do not redefine or relocate a box after seeing results.

### 7.5 Reproducibility and reporting

**Evidence:** Bit-exact replay on 10/17 pairs and no more than four LSB difference on the remaining seven, with identical layer parameters, is good provenance evidence. It is not fully bit-exact experimental control.

**Model estimate:** Four-LSB drift is unlikely to explain the large gate failures, but its effect on a small median gain such as 0.0142 cannot be certified without a repeatability baseline. Run identical-config cross-machine repeats to establish metric noise floors, or perform paired cells on one pinned machine when the expected effect is small.

The “6/6 sentinel” result should also state the seed-level result explicitly—whether it was 12/12 cells, six image-level majorities, or another aggregation. That reporting clarification is a recommendation; the supplied result is not sufficient to infer the seed-level count.

## Final recommendation

Proceed with the approved 4D-1a screen, but implement it conceptually as remint-led, support-gated H1/H2 restoration rather than naive source-pixel reinjection. Treat any zero-vendor pass as permission for further evaluation only. Keep W2 as the top product risk, retain W1 as the top measured quality target, isolate float/RGB handoff next, and do not touch camera radii again until raw and monotonic edge-spread profiles identify whether the observed widening is true blur, ringing-induced crossing distortion, or both.
