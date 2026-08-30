# MASTER ENGINEER REVIEW — C8_4D_1A_BRIEF_AUDIT_V2.md

Date: 2026-08-27 · Reviewer: master engineer · Status: **ALL ITEMS ACCEPTED — v3 ISSUED**

C88's second pass is accepted in full. Disposition:

1. **Population mismatch — ACCEPTED, option 2 chosen.** C88 correctly proved the
   frozen denominator mixed 17 legacy cells with the 16-cell round, missing
   IMG-1/4/10 ctla2 and including IMG-2/3/7 cells. Option 1 (exact 16-cell mean)
   is impossible — three legacy baselines do not exist. Adopted option 2: the
   screening population is now the SIX sentinels × both seeds = 12 pairs / 24
   cells, exact legacy match, and the sentinel-set mismatch is fixed
   simultaneously.
2. **Frozen denominator — REGENERATED population-exact.** 12-cell B mean
   **0.098217** (≥0.02 floor); hard-subset **0.106025**; G3 threshold exact
   **0.07951875**; evidence file with per-cell job ids, O2/O5 pixel hashes,
   formula, and population list:
   `round-4d-cam-1/incumbent-o2-o5-baseline-v3.json`
   SHA-256 `90be734b4c6a45b5077e8691a31e44ea26083a422cb9ab5fecf7c26ff1c2be9c`.
3. **Primitive completion — ACCEPTED verbatim.** C88's recommended confidence
   formula (five normalized margins, min-combination, SNR saturated at 8),
   alignment geometry (32 px block / 16 stride / ±8 search / quadratic subpixel),
   band-wise warp after decomposition, MAD-based noise estimate with 1e-6
   fallback, p92 Sobel union edge mask with 2 px Euclidean dilation, additive
   luma-delta reconstruction with single clip (chroma-preserving), frozen
   `_gauss` uint8-quantized numeric path, and single vectorized window-rescale
   cap enforcement are all frozen in v3 §3.
4. **Gate 6 semantics — ACCEPTED verbatim.** Source-relative worsening formula,
   hashed-before-inspection support, pair/round median definitions, minimum
   counts (100/pair, 20 protected) as hard failures, excess-energy denominator
   floor max(B_excess, 0.01), ±0.5 px second-peak matching, +0.02 amplified-peak
   rule, pinned ESF evaluator.
5. **Gate 7 semantics — ACCEPTED with the only honest resolution.** The MOCK
   evaluator is pinned by the deployed `grade-image` identity hash at round time;
   the component/family list is whatever the pinned MOCK emits, declared before
   first light; fail-closed on missing components. We do not invent a family
   taxonomy that the MOCK may not produce.
6. **Report timing — ACCEPTED.** `transfer_4d_1a` assembled post-O5, hashes
   recorded at transfer time.
7. **Vendor freeze — ACCEPTED, no exception.** Owner must freeze Vendor 2 and all
   vendor-leg constants BEFORE the first screening result is viewed. Screening
   may not start without it. This is now an owner gate on the round itself.
8. **Label — ACCEPTED.** `α=0.10` exact, not `α≤0.10`.

Resulting document: `C8_MASTER_PROMPT_4D_1A_BUILD_BRIEF_V3.md`.
Next: owner sends v3 to C88 (`C8_4D_1A_BRIEF_AUDIT_V3.md`). On accept, and with
Vendor 2 frozen, I commission the 24-cell build and round.
