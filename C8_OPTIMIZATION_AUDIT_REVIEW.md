# MASTER ENGINEER REVIEW — C8_OPTIMIZATION_AUDIT_RESPONSE.md

Date: 2026-08-27 · Reviewer: master engineer · Status: **ACCEPTED with amendments**

C88's response is high quality, evidence-disciplined, and correctly labels every
unverifiable claim as a model estimate. It changes no frozen artifacts and violates
no protocol rule. Verdict: accept as the working basis for the next round.

## Items C88 flagged that I have now resolved with data

1. **"Missing 33rd chain" in 23/32 — resolved, not missing.**
   `ATTRIBUTION_REPORT.md` §0 documents it: 33 dirs retrieved; the 32 captured jobs
   (192/192 files pixel-verified) form the complete analysis set; the exclusions are
   `d2f1a8d5` (error row, no checkpoints — correct) and `daf0f0a7` (volume dir with no
   ledger row — superseded dispatch). The 23/32 PRIMARY count covers 100% of eligible
   chains. My brief should have carried the exclusion note; C88's question was fair.

2. **Sentinel aggregation — both levels hold.**
   Re-computed from `gate-results.json`: not only 6/6 image-level means, but
   **12/12 seed-level sentinel cells** are positive on O5 EATR, and 12/12 on texture
   HFTR_H1, and 12/12 on protected EATR. Stronger than my brief stated.

3. **Edge-width ratio inflation — CONFIRMED as a real confound, but only part of the story.**
   Absolute gap (px, combined band edge_width_10_90, B→C):
   - Near-zero denominators produced the giant relative figures (e.g., IMG-5 ctla1
     gap 0.103→1.179 = −10.5 relative, but only 0.4→4.6 px absolute).
   - However **genuine absolute widening exists**: IMG-8 ctla1 7.3→22.6 px,
     IMG-7 ctla1 8.1→10.0 px, IMG-6 ctla1 0.4→2.8 px — while other pairs are sub-pixel
     or improve (IMG-8 ctla2 10.6→6.7, IMG-7 ctla2 9.1→4.3).
   → Both of C88's hypotheses are live: real edge-spread damage on some images AND
     ratio instability on others. Adopt absolute widths + indeterminate-denominator
     marking for all future edge gates. The median relative closure −8.3% is not
     purely a ratio artifact.

## What I adopt from C88

- **Risk framing**: W2 = top product risk (detection lexicographically primary);
  W1 = top measured quality loss. Re-rank accepted.
- **4D-1a architecture**: remint-led, support-gated, phase-preserving H1/H2 energy
  matching — source supplies target energy, never raw phase/residual copy. This
  matches the owner's recorded double-edge caution and is the correct first move.
- **Agreement gates**: local alignment (pyramid displacement), orientation (≤15°),
  phase/polarity (signed corr ≥0.80, no second peak), cross-scale persistence,
  protected-edge dilation exclusion, per-region energy cap, full-frame processing
  with crops used for measurement only.
- **Edge diagnosis**: substage edge-spread audit (raw + monotonic-fitted widths,
  overshoot/undershoot, out-of-transition energy, MTF50/90, stratified by
  orientation/contrast) before ANY further camera radius change.
- **Lattice**: keep 1250px; isolate float/RGB handoff (4D-2A) first; lattice change
  only after a sealed finisher-grid experiment passes the frozen gates.
- **Wash**: fail-closed content-routed candidates from approved wash paths only;
  MOCK rejection first; post-wash AND post-finisher (O5) eligibility; never paste
  unwashed source; abstain rather than ship a flagged image.
- **Recipe upgrades** (future rounds, frozen tools untouched): report the paired
  (dEATR, dHFTR_H1) vector + joint loss alongside the scalar; normalize frequency
  bands in cycles/picture-height; absolute edge widths + denominator floors;
  per-ROI values before aggregation; seed-level sentinel reporting.

## Amendments I require before 4D-1a GO

1. **Bit-identity of the OFF arm**: transfer-off must replay to the exact incumbent
   O2/O5 pixel hashes (same replay-proof discipline as 4D-CAM-1). No silent drift.
2. **Support-gate parameters frozen in the brief before first light**, including the
   numeric thresholds C88 proposed (displacement, orientation, correlation, dilation).
3. **Gate 2 MOCK detection margins**: C88's ≤0.45/0.30/0.10 + 0.02 non-inferiority on
   MOCK grades is acceptable as a conservative screen (MOCK emulates vendor numerics),
   but must be labeled screening-only; real-vendor leg remains the only eligibility proof.
4. **Subset gate reuse**: ≤0.1561 was derived for the PSF variable on IMG-5/6/9/11 ×
   2 seeds. Reusing it for 4D-1a is permitted ONLY as a pre-registered acceptance gate
   for this round; it does not inherit the 0.2081125 baseline meaning (that baseline
   was Config A's own loss — for 4D-1a the paired incumbent is the comparison).
5. **Edge gate re-specified in absolute terms** per the finding above: median absolute
   gap closure ≥10% AND no pair worsens by more than the frozen absolute floor (to be
   set from the incumbent distribution, pre-light).
6. **Reproducibility note**: the 4-LSB cross-machine drift is below all transition-loss
   scales (0.02–0.43) and cannot change gate verdicts; for small-median metrics
   (EATR gain ~0.014 scale), paired deltas computed on ONE machine from verified
   checkpoints remain the canonical recipe (as done here).

## Immediate next move (zero vendor, zero code, existing buffers)

Run the **edge-spread substage audit** C88 specified, on the 34 4D-CAM-1 checkpoint
dirs already retrieved (OR_postresample vs O2_precamera, B and C arms, 17 pairs):
raw vs monotonic 10–90 width, overshoot/undershoot, out-of-transition energy,
stratified by orientation/contrast. This settles whether widening is true blur
spread or ringing-induced crossing distortion BEFORE 4D-1a code is commissioned.

## After that

Owner GO → I author the 4D-1a build brief for C88 (code access): transfer stage
placement, support gates, checkpoint contracts, replay proofs, then the 16-pair
sealed screening round per C88's §6 with my amendments 1–5.
