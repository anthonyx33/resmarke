# MASTER ENGINEER REVIEW — C8_4D_1A_BRIEF_AUDIT.md

Date: 2026-08-27 · Reviewer: master engineer · Status: **ALL MANDATORY AMENDMENTS ACCEPTED**

C88's audit is accepted in full. Disposition per item:

1. **Equation — ACCEPTED.** `B' = α·w·(B_src − B_remint)` was coefficient
   interpolation and did not prove phase preservation. Replaced with the one-sided
   remint-coefficient scaling `B' = g·B_remint`,
   `g = 1 + min(α·w·(√(E_src/E_remint) − 1), 0.10)`, `g ≤ 1.10`, energy caps
   `E' ≤ min(1.21·E_remint, E_src)`, never attenuate, sign preserved exactly.
   Source sample values never enter the output.
2. **Alpha dose — ACCEPTED.** α requested frozen at exactly 0.10; the g/energy
   caps give it an unambiguous maximum dose; local w may only reduce it.
3. **Edge gate target — ACCEPTED.** Comparing standard O2s was vacuous (identical
   by construction). Gates now compare C `O2_transfer` against paired B O2 on
   frozen common edge support, source-relative, at both the transfer stage and O5.
4. **Out-of-transition energy + candidate-relative second-peak — ACCEPTED.**
   Restored the oot gate (2% median / 5% pair, both stages); second-peak rule is
   now candidate-created only (zero new protected peaks; +0.25 pp global /
   +1.0 pp per-pair incidence), because the incumbent itself rings (~6–7 crossing
   candidates, overshoot ≈0.065 at O2).
5. **Frozen arithmetic — RESOLVED WITH DATA, not just wording.** C88 demanded the
   O2→O5 denominator be published before first light. Computed from the 17
   incumbent B cells already retrieved:
   `round-4d-cam-1/incumbent-o2-o5-baseline.json` —
   all-pair B mean **0.119253**, hard-subset B mean **0.106025** (≥ 0.02 floor,
   well-conditioned). Gate formula frozen as `1 − mean(L_C)/mean(L_B) ≥ 0.25`
   over combined scalars (never per-pair percentages); hard-subset operational
   gate **0.0795**.
6. **Flag semantics — ACCEPTED.** `4d1a: true` without a valid lab seed fails
   closed; absent/false preserves incumbent behavior byte-for-byte.
7. **Determinism — ACCEPTED.** All primitives frozen (R2 resampler, luma, gauss,
   energy window, w smoothing, NCC ε/tie-break, border mode, float64, serialization);
   same-build/same-machine byte-identity required; cross-machine runs
   non-authoritative, noise floor measured at build time.
8. **Fixture proofs — ACCEPTED.** Flat no-op, E_src ≤ E_remint no-op,
   equal-energy/different-phase invariance, zero-crossing retention,
   mask-boundary extrema, α=0/flag-false/flag-absent byte-identity, NaN/border/
   zero-denominator fail-safe added.
9. **Pre-vendor carrier-drift screen — ACCEPTED.** MOCK gate 7 now requires zero
   new family-threshold crossings and full B→C detector vector reporting, not just
   the three aggregate axes.
10. **Vendor-leg freeze — ACCEPTED, owner action flagged.** Vendor 2, sentinel
    identities, vendor versions, score mapping, retry policy, and the combination
    rule must be frozen BEFORE round first light. If the owner does not freeze
    Vendor 2, screening may proceed but the vendor leg and any promotion cannot.
11. **Attribution wording — ACCEPTED.** The brief no longer claims adaptive
    sharpen is the causal substage inside O2→O5; the composite is implicated and
    the finisher substage remains a model estimate.
12. **Threshold classification table — ACCEPTED as authoritative for this round.**

Resulting document: `C8_MASTER_PROMPT_4D_1A_BUILD_BRIEF_V2.md` (supersedes v1).
Next: owner sends v2 to C88 for the accept/amend pass (`C8_4D_1A_BRIEF_AUDIT_V2.md`);
on accept, owner commissions the build.
