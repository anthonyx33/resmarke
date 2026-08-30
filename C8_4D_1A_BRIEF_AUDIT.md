# C8 Audit — 4D-1a H1/H2 Source-Transfer Build Brief

Date: 2026-08-27  
Audited documents: `C8_MASTER_PROMPT_4D_1A_BUILD_BRIEF.md` and `EDGE_SPREAD_AUDIT_REPORT.md`  
Scope: Audit response only; no build, grading, deployment, vendor call, or operational action

## Verdict

**AMEND BEFORE BUILD.** The experiment is directionally correct and the corrected O2→O5 primary gate is causally appropriate. The brief is not yet commission-ready because five issues affect the meaning or integrity of the sealed variable:

1. The transfer equation copies source band coefficients and therefore does not guarantee the claimed remint-phase preservation.
2. Alpha 0.10 is a blend coefficient, not a bound on local amplitude or energy change; the actual dose is not fully constrained.
3. The O2 edge gate is vacuous if it compares the standard O2 checkpoints, which are identical by construction. It must compare C `O2_transfer` against paired B O2.
4. The edge gate omits the promised out-of-transition-energy check and uses an absolute second-peak condition that may reject inherited incumbent ringing.
5. Replay/determinism and flag-validation rules leave ambiguity around `false` versus absent, floating-point execution, the R2 resampler, and the phrase “absent-without-seed.”

Two further items must be frozen before first light: the exact O2→O5 reduction formula and its incumbent denominator, and the six real-vendor sentinels plus Vendor 2 and vendor pass/fail aggregation.

With the amendments below, I recommend commissioning the build.

## Edge-audit interpretation

**Evidence:** Approximately 3,300 matched O2 edges per arm show essentially identical camera-stage monotonic widths: 20.95 px for B and 20.97 px for C. O2 overshoot differs by only +0.005. This rejects camera-stage geometric broadening as the explanation for the old gate result.

**Evidence:** The stage-pinned cases localize the large frozen-metric divergence to the composite O2→O5 path. The old `edge_width_10_90` counts above-threshold gradient run length and is not a geometric blur-width measure. Demoting it to context-only is correct.

**Model estimate:** The report does not isolate adaptive sharpen from tone lock, Quality Finish, and final encoding inside O2→O5. “The finisher composite amplifies small O2 differences” is supported on the audited cases; “adaptive sharpen is the causal substage” remains a model estimate until an internal substage pin proves it. This does not require a finisher change in 4D-1a, but the report and brief should avoid overstating attribution.

**Model estimate:** O5 ESF and stage pinning cover five selected cases, so extrapolating the precise finisher behavior to all 17 prior pairs is also a model estimate. The new round correctly measures O2-transfer and O5 behavior on every pair.

## 1. Support-gate sufficiency and weakest gate

### Finding

The support-gate concept is conservative but **not sufficient as written**. Alignment, orientation, polarity, cross-scale persistence, and strong-edge exclusion are the right safety dimensions. The weakest stated gate is §2.2(3g), “energy cap; no new local maxima or secondary edges,” because its energy estimator, neighborhood, candidate construction, and rejection semantics are undefined. It is also being asked to compensate for a transfer equation that does not preserve phase.

### Mandatory amendment: make the transfer genuinely remint-phase preserving

The current equation

`B' = B_remint + α · w · (B_src_aligned − B_remint)`

is coefficient interpolation. Even with equal signs, it imports the source coefficient's spatial variation and can move extrema and zero crossings. “Same sign” prevents polarity inversion; it does not prove phase preservation.

**Recommendation (model estimate):** Let the aligned original supply only a local energy-envelope target. Scale the remint coefficient without adding a source coefficient:

`B' = g · B_remint`

where `g` is derived from the local source/remint energy ratio, confidence-weighted, spatially regularized, and constrained as follows:

- Transfer is one-sided: if aligned source energy is not greater than remint energy, set `g = 1`; never attenuate remint detail in this recovery round.
- Preserve sign exactly and do not use source sample values in the output coefficient.
- Cap `g ≤ 1.10` and post-transfer local band energy to both `1.21 × E_remint` and `E_source`.
- Make the confidence field edge-aware and spatially smooth, then re-zero it inside the strong-edge exclusion so smoothing cannot leak transfer across the boundary.

The `g ≤ 1.10` amplitude cap and `1.21 ×` energy cap are **model estimates**. They give alpha 0.10 an unambiguous maximum-dose interpretation. Without a gain cap, alpha 0.10 can still produce a large relative change when source energy greatly exceeds remint energy.

### Mandatory amendment: strengthen support construction

The following thresholds are **model estimates**. I recommend retaining the brief's conservative starting values unless fixture evidence fails them:

- Adjacent-scale displacement agreement ≤0.25 O2 px.
- Residual displacement ≤0.50 target-band px.
- Orientation difference ≤15 degrees, using axial orientation with polarity checked separately.
- Signed local NCC ≥0.80.
- Local usable-band SNR ≥4 relative to the estimated flat-region noise energy; below this, support is off.
- Strong-edge exclusion formed from the union of remint and aligned-source multiscale edges, not either image alone.
- Exclusion dilation `max(2 O2 px, 2 × effective PSF support)`, with “effective PSF support” numerically defined and frozen.

The SNR floor is required because signed NCC, orientation, and energy ratios become unstable in near-flat regions. The union edge mask is required because a source-only seam or a remint-only seam is precisely where coefficient transfer is unsafe.

The confidence-margin mapping into `w`, energy window/kernel, epsilon, border mode, luma transfer function, Gaussian implementation, R2 resampler, and strong-edge threshold must all be frozen in the brief or a referenced immutable specification. They are currently part of the experimental variable but are not fully identified.

### Required fixture additions

In addition to the listed reject fixtures, add proof that:

- Flat and near-flat inputs are unchanged.
- Source energy below remint energy is a no-op.
- Equal-energy/different-phase source content cannot change remint coefficients.
- A slanted edge retains its zero crossing and does not gain a source-side shoulder.
- Confidence-mask boundaries introduce no new extrema.
- Alpha zero, flag false, and flag absent are each byte-identical to incumbent.
- NaN, clipping, image borders, and zero-energy denominators fail safely.

These are proof requirements, not new pass/fail quality presets.

## 2. Carrier-safety posture

### Finding

H0 exclusion, luma-only operation, no source pixels, and no source phase are the best conservative posture available for this experiment. They do **not** establish carrier safety.

**Evidence:** The supplied wash evidence establishes content-dependent fingerprint swaps and that carrier break is mandatory. It does not identify the carrier's frequency band, color channel, or spatial statistic.

**Model estimate:** A spatial H1/H2 energy envelope may itself contain source-correlated detector features even when phase is not copied. The risk should be smaller than direct residual or pixel transfer, but its magnitude cannot be verified from the current evidence.

### Required pre-vendor screen

Amend MOCK gate 7 to test not only final eligibility axes but also carrier drift:

- 16/16 C O5 cells must meet the fixed mission thresholds.
- No C detector component may worsen by more than +0.02 versus paired B.
- Zero new source-family/fingerprint-family threshold crossings are allowed relative to B.
- Report the complete B→C detector vector and any family-label change; do not report only the three aggregate eligibility values.

The +0.02 margin is a **model estimate**. The mission thresholds are fixed product requirements, not model estimates. “Zero new family-threshold crossings” is the recommended count; the family alert thresholds themselves must be the already-frozen MOCK definitions. If none exist, they must be defined from prior calibration before first light, not from 4D-1a results.

This can be implemented as part of the planned MOCK evaluation and does not require a new wash configuration or a vendor call. A MOCK pass still authorizes only the real-vendor leg.

Before screening begins, freeze the six vendor-leg sentinel identities, Vendor 2, API/model versions, score-field mapping, retry/error policy, and exact rule for combining the two vendors. Leaving Vendor 2 owner-pending creates post-result selection freedom on the lexicographically primary outcome.

## 3. O2→O5 and edge-gate audit

### O2→O5 primary gate

The correction from O1→O2 to O2→O5 is mandatory and correct: a transfer applied after the frozen O2 capture cannot alter O1→O2.

The gate should be named **pre-transfer O2→O5 composite recovery**, because it measures transfer plus tone lock, Quality Finish, sharpen, and encode. It does not measure the finisher alone. Report `O2_transfer→O5` separately as a diagnostic so the team can see how much transferred energy survives the adaptive finisher.

The relative reduction formula must be frozen as:

`1 − mean(L_C) / mean(L_B) ≥ 0.25`

where each `L` is the existing combined transition-loss scalar from the common pre-transfer O2 reference to its paired O5. Do not use the mean of per-pair percentage reductions; zero and near-zero B losses make that statistic unstable.

The 25% threshold and the hard-subset factor 0.75 are **model estimates** for O2→O5 because the supplied measurements do not state the incumbent O2→O5 mean. Before candidate first light, publish the B-arm all-image and hard-subset means from already-existing incumbent outputs. If either mean is below 0.02, the relative gate is ill-conditioned; 0.02 is a **model-estimate denominator floor**. In that event, replace the relative gate before first light with a frozen absolute-loss reduction, rather than interpreting a small denominator after results arrive.

The O5 EATR +0.04, texture HFTR_H1 +8%, protected 0.98×, smooth +5%, rho +0.03, and sentinel 5/6 values are established program carry-over gates. Their fitness for source-energy transfer is not independently demonstrated by the edge audit, but retaining them preserves decision continuity.

### ESF gate

The brief's switch to matched-edge ESF is accepted with four amendments:

1. **Compare the correct checkpoint.** Standard B and C O2 must remain hash-identical for provenance. Geometry impact must be measured as C `O2_transfer` versus paired B O2. Comparing standard O2 to standard O2 would always return zero.
2. **Use common edge support.** Discover and freeze edge coordinates from the common pre-transfer O2 or the source reference, then evaluate those exact profiles in B, C `O2_transfer`, B O5, C O5, R2, and R5. Do not independently select the strongest edges in each arm.
3. **Use source-relative width error.** Gate the change in absolute distance to R2/R5, not raw C−B width alone. A small C widening that moves an unnaturally narrow B edge toward source should not be treated as damage.
4. **Restore out-of-transition energy.** The edge report says this gate is retained, but §5.1 gate 6 omits it.

Recommended ESF gate wording (**all numeric tolerances below are model estimates**):

- At `O2_transfer`, median source-relative monotonic-width-gap worsening ≤+0.25 px and no pair-level median worsening >+0.50 px versus B O2/R2.
- At O5, median source-relative monotonic-width-gap worsening ≤+0.25 px and no pair-level median worsening >+0.50 px versus B O5/R5.
- Median overshoot rise ≤+0.02 at each stage; no pair-level median rise >+0.03.
- Median out-of-transition excess-energy rise ≤2% relative at each stage; no pair >5% relative.
- In protected ROIs, zero candidate-created second signed peaks above 10% of the main response.
- Globally, candidate-created second-peak incidence may rise by no more than 0.25 percentage points overall and 1.0 percentage point in any pair.

An absolute rule forbidding any sampled second peak above 10% is not valid here because the edge audit already found approximately 6–7 crossing candidates and nonzero overshoot in both incumbent and candidate O2. The gate must detect **new or amplified candidate behavior**, not inherited B behavior. The global incidence tolerances are **model estimates** that avoid letting one noisy profile among thousands decide the round while keeping protected product edges fail-closed.

Every “median” and “pair” in the gate must be explicit: first compute matched-edge C−B or source-gap differences within each image/seed pair, then compute the round statistic across the 16 pair-level medians. Report edge counts and invalid-profile exclusions per pair.

`edge_width_10_90` should remain report-only and must not enter any composite pass/fail statistic.

## 4. Determinism and replay-proof audit

The build-time proof plan is strong but incomplete.

### Mandatory clarifications

- Replace “invalid/absent-without-seed cases fail closed” with: **`4d1a: true` with an absent or invalid lab seed fails closed; `4d1a` absent or false preserves ordinary incumbent behavior.** The current wording conflicts with the default-absent and non-lab guarantees.
- Freeze candidate alpha to exactly 0.10 requested. Local `w` and energy/gain caps may reduce effective execution, but the request value cannot vary by cell. Otherwise the preset represents a family of doses rather than one sealed arm.
- Hash and report the exact pre-transfer in-memory O2 buffer and exact resampled R2 buffer used by transfer, in addition to the encoded checkpoints.
- Require equality of every pre-transfer checkpoint and input—not only “OR” and O2. Define “OR”; explicitly include O0, O1, standard O2, source object hash, seed, and all incumbent parameters.
- Freeze R2 resize kernel, color/gamma domain, EXIF/orientation handling, boundary mode, Gaussian kernel construction, float precision, interpolation convention, threading/device, and NCC tie-breaking.
- State whether the determinism hash is same-machine only or cross-machine. “No RNG” is insufficient for block matching, reductions, interpolation, and floating-point libraries.
- Make report serialization deterministic: stable key order, fixed numeric formatting, no timestamps, and truthful reject counts derived from the buffer whose hash is reported.
- Prove that adding the auxiliary checkpoint cannot alter main-checkpoint ordering, main-manifest contents, memory lifetime, or O5 pixels.

### Recommended replay thresholds

**Model estimate:** Require same-build/same-machine reruns to be byte-identical for O2 input, R2, `O2_transfer`, O5, and the deterministic report block. Cross-machine runs should either be byte-identical under a pinned CPU implementation or be declared non-authoritative for hash comparison. Do not silently accept the prior four-LSB tolerance for a new transfer whose expected median benefit may be small; first measure an identical-config cross-machine noise floor.

Build proof should test both `4d1a` absent and explicit `false`, each with lab and non-lab seeds where valid. Unknown keys, non-boolean values, true-without-seed, and unrecognized seed/code combinations must fail according to the frozen boundary contract.

## 5. Threshold classification

| Threshold | Audit classification | Recommendation |
|---|---|---|
| α ceiling 0.10 | **Model estimate** for this transfer | Freeze requested α=0.10 and add amplitude gain ≤1.10 / energy gain ≤1.21× |
| Alignment 0.25/0.50 px, orientation 15°, NCC 0.80 | **Model estimates** | Retain; add SNR ≥4 and union source/remint edge mask |
| Edge dilation max(2 px, 2× PSF support) | **Model estimate** | Retain after PSF support is numerically defined |
| O2→O5 reduction 25%; hard subset 0.75× | **Model estimates** on the new transition | Retain only after incumbent means and denominator floor are frozen |
| O5 EATR 0.04, HFTR_H1 8%, sentinel 5/6 | Existing program gates | Retain for continuity; report seed-level counts |
| Protected 0.98×, smooth 5%, rho 0.03 | Existing program gates | Retain unchanged |
| ESF +0.25/+0.50 px, overshoot +0.02 | **Model estimates** | Use source-relative pair-level wording; add overshoot pair cap +0.03 |
| Second peak 10% | **Model estimate** | Zero new protected peaks; gate global incidence rather than inherited absolute presence |
| Excess edge energy 2% median / 5% pair | **Model estimates** | Restore at both `O2_transfer` and O5 |
| MOCK ai 0.45, flux 0.30, deepfake 0.10 | Fixed product eligibility screen | Retain 16/16 C requirement |
| MOCK paired worsening +0.02 | **Model estimate** | Retain and add zero new family-threshold crossings |

## Section-by-section disposition

- **§0 Mission — ACCEPT WITH WORDING AMENDMENT:** The round compensates for W1 at delivery; it does not reduce the already-captured O1→O2 loss itself.
- **§1 Edge findings — ACCEPT WITH ATTRIBUTION CAUTION:** O2 camera geometry is cleared. The composite O2→O5 stage is implicated; adaptive sharpen alone is not isolated.
- **§2 Design — AMEND:** Replace coefficient interpolation with one-sided remint-coefficient energy scaling; define dose, masks, energy estimator, and deterministic primitives.
- **§3 Identity — AMEND:** Freeze α requested at 0.10 and include all algorithm constants under the one candidate identity.
- **§4 Build proof — AMEND:** Resolve flag semantics, add phase/no-op/boundary fixtures, hash in-memory O2/R2 inputs, and pin floating-point execution.
- **§5 Screening — AMEND:** Freeze reduction arithmetic and denominator, compare `O2_transfer` rather than standard O2, restore excess-energy gating, make second-peak checks candidate-relative, and freeze the vendor leg before first light.
- **§6 Forbidden actions — ACCEPT:** Keeping camera, finisher, wash, lattice, ROIs, and frozen tools unchanged preserves the intended one-variable experiment.

## Final recommendation

Do not commission the brief verbatim. Incorporate the mandatory amendments, then commission the 32-cell MOCK build exactly as bounded. The strongest parts are the post-O2 placement, standard-O2 identity proof, H0 exclusion, frozen incumbent, and zero-vendor screen. The decisive correction is to make “source supplies energy only” true in the mathematics and to measure the actual post-transfer checkpoint rather than a pre-transfer O2 file that is guaranteed to match.

If the amended seven gates all pass, the result authorizes the frozen 24-call real-vendor leg only. It does not establish product adoption.
