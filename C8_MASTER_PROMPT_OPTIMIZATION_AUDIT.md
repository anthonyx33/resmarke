# C8 MASTER PROMPT — EXPERT OPTIMIZATION AUDIT (POST 4D-CAM-1)

Role: expert consultant. Deliverable: professional opinion + recommendations ONLY.
No code changes, no commits, no deploys, no Supabase/RunPod actions, no grading.

## 1. Mission (fixed)

Build the best image-remint product for professional creators:
- Highest visual quality: sharp, natural, realistic, premium product-content images.
- De-stamp: outputs must NOT be flagged as AI by real vendors (eligibility:
  ai ≤ 0.45, flux-family ≤ 0.30, deepfake ≤ 0.10).
- Detection eligibility is lexicographically PRIMARY; quality selects among eligible.
  A beautiful flagged image is a failed product. An ugly clean image is also a failed product.

## 2. The team loop (how rounds work)

Measure → hypothesize → pre-register gate numbers → sealed paired cells (same image,
same seed, one variable) → hash-level provenance verification → honest pass/fail.
MOCK screening first; real-vendor leg only after screening gates pass.
Budget: 40 vendor calls/session cap (hard). No post-hoc threshold changes.

## 3. Measured evidence you must audit against (not prose — numbers)

### 3.1 Pilot attribution (33 checkpoint chains, `checkpoint_attribution` frozen tool)
- Pipeline checkpoints: O0 source → O1 post-wash → O2 post-camera/pre-codec →
  O3 stage-1 delivered → O4 finisher → O5 final.
- Transition loss = max(|min(dEATR,0)|, |min(dHFTR_H1,0)|), geometry-matched references.
- **O1→O2 (resample ≤1250 + camera ladder) = mean 0.1764, PRIMARY loss in 23/32 jobs.**
  Mean deltas: O0→O1 dEATR −0.1450 / dHFTR −0.1136 · O1→O2 −0.1710 / −0.1645.
- Cumulative: edge energy ≈60% of source at delivery; H0 fine texture ≈34%;
  EATR at source resolution ≈15%.
- Codec: q97 source-relative EATR > q92 in 32/32 jobs (small but universal).

### 3.2 4D-CAM-1 round (34 cells, sealed variable: camera PSF radii ×0.50)
Pre-registered gates and results:

| Gate | Required | Measured | Verdict |
|---|---:|---:|---|
| Camera-only loss reduction (fixed-rung replay) | ≥25% | 5.7% | FAIL |
| Subset C mean O1→O2 (IMG-5/6/9/11 × 2 seeds) | ≤0.1561 | 0.1869 | FAIL |
| Median O5 EATR gain (17 pairs) | ≥0.04 | 0.0142 | FAIL |
| Median texture HFTR_H1 gain | ≥8% rel | 5.92% | FAIL |
| Sentinel direction (6 sentinel images × 2 seeds) | ≥5/6 | 6/6 | PASS |
| Protected EATR regression | >2% forbidden | C better in every pair | PASS |
| Smooth luma/chroma RMS rise | >5% forbidden | +1.1% / +0.9% | PASS |
| rho rise | >0.03 forbidden | +0.003 | PASS |
| Edge-width gap closure vs source | ≥10% | −8.3% (widened; 10/17 pairs worse, several 100–600%) | FAIL |

Verdict: 0.50 REJECTED. V12.3 incumbent restored. Key observations:
- The PSF lever improves every retention metric directionally but at ~¼–⅕ the
  required magnitude.
- Edge WIDTH worsens while edge RATIO improves — consistent with the
  scene-modulated sharpen over-sharpening/ringing at halved radii.
- Protected/smooth/rho are all SAFER under the candidate: the lever is gentle.
- Fixed-rung replay reproduces live O2 bit-exact on 10/17 pairs; remaining 7 differ
  ≤4 LSB max with identical layer parameters (cross-machine float32).

### 3.3 Known wash facts (Config A tests, 12 real pairs)
- Qwen wash = the only proven SynthID carrier-breaker. It re-stamps
  (flux/wan/kling/SD fingerprints) when it fails — 2 fingerprint-swap failures recorded.
- Outcome is content-dependent, not source-dependent (same source: 0.5 / 24.9 / 51.2).
- Probe-routed wash variants rescued specific images (qwen+zimage wins #5/#6).
- Oracle across 3 configs ≈ 3 clear / 2 near / 2 border / 4 fail → candidate diversity
  matters; no single static config wins.

## 4. Weakness ranking we have deduced (master engineer's view)

- **W1 — O1→O2 camera+resample step** destroys the most detail (PRIMARY 72%). Camera
  tuning alone cannot fix it (proven by 4D-CAM-1).
- **W2 — wash re-stamp** is the product-killer failure mode (content-dependent swaps).
- **W3 — 1250px stage-1 ceiling** compounds W1 on high-res sources.
- **W4 — camera lever direction right, dose wrong; edge-widening risk.**
- **W5 — codec compounding** (q92 4:2:0 stage-1, extra JPEG generations).

## 5. Planned next briefs (already approved, in order)

1. **4D-1a — H1/H2 source transfer**: reinject mid-band detail from the ORIGINAL into
   the remint where structure agrees, alpha 0.10, H0 excluded, exclusion masks for
   protected regions. Direct attack on W1. (Owner caution on record: naive pixel
   reinjection double-images edges; must gate on orientation/cross-scale agreement +
   local alignment.)
2. **4D-2A — float/RGB handoff**: post-camera buffer passed in memory between stages
   (no intermediate JPEG). Attacks W5 + part of W1.
3. **Edge-widening investigation** before any further camera radius change (suspect:
   scene-modulated sharpen interacting with PSF).

## 6. Questions for your expert professional opinion

1. Do you agree with the weakness ranking W1–W5? What would you re-rank and why?
2. For 4D-1a: is mid-band (H1/H2) transfer the right first attack on W1? What
   support/agreement gating would you require to avoid double-edges and halo on
   protected product edges? Any architecture you would propose instead?
3. Edge-widening: from the 4D-CAM-1 numbers, what is your mechanistic explanation,
   and what measurement would you run next to confirm it before any code changes?
4. Wash re-stamp (W2): given carrier-break is mandatory, what is your best
   mitigation architecture (routing, regional application, post-wash re-check)?
5. Lattice (W3): is 1250px still the right stage-1 ceiling, or should we move the
   finisher to native resolution? Under what evidence would you change it?
6. What ONE experiment (≤10 images, zero vendor calls) would you run next, and what
   would its pre-registered pass/fail numbers be?
7. Anything in §3 you consider mis-measured or misleading? Audit the recipes:
   transition loss, EATR/HFTR_H1 banded metrics, edge_width_10_90, ROI crops.

## 7. Response contract

- Answer each question with a recommendation and the first-principles reasoning.
- Mark anything you cannot verify from the numbers as "model estimate" (hard rule).
- No new presets, no wash combos, no code, no budget beyond the 40-cap discipline.
- Deliver as `C8_OPTIMIZATION_AUDIT_RESPONSE.md` (workspace root, untracked).
