# C8 4D-1b Consultation Response

Date: 2026-08-27  
Role: expert consultant  
Scope: professional opinion and recommendations only

## Executive opinion

4D-1b is the right next direction, but I would narrow and rename the product
candidate: **loss-constrained H1 preservation from the geometry-matched
post-wash/pre-camera buffer (`OR_postresample`) across the camera stage**, not
a combined H0/H1 reinjection and not generic sharpening.

The master engineer's restore-only position is necessary but incomplete.
Restoring no more than the camera removed prevents invention and uncontrolled
oversharpening; it does **not** prove detection safety. O1 can contain a residual
source carrier, a wash-model carrier, or both. Passing only O1-derived detail to
O2 removes the specific risk of importing carrier content directly from O0, but
it can still strengthen a carrier already present in O1. The candidate therefore
requires two independent protections:

1. a structural limit on what pixels and bands may change; and
2. a paired detector non-amplification gate, followed by the fixed real-vendor
   eligibility gate.

I recommend keeping H0 out of the first product arm. H1 offers substantially
better delivery yield, while the detector risk of restoring fine, spatially
stationary microtexture has not been measured. A combined H0/H1 arm would also
make a detector movement impossible to attribute to one band.

No live screening cells should be commissioned until the frozen candidate has
demonstrated, by replay on the existing O1/OR/O2 checkpoints, that it activates,
survives O5, and reaches the full objective effect-size floor. That is the
process change most likely to prevent a third underpowered or no-op round.

## Evidence classification

Throughout this opinion:

- **MEASURED** means reproduced in the supplied 4D-CAM-1 or 4D-1a record, or
  directly calculated from its reported means.
- **FIXED PRODUCT REQUIREMENT** means supplied by the owner and is not my
  estimate.
- **MODEL ESTIMATE** means a proposed threshold that the present measurements
  do not validate as an optimal boundary. It should be frozen before candidate
  outputs or detector results are inspected.

## 1. Is 4D-1b the right next move?

Yes, with the H1-first qualification above.

The 12-cell X-ray gives a direct stage target. **MEASURED:** H1 falls from
0.938 at O1 to 0.484 at O2, an absolute loss of 0.454 and retention of 51.6%.
After O2, 0.362/0.484 = 74.8% of the remaining H1 reaches O5. By contrast,
**MEASURED:** H0 falls from 0.608 to 0.290 at the camera and only
0.126/0.290 = 43.4% of O2 H0 reaches delivery. Under a simple local-linear
planning assumption, a unit of H1 restored at O2 has about 1.72 times the
delivery yield of a unit of H0 restored there. That yield comparison is
calculated from the measurements; linear response of a new candidate is not
yet proven. The 0.454 is combined resample-plus-camera loss; it must not be
treated as the local restore-only allowance where O1 was resized.

The finisher is not the first lever. **MEASURED:** the H1 loss is 0.454 across
O1→O2, 0.074 across O2→O3, and 0.052 across O3→O4. The camera-stage H1 loss is
about 8.7 times the finisher's H1 loss. The earlier 32-job attribution also
identified O1→O2 as the largest mean transition loss and primary in 23/32
jobs. Retuning the finisher first would work on a much smaller budget of
recoverable detail.

Nor would I repeat a scalar PSF-radius reduction. **MEASURED:** 4D-CAM-1
reduced fixed-rung camera loss by only 5.7% against a 25% target, delivered a
0.0142 median EATR gain and 5.92% texture-H1 gain, and widened the median edge
gap by 8.3%. That result says the radius is a real but weak lever and that it is
coupled to the sharpen path.

4D-1b should therefore be understood as a selective bypass around the measured
loss, not as a second sharpening stage. It changes the camera step's net
destruction without disturbing the camera model globally. The synthesis
reference should be `OR_postresample`: the O1-derived, geometry-matched buffer
immediately before the camera ladder. The main arm should carry only its H1
structure that the incumbent camera demonstrably removed.

I challenge two statements in the preliminary rationale:

- Raw O1 and O2 do not always have a common lattice: the recorded high-resolution
  path contains a 2048→1250 resample before O2. `OR_postresample` and O2 do have
  a common lattice, but their local agreement still does not pass “by
  construction.” Demosaic simulation, clipping, and sharpening can alter
  polarity, phase, and edge shape. Agreement should be measured and remain a
  support condition.
- “No source contact” means no direct O0-carrier reintroduction. It does not
  mean carrier-safe. O1 itself is an untrusted carrier with respect to
  detection.

H0 can be considered later as a separately sealed experiment only if the H1
candidate clears real-vendor validation and the delivered H0 opportunity is
shown to justify its lower downstream survival. It should not be bundled into
4D-1b.

## 2. Detection-safety posture and required safeguards

The correct posture is **non-amplifying preservation under uncertainty**. The
candidate must be presumed capable of strengthening a detector-relevant
component until paired real-vendor evidence says otherwise. Energy caps reduce
risk; they do not certify it, because detector scores are not known to be
monotonic in H0/H1 energy and a fingerprint may occupy only a small structured
part of a band.

### Structural safeguards

1. **Strict data boundary.** Synthesis may reference only the O1-derived
   `OR_postresample` buffer and the incumbent camera result derived from it. O0,
   a resampled O0, source alignment, and source coefficients must not enter the
   candidate. The source remains measurement-only. Raw O1 should not be aligned
   anew when the existing deterministic post-resample buffer already defines
   the output lattice.

2. **One band, one variable.** The product arm restores H1 only. H0, H2,
   camera radii, sharpen, codecs, finisher, wash, and final encode remain
   frozen. This is required for attribution, not merely implementation
   convenience.

3. **Camera-residual basis.** A change is eligible only where OR contains more
   local H1 energy than O2 and the signed OR/O2 H1 structures agree. The added
   signal must be a dose of the observed OR→O2 residual; it must not be a free
   high-pass transform of OR or O2. It may increase H1 toward OR but never past
   OR, may not attenuate H1, and may not reverse coefficient polarity. Those
   are restore-only invariants, not claims of detector neutrality.

4. **Dose ceiling.** **MODEL ESTIMATE:** cap the requested local restoration at
   25% of the positive H1 energy demonstrably removed by OR→O2, with the exact
   post-change local H1 energy also capped at OR's local energy. Use one frozen
   dose for the sealed candidate. The 25% value is a conservative starting
   point, not a measured optimum.

5. **Agreement and noise support.** **MODEL ESTIMATE:** require signed local
   OR/O2 H1 correlation ≥0.90, axial orientation difference ≤10°, and usable
   H1 SNR ≥4. These values have not been characterized on the 4D-1b pair set.
   Eligibility must be re-applied after any confidence-field smoothing so that
   weight cannot leak outside support.

6. **Artifact exclusions.** Exclude flat/near-flat areas, clipped or saturated
   neighborhoods, unstable color transitions, and locations where the camera
   introduced a sign reversal or a second edge response. Use the union of
   strong edges found independently in OR and O2, not the intersection.
   **MODEL ESTIMATE:** dilate that exclusion by 2 O2 pixels. Protected product,
   architecture, typography, and privacy-edit boundaries from the frozen ROI
   manifest are evaluation vetoes even though the manifest should not tune the
   runtime synthesis.

7. **No carrier-directed optimization.** Do not choose masks, dose, or bands by
   repeatedly querying a real vendor. Candidate selection must be completed on
   frozen checkpoint/quality evidence and the pinned simulated screen. Real
   vendors are a release gate for that fixed candidate, not a tuning oracle.

8. **Fail-closed reporting.** Record pre/post local band-energy distributions,
   eligible and affected support, cap hits, exclusions by reason, exact pixel
   hashes, and O1/OR/O2/preservation/O5 identity. A missing or unclassified
   detector component, changed evaluator identity, cap violation, or report
   inconsistency rejects the candidate.

### Detector safeguards

The paired-incumbent criterion should be retained and made component-wise.
Aggregate “AI likelihood” is insufficient: one family can worsen while another
improves and conceal the regression in an average.

- **FIXED PRODUCT REQUIREMENT:** every required real-vendor C output must
  satisfy ai ≤0.45, flux-family ≤0.30, and deepfake ≤0.10.
- **MODEL ESTIMATE:** use stricter release headroom of ai ≤0.40,
  flux-family ≤0.27, and deepfake ≤0.08 for the candidate. These margins are
  prudent but are not supported by a supplied vendor repeatability study.
- **MODEL ESTIMATE:** on the pinned simulated detector, no individual C
  component may rise by more than +0.02 versus its paired B, the cohort median
  change for every component must be ≤0.00, and there may be no new family or
  verdict crossing.
- **MODEL ESTIMATE:** at each required real vendor, the cohort median paired
  change for every mapped component must be ≤0.00, no individual paired
  component may worsen by more than +0.02, and C may not receive a worse
  verdict category than B. The +0.02 individual allowance is a provisional
  noise margin. If a pre-frozen same-file repeatability bound is worse than
  +0.02, that vendor cannot substantiate the non-amplification claim at this
  margin; do not silently widen the acceptance limit.

The absolute requirement and paired non-amplification requirement are both
necessary. A candidate well below the absolute threshold can still be moving
toward failure, while a candidate neutral to B can still be ineligible if B
was already above a fixed ceiling. Simulated grades may prune; only the frozen
real-vendor leg can support promotion of a pixel-changing candidate.

## 3. Recommended pre-registered product gates

The gates should be conjunctive: no quality win may compensate for detection
or artifact failure. “Mean” below means the arithmetic mean over paired cells,
not the mean of per-pair percentages. All image-level direction counts should
combine the two seeds before counting an image.

| Gate | Recommended requirement | Basis |
|---|---|---|
| Pre-cell replay: activation | **MODEL ESTIMATE:** all 12 archived candidate replays produce a quantized change at the preservation checkpoint and at O5; no fail-closed or empty-support result | Prevents a repeat of 4D-1a's no-op round; the 12/12 threshold is proposed, not validated |
| Pre-cell replay: effective dose | **MODEL ESTIMATE:** recover ≥20% of the cohort's measured OR→O2 H1 energy loss, with no pair below 10% | Tests actual aggregate effect after masks and quantization, not requested dose; excludes legitimate resample loss from the allowance |
| Provenance | 12/12 O1, OR, and raw-incumbent-O2 inputs equal within each B/C pair; same image, seed, wash, resample, camera, codec, finisher, and detector identities; all hashes and reports complete | Exact paired-design requirement; no tolerance is appropriate |
| Primary composite recovery | **MODEL ESTIMATE:** reduce mean common-O2→O5 transition loss by ≥25%. Using the **MEASURED** B means 0.098217 overall and 0.106025 on the hard subset gives C ceilings 0.07366275 overall and 0.07951875 for IMG-5/6/9/11 | Reuses the prior product-effect bar; the baselines and arithmetic are measured, but 25% as the minimum meaningful improvement is a model estimate |
| Delivered H1 | **MODEL ESTIMATE:** mean O5 H1/source ratio ≥0.445, median texture-ROI HFTR_H1 gain ≥8% versus B, and ≥5/6 image means improve | 0.445 is the approximate outcome of restoring 25% of the measured 0.454 camera H1 loss and applying the measured 0.748 downstream survival; response linearity is unverified |
| Delivered edge/detail | **MODEL ESTIMATE:** median O5 EATR gain ≥0.04 versus B | Reuses the prior declared product-effect floor; it has not been validated as a user-perceptual threshold |
| Protected and smooth regions | **MODEL ESTIMATE:** protected EATR ≥0.98×B in every pair; smooth-region luma and chroma RMS rise ≤5%; directional rho rise ≤0.03 | Reuses the existing safety envelope; supplied results show it can be measured, not that these are optimal limits |
| Edge geometry | **MODEL ESTIMATE:** median width-gap worsening ≤+0.25 px and no pair >+0.50 px; median overshoot rise ≤+0.02 and no pair >+0.03; out-of-transition excess-energy median rise ≤2% and no pair >5%; zero candidate-created second peaks in protected ROIs | Retains the already specified 4D-1a artifact vetoes; the numerical tolerances remain model estimates |
| Simulated detection | **MODEL ESTIMATE:** apply the 0.45/0.30/0.10 ceilings as a MOCK pruning screen; require component-wise median C−B ≤0.00, no individual component >+0.02, and no new family/verdict crossing | MOCK scores are not verified as calibrated to real-vendor scores; screening only, cannot promote |
| Blinded visual panel | **MODEL ESTIMATE:** on the frozen −2 to +2 preference scale, median pair score ≥+0.5; no named artifact reported by at least 2 reviewers on at least 2 images | Ensures the metric gain is a visible, natural product improvement |
| Real-vendor release | **FIXED PRODUCT REQUIREMENT:** every C satisfies ai ≤0.45, flux-family ≤0.30, deepfake ≤0.10 at every required vendor. **MODEL ESTIMATE:** also meet 0.40/0.27/0.08 headroom, component-wise median C−B ≤0.00, no individual increase >+0.02, and no worse category | Detection has priority over visual quality; missing results fail closed |
| Determinism and scope | Same-build/same-machine outputs and reports byte-identical; OFF arm byte-identical to incumbent; only the sealed H1-preservation variable differs | Exact invariants, not statistical tolerances |

The O5 H1 target is intentionally tied to the measured stage destruction rather
than to arbitrary sharpness. Its planning calculation is:

- **MEASURED:** camera H1 loss = 0.938 − 0.484 = 0.454;
- **MODEL ESTIMATE:** restore 25% = 0.1135 at O2;
- **MEASURED planning factor:** 0.362/0.484 = 0.748 downstream survival;
- **MODEL ESTIMATE:** O5 result = 0.362 + 0.1135 × 0.748 ≈ 0.447, rounded down
  to a 0.445 gate.

This arithmetic is a useful pre-registration target, not a prediction of a
nonlinear, support-masked implementation. It uses the combined O1→O2 stage loss
because no cohort OR-band mean was supplied; the actual local restoration cap
must use only OR→O2 loss. If that stricter candidate cannot clear the O5 gate in
checkpoint replay before any live cell, it is underpowered and should not enter
the round.

## 4. Were the rejected rounds avoidable?

Partly—and the avoidable part was the use of full sealed rounds to answer
questions that archived-checkpoint feasibility could answer first.

**4D-CAM-1:** the hypothesis was reasonable and the result was informative.
However, its promotion to a 34-cell screening round was avoidable. A fixed-rung
replay on the existing OR buffers, followed by the same edge-spread audit, could
have exposed both the 5.7% effect against the 25% target and the edge widening
before live cells. The mistake was not testing the radius; it was placing
effect-size characterization after commissioning the product round.

**4D-1a:** the full 24-cell round was much more clearly avoidable. Source/remint
support coverage, cross-scale persistence, and whether a quantized output could
exist were checkpoint-level mechanism questions. Replaying a small frozen
sample would have revealed 0.02–0.13% support and the no-op before deployment.
The carrier-safety gates were sensible; the missing step was a feasibility
audit of their intersection.

Neither result was scientifically worthless. Both located a failure mechanism.
But neither produced a product candidate, and both used the most expensive
validation layer to discover a condition that a cheaper layer could have
rejected.

The process should become a staged evidence funnel:

1. **Mechanism feasibility:** on frozen archived checkpoints, show eligible
   support, cap compliance, quantized activation, and same-machine determinism.
2. **Effect-size replay:** on the entire proposed sentinel set, require the
   candidate to clear the same objective product gates intended for the live
   round, including O5 survival and edge artifacts.
3. **Candidate freeze:** choose one dose and one band, freeze all identities,
   masks, reports, evaluator versions, thresholds, and stop rules. No candidate
   selection after detector outcomes are visible.
4. **Sealed simulated screen and panel:** verify paired provenance, reproduced
   effect, and perceptual naturalness. Stop on any required gate.
5. **Real-vendor release:** spend only on the already frozen candidate and stop
   on either absolute ineligibility or paired component amplification.

It is impossible to guarantee that a legitimate product experiment will
succeed. The defensible guarantee is narrower: another no-op or obviously
underpowered mechanism must not reach the live screening round. If 4D-1b later
fails only at a real detector despite clearing replay, quality, artifacts, and
simulated screening, that is not preventable from the present evidence; it is
the irreducible reason the real-vendor release gate exists.

## 5. Threshold status and recommendation summary

The only detection thresholds verified as requirements by the supplied brief
are **ai ≤0.45, flux-family ≤0.30, and deepfake ≤0.10 at real vendors**. They
are owner-defined fixed product requirements, not empirical estimates from the
band-energy study.

The 0.098217 overall and 0.106025 hard-subset transition-loss baselines, the
stage band-energy ratios, the 5.7% 4D-CAM-1 loss reduction, and its measured
quality/edge movements are recorded measurements. Arithmetic derived directly
from them is labeled measured above.

Every new numerical decision boundary in this response—including the 25%
local H1 dose, support thresholds, replay recovery floors, quality floors,
artifact tolerances, detector-delta allowances, release headroom, and panel
score—is explicitly marked **MODEL ESTIMATE**. None should be represented as a
validated human-perception threshold, a calibrated detector-noise bound, or an
optimal operating point without new evidence.

## Final recommendation

Advance one candidate concept to pre-cell replay: **OR→O2 H1-only,
loss-constrained camera-detail preservation derived solely from the wash
output**. Do not include H0, do not retune
the finisher, and do not alter the camera radii or sharpen path in the same
candidate. Require the replay to clear the proposed full product-effect gates
before commissioning cells. If it does, run the sealed screen with absolute
eligibility and component-wise non-amplification as independent vetoes. If it
does not, stop at replay; the mechanism is not ready for a product round.

This opinion authorizes no implementation, operational action, grading, or
promotion.
