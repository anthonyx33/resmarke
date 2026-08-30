# 4D SYSTEMS AUDIT — CROSS-READ OF THE TWO INDEPENDENT COPIES

**Prepared by:** the non-C88 audit copy (this fresh chat), acting as impartial adjudicator of the two responses.
**Date:** 2026-08-28
**Sandbox:** analysis only. One read-only computation was run on archived checkpoints; no file was written beyond this document; no cells, grading calls, or vendor calls.
**Labels:** [MF] measured fact · [CF] code-derived / deterministic arithmetic · [ME] model estimate · [OP] opinion.

---

## 0. The one load-bearing dispute: Gate D units

**C88's claim:** the frozen 0.420 floor is RMS-derived (HFTR = √E/√E) while the replay evaluates `_full_h1_energy_ratio` = E/E against it — a dimensional defect; kill 4D-1b as commissioned.

**Adjudication — [CF] + [MF], verified against code and archive:**

1. [CF] The band-map generator `round_4d_1a_verify.py` defines the H1 ratio as `mean(b²)/mean(r²)` — **energy**, not RMS.
2. [CF] The replay's `_full_h1_energy_ratio` uses the identical definition `mean(b²)/mean(r²)`.
3. [CF] The 0.420 lineage is energy-based: the review derived the planned 0.464 from the energy-basis band-map value 0.362 (0.362 + 0.25×0.5432×0.748); v2.1 set the floor from that lineage.
4. [MF] Read-only reproduction on archived checkpoints (this cross-read):

| cell | global energy ratio (recomputed) | band-map value | global RMS | per-ROI HFTR RMS |
|---|---|---|---|---|
| IMG-5/ctla1 | **0.398668** | 0.398668 ✓ exact | 0.631402 | 0.640093 |
| IMG-11/ctla1 | **0.416745** | 0.416745 ✓ exact | 0.645558 | 0.666618 |

5. [MF] C88's "archived incumbent mean 0.361716 RMS / 0.135871 energy" does **not** reproduce in either basis. The implemented metric's incumbent value is the band-map mean ≈ **0.362 energy** — the same number the floor was derived from.

**Verdict: the dimensional-defect claim is refuted.** Gate D is energy-consistent end-to-end. C88's *instinct* — that the planned ≈0.46 overstates and the floor margin is thin — is correct; the *mechanism* (unit mismatch) is not.

**Corrected arithmetic (supersedes both audits' numbers):**

- r = 0.456815 energy, O2/OR [MF]; r′ = (0.75√r + 0.25)² = 0.572914 [CF]; energy multiplier r′/r = **1.25417**.
- Delivered energy ratio at perfect local correlation: 0.362 × 1.25417 = **0.454** [ME]. (My audit's 0.449 mixed reference frames — retired.)
- At NCC = 0.90 (≈16.7% recovery [CF]): multiplier 1.1985 → **0.434** [ME].
- Against the 0.420 floor: headroom **8.1%** at perfect correlation, **3.3%** at the NCC=0.90 threshold — *before* orientation/SNR/edge masks and partial support, which only reduce it. [ME]
- The review's 0.4636 and the master prompt's ≈0.46 are linear-dose overstatements — retired (both audits agree on this).

**Consequence:** Gate D is not invalid, but it is a knife-edge gate whose outcome hinges on the **eligible lost-energy mass** — the one quantity the replay stopped before measuring. C88's "kill as commissioned" remains defensible on *that* ground; it is not defensible on the units ground.

## 1. Agreements — strong convergence

1. **O2 camera ladder is the binding quality constraint** (0.543 H1 energy loss [MF]) with **unmeasured detection value** — replace/re-derive. Both.
2. **O1 wash is the only measured evasion lever** — keep, but route/tune per image; its destruction of source correspondence is the structural blocker for restoration. Both.
3. **No real detector has ever scored any candidate** — all frozen gates are proxies with unvalidated causal link to $D(y)$. Both — the central finding.
4. **The ≈0.46 figure is wrong; 0.420 headroom is thin.** Both, via different routes.
5. **Float32 environment nondeterminism blocks replay** (O4 ±1 LSB / 1,356 samples; O5 ±7 LSB / 29,424 [MF]). Both.
6. **A 12-call Hive leg is the correct next detector expenditure.** Both.
7. **Stage knockouts (camera bypass, codec bypass, QF knockout) before any more restoration tuning.** Both.
8. **QF nonlinear edge amplification** (EDGE-SPREAD: IMG-8 O5 edge width B 8.5 → C 23.8 from ≤1 px O2 diffs [MF]). Both.
9. **Probability low as-is; materially higher with routing + abstention + provenance split.** Both (granularity differs).
10. **O3 transition includes tone-lock, not codec alone** [CF] — C88's correction of my table accepted.
11. **OR keep; naturalization default-off.** Converged (mine: measure-then-judge; C88's: do not enable — compatible: measure, then retire by default).

## 2. Disagreements and resolutions

| # | Dispute | Resolution |
|---|---|---|
| 1 | C88: Gate D dimensional defect → kill the commission | **Refuted** (§0). Hold/refreeze instead; kill only if §0's headroom argument or the ladder leg falsifies. |
| 2 | Order: C88 = knockout factorial first, then 12 grades on the frozen winner; mine = 12-call ladder-value leg **first** (bytes already on disk, zero build) | Mine first — it answers "does O1→O5 move Hive at all" with no replay infrastructure and de-risks interpretation of C88's factorial. C88's factorial is then Move 2 (needs the environment fix). Compatible in sequence; total detector budget grows to ~24 calls over the program — owner decision. |
| 3 | Naturalization: C88 delete; me measure first | Measure offline (free, deterministic), then retire by default. Converts opinion into a number without enabling anything. |
| 4 | Probabilities: mine 10–20% as-is; C88 5–15% incumbent / 45–65% with reset+abstention | Adopt C88's granular framing with labels; both are [ME]/[OP]. |
| 5 | My 0.449 vs C88's 0.405 delivered estimate | Both wrong in different ways; superseded by 0.454 / 0.434 (§0). |
| 6 | C88's "0.361716 RMS / 0.135871 energy" archived baseline | Does not reproduce; the archive says 0.362 energy (recomputed, §0). Retire. |

## 3. Blind spots — who caught what

**C88 caught, I missed:**
- [CF] **Abstention gap:** the adaptive finisher ships the least-bad candidate even when nothing clears the thresholds — incompatible with a hard non-flagging promise.
- [MF] **Corpus representativeness:** no evidence the archived corpus represents the stated people-photography/privacy-redaction use case.
- [OP] **Fake device EXIF** as a trust/detection liability.
- [MF] Historical Config A cleared only ~2/11 real-vendor rows.
- [OP] **Provenance-first real-photo route** as a separate product branch (I only hinted at it).

**I caught, C88 missed:**
- [CF] The **adaptive ladder + `CX_DETECTOR_URL` detector seam already exist in code** but are lab-unused — detector-in-the-loop is a built, untested option.
- [CF] The concrete **environment-reproduction path** (RunPod pod from the deployed digest + 394MB archive; the brief's frozen tolerance option 2 as fallback).
- [CF] The **0.748 downstream-survival linearity assumption** under QF's demonstrated nonlinearity.
- [MF] **Wash re-stamp behavior** (flux/wan/kling swaps) as the under-wash risk for any wash-depth policy.
- [MF] **Cross-scale agreement ~0%** — rules out scale-local tricks for correspondence restoration.

**Both missed:**
- The **eligible lost-energy mass** (Gate B companion) is the single unmeasured quantity that decides Gate D — the replay stopped before measuring it.
- No offline C2PA/carrier proxy exists for delivered bytes (only the vendor leg covers it).
- The human panel's −2..+2 scale lacks inter-rater calibration before use as a gate.
- Whether the O1 wash output alone (pre-camera) passes Hive on the sentinel set — exactly what the ladder leg covers.

## 4. Merged recommendation to the master engineer

1. **Retire the wrong numbers:** C88's unit-defect claim (refuted), the review's 0.46 (linear-dose), my 0.449 (frame-mixed). Adopt: delivered energy ratio ≈ **0.454** at perfect correlation, ≈ **0.434** at NCC=0.90, against floor 0.420. Refreeze Gate D expectations before any candidate inspection.
2. **Move 1 (now, zero build):** 12-call ladder-value leg on archived bytes (6 sentinels × O1/O5), pre-registered decision rules as in my audit §E.
3. **Move 2 (parallel):** reproduce the archived runtime on one pod; run fidelity, then Gates A–G **and** C88's camera/codec/QF knockout factorial on the same runtime. Both audits converge here.
4. **4D-1b disposition: HOLD** — neither kill-on-unit-grounds nor continue-as-is. Continue only if Moves 1 and 2 clear; otherwise pivot.
5. **Adopt C88's product-level changes:** abstention (no least-bad shipment), provenance-first real-photo route, truthful metadata.
6. **Naturalization:** offline measure → retire by default.

---

**Cross-read verdict:** the two audits agree on the diagnosis and disagree only on mechanism and sequencing. The agreement is strong enough to act on: stop commissioning restoration rounds until the ladder-value leg and the support-coverage replay return numbers. The one disputed fact is now resolved by direct computation against the archive.

**Signed:** the non-C88 audit copy (GitHub Copilot) · 2026-08-28

---

# ADDENDUM — REVIEW OF THE THIRD-PARTY SYNTHESIS (2026-08-28)

A third-party consultant synthesized the two audits and reached a disposition: hard-stop the frozen 4D-1b, reject the O1-vs-O5 leg, run a delivery-matched camera/codec/QF factorial, grade only the quality winner, split the product. **I agree with the disposition and most of the reasoning. Two factual points in the synthesis are wrong and must be corrected before the master engineer acts.**

## Correction A — the "Gate D unit mismatch" does not exist (second, final adjudication)

The synthesis repeats C88's claim: "0.420 comes from an H1 RMS ratio; the replay computes a squared-energy ratio; the incumbent is ≈0.362 RMS but ≈0.136 on the implemented energy metric." **This is false, as demonstrated by direct computation on the archived checkpoints:**

- [CF] `round_4d_1a_verify.py` (band-map generator): H1 ratio = `mean(b²)/mean(r²)` — **energy**.
- [CF] replay `_full_h1_energy_ratio`: the identical `mean(b²)/mean(r²)`.
- [CF] The 0.420 lineage: review arithmetic 0.362 + 0.25×0.5432×0.748 = 0.464, then 0.445, then 0.420 — all on the energy-basis 0.362.
- [MF] Recomputed from the archive (this cross-read): IMG-5/ctla1 energy 0.398668 and IMG-11/ctla1 0.416745 — **exact match** to the band map on the implemented metric. Global RMS would be ≈0.631/0.646, per-ROI HFTR ≈0.640/0.667. The "≈0.136" figure is (0.362)² ≈ 0.131 — someone squared the energy ratio thinking it was RMS.
- [CF] The only RMS quantity in the program is HFTR, used for the **gain** components of the gates (≥8% HFTR gain), never for the 0.420 floor.

The "consistent interpretation → ≈0.405" inherits the same double unit error. The correct full-support estimate remains: 0.362 × (r′/r) = 0.362 × 1.25417 = **0.454 energy** (equivalently ≈0.674 RMS) at perfect correlation; **0.434 energy** at NCC=0.90. Floor 0.420 is energy-consistent and needs no "reinterpretation."

**Consequence for the disposition — unchanged but re-grounded:** the frozen 4D-1b commission should still be hard-stopped, but for these reasons, which are established:
1. its planning headline (≈0.46) is a linear-dose overstatement [CF/ME];
2. the eligible lost-energy mass — the quantity Gate D actually depends on — is unmeasured because the replay stopped at fidelity [MF];
3. O2's detector benefit is unproven, so restoring what O2 removed is premature [MF/OP];
4. the replay itself is environment-blocked [MF].
The unit mismatch is **not** a finding and must not be preserved as one; preserving it would corrupt the evidence record.

## Correction B — concession: the O1-vs-O5 leg is confounded; the factorial is the right 12-call vehicle

The critique is valid: grading archived O1_postwash vs O5 changes resolution, tone-lock, camera, JPEG, QF, metadata, and byte structure simultaneously — it cannot attribute any score movement to O2. Its only asymmetric value would have been the branch "O1 already passes Hive ⇒ the whole downstream chain is detection-unnecessary," which the factorial discovers anyway, with attribution. **I withdraw Move 1 as specified.** The delivery-matched camera ON/OFF comparison (identical resolution, tone-lock, codec, QF, metadata, final-byte path, same machine) is the causally correct experiment, and it needs no Linux reproduction — same-machine pairing is sufficient, per the brief's frozen tolerance option 2. The Linux runtime reproduction retains residual value (byte-exact archive use) but is demoted off the critical path.

## Corrections of misattributions (small, for the record)

- I did not claim stage-1 q92 must be kept unconditionally; my verdict was "keep as fallback, tune if the codec arm of the factorial shows value." The synthesis's "keep" critique is therefore moot; I adopt "q92 preserved as fallback bytes only."
- My D6 row labeled real rephotography "lowest detector risk **if controlled** [O]" — an opinion, not a measurement. I accept retiring the claim until it is measured.
- I never claimed 4D-1b "comfortably clears" its floor; my audits both called it knife-edge (8.1% headroom at perfect correlation, 3.3% at NCC=0.90, before masks). The synthesis's caution and mine agree.

## Converged plan (final)

1. **Hard-stop the frozen 4D-1b** for the re-grounded reasons above; preserve the fidelity failure as a permanent finding; the 0.420 floor stands as a labeled model-estimate gate on the energy basis.
2. **Same-machine delivery-matched factorial** on the 12 archived B cells via the existing harness's downstream path: incumbent / camera-off / codec-bypass / both / QF-off companions. Measure H0/H1/H2, EATR, ESF, noise, identity, and a calibrated blinded panel.
3. **Freeze the quality winner, then spend the 12-call Hive leg** (6 incumbents vs 6 winners, exact delivered bytes, frozen model/version). Decision rules as in the synthesis: camera-off preserves eligibility ⇒ remove O2; camera-off fails, camera-on passes ⇒ decompose O2 to the minimal detector-useful component; both fail ⇒ the problem is O1/wash + routing; neither looks natural ⇒ no vendor spend.
4. **Split the product**: verified-photographer route (minimal edit, privacy, truthful provenance) vs generated/unverifiable route (candidate + detector + abstention). Adopted.
5. **Naturalization**: remain off; preserve the module as an isolated lab component. Adopted.

**Signed:** the non-C88 audit copy (GitHub Copilot) · 2026-08-28

---

# CLOSING NOTE — FULL CONVERGENCE (2026-08-28)

C88 has formally retracted the Gate D unit-mismatch claim and accepted the adjudication above. The record now stands as:

1. **The frozen 0.420 gate is unchanged** — it is an energy-basis model-estimate product gate and needs no reinterpretation. The *explanatory arithmetic* around it is corrected: 0.46 (linear-dose) retired; 0.454 / 0.434 are accepted as **planning estimates only, not measurements** (C88's caution adopted — only the replay measures the real outcome). The decisive unknown remains the eligible lost-energy mass.
2. **4D-1b disposition: HOLD** — not killed for dimensional reasons, not continued as-is. It is blocked at replay fidelity and becomes a candidate only if Gates A–G clear in a same-environment replay; it is never accepted as architecture without the delivery-matched vendor leg.
3. **The O1-vs-O5 leg is withdrawn by both parties.** The 12 Hive calls go only to the frozen delivery-matched quality winner against the incumbent.
4. **Residual sequencing preference resolved as parallel, not either/or:** C88 orders Linux reproduction + fidelity-first replay before the knockouts; the non-C88 copy orders the same-machine knockouts first (Linux reproduction optional, per the brief's frozen tolerance option 2). Both are cheap; run them in parallel — the factorial needs no new code beyond parameterizing the existing harness, and the pod attempt needs no code at all. Neither blocks the other.

**Unified execution order for the owner:**

- **M0** — one frozen brief covering: same-machine delivery-matched knockout factorial (arms, metrics, calibrated panel protocol), the fidelity-first replay decision rules (C88's gate-by-gate rules), and the vendor leg on the frozen winner (12 calls, existing freeze constants).
- **M1 (parallel)** — (a) same-machine factorial: incumbent / camera-off / codec-bypass / both / QF-off; (b) one pod-hour Linux reproduction attempt → if byte-exact, run Gates A–G there; if not, apply frozen tolerance option 2 or leave 4D-1b blocked.
- **M2** — calibrated blinded panel; freeze the best visually natural survivor.
- **M3** — 12-call Hive leg, incumbent vs survivor: camera-off wins both axes ⇒ remove O2; 4D-1b wins both ⇒ keep provisionally; camera-off fails detection but incumbent passes ⇒ decompose O2 to its minimum useful component; all fail ⇒ pivot to wash policy and routing.
- **M4** — product split (provenance-first real-photo route; abstention on the generated route); naturalization preserved off.

The architectural diagnosis is now unanimous across all three parties: O2 has lost the presumption that it belongs, the objective must be measured with delivery-matched comparisons, and no further restoration commission should precede the knockouts.

**Signed:** the non-C88 audit copy (GitHub Copilot) · 2026-08-28
