# ROUND 4D-CAM-1 — MASTER ENGINEER ANALYSIS & VERDICT

Round experiment: `a137ce61-8a42-49f4-abe4-9e22b19300df`
Sealed variable: `optics_psf_scale` 1.00 → **0.50** (build `acbcead`, C8 verified, deployed by owner)
Operator: DeepSeek Flash Max (34/34 cells, all MOCK) · Analysis: master engineer
Date: 2026-08-27

---

## 0. Verdict

**4D-CAM-1 (scale 0.50) is REJECTED.** Four of the eight pre-registered gates fail
(gates 2, 3, 4, 6). Per §6 of the frozen brief: `0.50` is rejected and the
hash-verified V12.3 incumbent (`c569595`) is restored. No alternative scale is
authorized. Panel (gate 7) and real-vendor leg (gate 8) are NOT reached — stopping
before panel/vendor spending is mandatory when screening gates fail.

## 1. Provenance (gate 1) — PASS

- 35 dirs retrieved from the RunPod volume = 34 round cells + 1 superseded pre-fault
  `3efe62e2` (excluded by design, never in the paired analysis).
- **238/238 files pixel-verified** against the DB-derived expected manifest
  (`pixel_sha256` = width‖height‖RGB tobytes): zero mismatches.
- 17/17 OR pairs hash-equal; O0_source equal within every pair.
- Server-side identity (verified earlier): B cells all `SEQ-CFA-*` (Config A),
  C cells all `SEQ-CAM1-*`, 17× scale 1.00 / 17× scale 0.50, all MOCK.

## 2. Camera-only effect (gate 2) — **FAIL**

Fixed-rung replay (rung `deep`, index 0 — the live selected rung in all 34 cells),
identical OR, creator, seed, and cfg for both arms:

| | B (scale 1.00) | C (scale 0.50) |
|---|---:|---:|
| paired mean camera-only loss | **0.2874** | **0.2709** |

- Reduction: **5.7%** — required **≥25%**. FAIL.
- Sub-conditions PASS: paired live-adaptive mean improves (0.2073 → 0.1893);
  no two-seed sentinel mean worsened (all 6 sentinels improved in both replay and
  live-adaptive loss).
- Replay validation: 17/17 self-deterministic on the analysis machine;
  **10/17 pairs reproduce BOTH arms bit-exactly vs live O2**; the other 7 differ by
  ≤4 LSB max / ≤0.008 LSB RMS with identical layer parameters (scene multiplier,
  effective radii) — cross-machine float32 noise (pod vs Mac), not a path difference.
  Full record: `round-4d-cam-1/replay-validation.json`.

## 3. Correct subset gate (gate 3) — **FAIL**

IMG-5/6/9/11 × two seeds, C-arm mean O1→O2 loss:

| | value |
|---|---:|
| required | **≤ 0.1561** |
| measured C mean (n=8) | **0.1869** |
| reduction vs Config A 0.2081125 | **10.2%** (required 25%) |

Recipe proof: the B arm of this round reproduces the frozen Config A per-cell values
**exactly** (0.1131 / 0.0916 / 0.1630 / 0.1713 / 0.2894 / 0.2892 / 0.2776 / 0.2697),
so the measured C values are directly comparable to the pre-registered baseline.

## 4. Delivered detail (gate 4) — **FAIL**

| metric | required | measured | |
|---|---:|---:|---|
| median O5 EATR gain (17 pairs) | ≥ 0.04 absolute | **0.0142** | FAIL |
| median texture-ROI HFTR_H1 gain | ≥ 8% relative | **5.92%** | FAIL |
| sentinel direction (6 images × 2 seeds) | ≥ 5/6 | **6/6** | PASS |

All six sentinel image means moved in the predicted direction for both O5 EATR and
texture HFTR_H1 — the lever is real and directionally correct, but its size is
roughly a quarter to a third of the pre-registered effect.

## 5. Protected / smooth safety (gate 5) — PASS

| metric | floor | worst measured |
|---|---:|---:|
| protected EATR ratio C/B | ≥ 0.98 (no pair) | **1.0188** (C better in every pair) |
| smooth luma RMS increase | ≤ +5% | **+1.06%** |
| smooth chroma RMS increase | ≤ +5% | **+0.89%** |
| directional rho rise | ≤ +0.03 | **+0.0033** |

No safety regression. The candidate is gentler on protected/smooth regions than B.

## 6. Edge behavior (gate 6) — **FAIL**

Median O5 edge-width gap to O0 (geometry-matched R5 reference), relative closure:

| | value |
|---|---:|
| required | ≥ +10% closure |
| measured median | **−8.3%** (widened) |
| pairs widened | 10 of 17 (several by 100–600%) |

Unexpected and material: while EATR/HFTR improve, the delivered edge *spread* worsens
— consistent with sharper PSF interacting with the scene-modulated sharpen to
oversharpen or ring, widening strong-gradient profiles. Gate 6 fails on its primary
metric; per the frozen rule one confirmed artifact on a protected edge would also
reject independently.

## 7. Panel + real detection (gates 7–8) — NOT REACHED

Screening gates failed → stop per §6. No panel run, no vendor freeze, **no vendor
calls made** (vendor 40-cap untouched: 0 consumed of the reserved 24).

## 8. Credit & budget reconciliation

- Privacy: 992920 → 992115 (−782 round + −23 orphan). DeepClean: 999553 → 999518
  (−34 round − 1 orphan). All accounted, no cell exceeded its cost.
- RunPod/GPU: 34 cells + superseded pre-fault cell, now cleaned from the volume.

## 9. What this teaches (for the next brief)

1. The PSF lever works in the intended direction on every objective metric that
   measures retention (EATR, HFTR, subset loss, protected/smooth safety) — but at
   **~20–25% of the required effect size**, while edges widen instead of tightening.
2. Half-scale Gaussian radii (deep: 0.32/0.40 → 0.16/0.20 G/RB) are insufficient to
   close the loss gap; the dominant O1→O2 loss is not primarily PSF blur.
3. The scene-modulated sharpen path appears to be the edge-widening suspect and
   deserves measurement before any further radius change.

## 10. Rollback & next actions

- **Owner (production):** confirm/restore V12.3 incumbent `c569595`; disable the
  `4D-CAM-1` lab preset in `/relab` (it must not be selectable for production use).
- **Owner (infra):** terminate retrieval pod `rm2m18tz3lp01e`, reattach
  `healthy_scarlet_squid` to `remint-v6`, restore worker scale (owner ops only).
- **Already done by me:** volume cleaned (34 round dirs + superseded dir + tar
  removed); local archive kept at `round-4d-cam-1/checkpoints/` (238 files, verified),
  `gate-results.json`, `replay-validation.json`, `expected-manifest.json`.
- **Next:** per §6, 4D-2A float/RGB handoff remains the next independent brief,
  followed by the already-approved 4D-1a H1/H2 source transfer (alpha 0.10, H0
  excluded). Neither may be merged into this rejected build.

### Artifact files

- `round-4d-cam-1/gate-results.json` — per-pair metric record + gate verdicts
- `round-4d-cam-1/replay-validation.json` — 34-arm replay vs live hashes/deltas
- `deepclean-worker/tools/round_4d_cam_1_gates.py` — gate computation (reuses frozen
  `checkpoint_attribution` / `camera_only_replay` primitives only)
- `deepclean-worker/tools/round_4d_cam_1_replay_validation.py` — replay validation
