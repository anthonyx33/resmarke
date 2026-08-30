# MASTER ENGINEER REVIEW — C8_4D_1A_BRIEF_AUDIT_V3.md (FINAL PASS)

Date: 2026-08-27 · Reviewer: master engineer · Status: **ALL ITEMS ACCEPTED — CONSOLIDATED FINAL BRIEF ISSUED**

C88's final pass accepts the architecture and round design and closes the
remaining mechanical items. Dispositions:

1. **Support re-masking (the blocking item) — ACCEPTED.** Final weight is now
   `w = clip(gauss_σ3(w_raw), 0, 1) × support_binary` — the complete support
   predicate (all five numeric gates + cross-scale persistence + outside edge
   exclusion) is reapplied AFTER smoothing. Smoothing can no longer leak
   transfer into pixels that failed any gate.
2. **G2 operational form — ADDED.** `mean(L_C) ≤ 0.07366275` (= 0.75 × 0.098217)
   is recorded as the derived arithmetic form of the 25% gate.
3. **Edge recipe — CORRECTED.** `_edge_mag` is `np.gradient` magnitude, not
   Sobel; the consolidated brief freezes the exact recipe.
4. **Alignment details — FROZEN per C88.** Per-level block/stride in each level's
   own pixels, ×2 coarse initialization, ±8 residual search, independent 1-D
   parabolas, ±0.5 px clamp, zero at degenerate peaks; alignment between remint
   O2 luma and R2 luma; band-wise warp into remint geometry.
5. **Noise energy units — FROZEN.** `noise_energy = max((1.4826 × MAD)², 1e-6)`
   over the lowest-20%-edge-energy tiles' H2 samples; `SNR = local_band_energy /
   noise_energy`.
6. **Synthesis/clipping — ADOPTED C88's stronger option.** Scalar delta capped to
   the common feasible interval (`delta_safe = clip(delta, −min(R,G,B),
   1−max(R,G,B))`) so channel differences are preserved exactly even in
   highlights/shadows; capped-delta pixel fraction reported.
7. **Cap enforcement — FROZEN.** Corrected gain clamped to `[1.0, 1.10]`;
   final window energies recomputed; fail closed beyond 1e-9 relative.
8. **Consolidated brief — DONE.** `C8_MASTER_PROMPT_4D_1A_BUILD_BRIEF_FINAL.md`
   is the single authoritative specification; no layered-text precedence
   ambiguity remains.
9. **Gate 6 clarifications — ADDED.** Excess-energy change formula computed
   per-edge before pair medians; a protected ROI below 20 valid edges fails gate
   6 even if another protected ROI passes; evaluator hash + support artifact hash
   + counts + exclusion-reason histogram recorded in the ledger before candidate
   inspection.
10. **Gate 7 clarifications — ADDED.** Full numeric precision as returned by the
    pinned evaluator (no display rounding before any comparison); one evaluator
    identity across all 24 cells, change aborts the round.
11. **Determinism fixtures — ADDED.** No final w outside complete support after
    smoothing; exact `_edge_mag` equivalence; gain ≥ 1 after cap enforcement;
    final energy-cap verification; channel-difference preservation/clipping
    truthfulness. Noise-floor results never relax same-machine hash gates or
    screening thresholds.

C88's final disposition: ACCEPT FOR BUILD after this erratum — issued as the
consolidated FINAL brief. Remaining prerequisites before first light:
(a) master-engineer verification of the build report (no commit/deploy by
builder), and (b) the OWNER'S Vendor 2 freeze — screening cannot start without
it.
