# C8 Final-Pass Audit — 4D-1a Build Brief v3

Date: 2026-08-27  
Audited inputs: `C8_MASTER_PROMPT_4D_1A_BUILD_BRIEF_V3.md`, `C8_4D_1A_BRIEF_AUDIT_V2_REVIEW.md`, `round-4d-cam-1/incumbent-o2-o5-baseline-v3.json`, and the referenced frozen `_gauss` / `_edge_mag` recipes  
Scope: Audit only; no build, grading, deployment, vendor call, or operational action

## Verdict

**AMEND — final mechanical redline required; architecture and round design accepted.**

V3 closes both population blockers and nearly all remaining specification gaps. I accept the 24-cell sentinel-only design, the denominator evidence, the remint-only energy architecture, the source-relative ESF policy, MOCK fail-closed policy, determinism posture, and vendor-freeze rule.

One safety defect remains: smoothing `w_raw` can leak positive transfer weight into pixels where alignment, orientation, NCC, SNR, or cross-scale support failed, because v3 re-zeroes only the strong-edge exclusion. Several smaller primitive definitions also remain open or contradictory. These can be fixed in a short authoritative erratum without reopening the experiment.

The round remains blocked until both the erratum and the owner's Vendor 2 freeze are recorded.

## 1. Population and denominator verification

### Disposition: ACCEPT

The new population is internally consistent:

- six sentinels × two seeds = 12 B/C pairs = 24 cells;
- the hard subset is eight of those 12 pairs;
- all six sentinel image means and all 12 seed-level directions are measurable from the screening round; and
- the later 24-call B/C vendor leg uses the same six named images.

The evidence file verifies as follows:

- SHA-256: `90be734b4c6a45b5077e8691a31e44ea26083a422cb9ab5fecf7c26ff1c2be9c` — matches v3.
- 12 unique image/seed cells, 12 unique B job ids, 12 unique O2 hashes, and 12 unique O5 hashes.
- Every row's `loss` equals `max(|min(dEATR,0)|, |min(dHFTR_H1,0)|)`.
- Exact 12-cell mean: `0.098216666666667`, correctly frozen to six decimals as `0.098217`.
- Exact hard-subset mean: `0.106025`.
- Exact G3 threshold: `0.75 × 0.106025 = 0.07951875`.

For absolute gate clarity, add the derived G2 operational form `mean(L_C) ≤ 0.07366275`, using the frozen six-decimal denominator. This is arithmetic derived from the existing 25% gate, not a model-estimate threshold.

The budget arithmetic is correct: 24 × 23 = 552 privacy credits, plus 24 deepclean operations and zero screening vendor calls.

## 2. Confidence-field safety

### Disposition: AMEND — blocking

V3 defines `w_raw=0` wherever any support gate fails, then applies Gaussian smoothing and re-zeroes only inside the edge exclusion. Gaussian smoothing spreads nearby positive values into zero-valued pixels. A pixel that failed displacement, orientation, NCC, SNR, or cross-scale persistence can therefore receive nonzero final `w`, contradicting the rule that all support gates must pass per position.

Freeze the final expression as:

`w = clip(gauss_σ3(w_raw), 0, 1) × support_binary`

where `support_binary` is one only where **all** five numeric gates, cross-scale persistence, and outside-edge-exclusion conditions pass. This re-applies the complete support mask after smoothing, not only the edge mask.

No new threshold is introduced. Sigma 3 remains the already-declared **model-estimate threshold**. This correction is required to make the implemented support match the frozen safety claim.

## 3. Primitive completeness

### Disposition: AMEND — narrow definitions

### 3.1 Edge recipe contradiction

V3 calls `_edge_mag` “Sobel magnitude.” The referenced frozen implementation is:

`gy, gx = np.gradient(y); hypot(gx, gy)`

It is not a Sobel operator. Freeze the strong-edge recipe as the exact referenced `np.gradient` magnitude at p92 and remove “Sobel.” Otherwise two faithful builders could produce different exclusion masks.

### 3.2 Pyramid alignment

The brief specifies the finest block but not the block/stride convention at coarser levels, how coarse displacement initializes the next level, or the exact quadratic refinement.

Recommended freeze (**model estimate**):

- use 32×32 blocks and stride 16 in each level's own pixels;
- multiply the accepted coarse displacement by two to initialize the next-finer search center;
- search the stated ±8 residual around that center;
- fit independent one-dimensional parabolas through the peak and its immediate ±1 x/y neighbors;
- clamp each subpixel offset to ±0.5 px; use zero subpixel offset at a boundary peak or non-concave/degenerate fit.

Also state explicitly that alignment is computed between remint O2 luma and R2 luma, and that the resulting field warps source H1/H2 bands into remint geometry.

These choices cannot be verified from existing measurements and are therefore **model estimates**.

### 3.3 Noise-energy definition

“MAD of the H2 band” is an amplitude statistic, while the gate compares band energy. Freeze the conversion and tile statistic.

Recommended freeze (**model estimate**): select the lowest-20% tiles by mean squared `_edge_mag`; concatenate their H2 samples; compute `noise_energy = max((1.4826 × MAD)^2, 1e-6)`. Define MAD about the selected-sample median. Then `SNR = local_band_energy / noise_energy`.

The SNR threshold 4, 20% tile selection, 32×32 tiles, Gaussian-noise conversion, and `1e-6` floor are **model estimates**.

### 3.4 Luma synthesis and clipping

Adding one scalar delta to RGB preserves RGB channel differences only before independent channel clipping. V3's claim that chroma/hue remain unchanged is not guaranteed when one channel reaches 0 or 1.

Recommended freeze: cap the scalar luma delta to the common feasible interval before addition:

`delta_safe = clip(delta, -min(R,G,B), 1-max(R,G,B))`

then `out_RGB = RGB + delta_safe`, followed only by uint8 rounding. This preserves channel differences even in highlights/shadows. Report the fraction of pixels where the scalar delta was capped. The choice to require exact channel-difference preservation is a **model estimate**; if ordinary per-channel clipping is retained instead, v3 must withdraw the unconditional chroma/hue-preservation claim and report new per-channel clipping counts.

### 3.5 Energy-cap enforcement

After applying the window-derived correction, clamp corrected gain back to `[1.0, 1.10]` so cap enforcement cannot violate the one-sided no-attenuation invariant. Recompute final window energies and fail closed if any valid grid window exceeds `min(1.21×E_remint, E_source)` beyond a frozen relative numerical tolerance.

Recommended tolerance: `1e-9` relative in float64 — a **model-estimate threshold**. A final verification is necessary because bilinear upsampling of overlapping window corrections does not by itself prove every recomputed window satisfies the cap.

### 3.6 Authoritative specification

V3 says everything not restated from v2 still stands. For commissioning, either issue a consolidated brief or state an explicit precedence rule: v3 overrides v2 on conflict, with a closed list of incorporated v2 sections. A single consolidated brief is preferred so builders and graders do not resolve layered-text conflicts differently.

## 4. Gate 6 discretion audit

### Disposition: ACCEPT WITH TWO CLARIFICATIONS

The source-gap formula, common frozen support, pair/round aggregation, minimum edge counts, excess-energy floor, candidate-created peak matching, incumbent-peak amplification rule, and evaluator hash close the substantive loopholes identified in v2.

Add two exact statements:

1. Excess-energy relative change is `(C_excess − B_excess) / max(B_excess, 0.01)` per matched edge before pair medians.
2. A protected ROI with fewer than 20 valid matched edges fails gate 6 even if another protected ROI for that image has sufficient edges; no protected box may be silently omitted.

The existing 0.01 floor, ±0.5-px matching tolerance, 10% peak level, +0.02 incumbent-peak allowance, 100/20 counts, and 2%/5% tolerances remain **model-estimate thresholds** as already declared.

The pinned evaluator must record its hash, edge-support artifact hash, valid/invalid counts, and exclusion reason histogram in the round ledger before candidate inspection.

## 5. Gate 7 discretion audit

### Disposition: ACCEPT WITH ONE CLARIFICATION

Pinning the deployed evaluator identity, declaring every emitted component, and failing closed on missing/unclassified results is correct.

“Score precision before thresholding” currently has no value. Freeze it as the full numeric precision returned by the pinned evaluator, with no display rounding before either eligibility or paired-delta comparisons. Record the evaluator identity hash on every cell and require one unchanged identity across all 24 cells; an identity change aborts the round.

The +0.02 adverse-score margin is a **model-estimate threshold**. The three mission eligibility thresholds are fixed product requirements.

## 6. Determinism and reporting

### Disposition: ACCEPT AFTER THE PRIMITIVE ERRATUM

Same-machine hash identity, one-machine grading, cross-machine non-authority, post-O5 report assembly, in-memory input hashes, auxiliary isolation, and fail-closed fixtures form an adequate proof plan once §2–§3 are frozen.

Add fixtures for:

- no final `w` outside complete support after smoothing;
- exact `_edge_mag` recipe equivalence;
- gain never below 1 after cap enforcement;
- final energy-cap verification;
- channel-difference preservation or truthful clipping reporting, according to the selected synthesis rule.

No build-time noise result may relax a frozen screening threshold or same-machine hash requirement.

## 7. Vendor prerequisite

### Disposition: SPECIFICATION ACCEPTED; OWNER FREEZE STILL REQUIRED

V3 correctly removes the exception: screening cannot begin before Vendor 2 and all vendor-leg constants are frozen. I do not choose or contact Vendor 2 in this audit.

The owner must record TruthScan or Sightengine, both vendor model/API versions, score mappings, retry/error policy, sentinel list, combination rule, and per-vendor eligibility interpretation before the first screening result is viewed. This is an external prerequisite, not a defect in the v3 experiment design.

## Threshold classification

| Value | Classification |
|---|---|
| Mission ai 0.45 / flux 0.30 / deepfake 0.10 | Fixed product requirements |
| G2 25%, G3 0.75×, delivered-detail and safety carry-over gates | Existing program gates |
| G2 C ceiling 0.07366275 / G3 0.07951875 | Arithmetic consequences, not model estimates |
| Alignment 0.25/0.50 px, 15°, NCC 0.80, SNR 4 | Model estimates |
| Confidence smoothing σ3 and proposed margin mapping | Model estimates |
| Gain 1.10 / energy 1.21× / numerical tolerance 1e-9 | Model estimates |
| ESF 0.25/0.50 px, 2%/5%, 10%, +0.02, counts 100/20 | Model estimates |
| MOCK paired worsening +0.02 | Model estimate |

## Final disposition

- **Population and denominator:** ACCEPT.
- **Energy-only architecture:** ACCEPT.
- **Confidence implementation:** AMEND complete-support re-masking.
- **Primitive specification:** AMEND the edge recipe, alignment details, noise-energy units, synthesis/clipping claim, and final cap verification.
- **Gate 6:** ACCEPT after two declarative clarifications.
- **Gate 7:** ACCEPT after full-precision and single-evaluator-identity wording.
- **Determinism:** ACCEPT after corresponding fixtures.
- **Vendor rule:** ACCEPT; owner freeze remains mandatory.

After one short consolidated erratum closes these items, I recommend **ACCEPT FOR BUILD** without another architecture review. Commissioning and screening remain blocked until that erratum and the owner Vendor 2 freeze are both recorded.
