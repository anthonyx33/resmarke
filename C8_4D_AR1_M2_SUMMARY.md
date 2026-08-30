# 4D-AR1 M2 Measured Results — CORRECTED v3 (master engineer)

This revision supersedes the two earlier M2 summaries. It incorporates the
builder C88's second audit, verified point-by-point by computation and
accepted in full. M1 factorial outputs preserved (84/84). **No panel,
candidate freeze, or Hive calls are authorized.**

Environment: `$TMPDIR/verify3` (Python 3.9.6, numpy 2.0.2, Pillow 11.3.0).
Cross-validation: A0 replay cohort `h1_energy_ratio` = 0.3617 vs archived
cohort fact 0.362.

## 1. Record corrections (accepted from the second audit)

1. **A4 is the sole floor-passer.** The machine record shows A4
   `all_pass: true` under the frozen §7.2 recipes; all five structural
   challengers fail. The earlier "no arm passes" statement was wrong.
   Formal A4 disposition: §2 below.
2. **A4 delivered identity:** 11/12 delivered cells are byte-identical to
   A0. IMG-5/lab-ctla1 differs at 2,165 decoded RGB pixel positions
   (4,112 channel samples) — the two pre-handoff candidate-pixel changes
   propagated through tone-lock/QF/JPEG. IMG-7/lab-ctla1's one pre-handoff
   change did not survive delivery. A4 fail-closed count: 10/12.
3. **Eligible lost-energy mass cohort:** mean 0.4826%, median 0.2232%,
   range 0–1.6588%.
4. **ESF ranges:** structural worst-pair overshoot deltas are
   **1.2628–8.1740** (not 0.33–8.16); protected second peaks **36–126**
   (not 8–126). Medians 0.0026–0.0215.
5. **Metric completeness:** `mean_abs_dchroma` was 255× too small
   (double normalization) — fixed; per-ROI H0/H2 energy and RMS ratios,
   texture-region residual noise (source-relative luma/chroma RMS and
   lag-1 rho1, frozen attribution recipe), per-band noise spectrum of the
   source-relative luma residual, ESF OOT deltas, and a uniform frozen
   staircase index (`checkpoint_attribution._staircase`) are now computed
   for all arms. Arm-minus-A0 noise variants are preserved under distinct
   names (`texture_arm_minus_a0_noise`, `arm_minus_a0_band_spectrum`).
   A0 cohort source-relative texture noise: luma 30.268 LSB, chroma
   28.722 LSB, rho1 0.653; band H0/H1/H2 RMS 0.0478255 / 0.0133457 /
   0.0150087 (independently matched to the auditor's reference values).
   A5/A6 QF `banding_index`/`staircase_index_jpeg` remain undefined
   (QF off) and are reported as such; their staircase attribution values
   are A5 0.425, A6 0.490 (A0 0.449).
6. The artifact index (349 entries) hash-covers the M2 results, tool,
   summary, amendments, and freeze.

## 2. Formal A4 disposition (under the existing freeze)

A4 passes all §7.2 floors and is therefore floor-eligible. Under §7.3, an
arm "with no meaningful naturalness improvement is rejected." Measured:
11/12 delivered cells identical to A0; the twelfth differs at 0.14% of its
pixels (2,165/1.56M) — below any meaningful naturalness improvement by
measurement. **A4 is therefore excluded from challenger selection by the
master engineer under the §7.3 no-meaningful-improvement criterion applied
to the measured no-op; no panel was run for A4.** This is a master-engineer
no-shortlist judgment, not an observed panel result. If the owner orders a
panel for A4, it follows the standard §7.3 protocol and its outcome is not
predetermined. No new threshold is created.

## 3. Measured quality table (unchanged, energy basis, vs source, 12 B cells)

| Arm | h1_energy | texture_h1_energy | eatr_p95 |
|---|---|---|---|
| A0 incumbent | 0.362 | 0.322 | 0.599 |
| A1 camera-off | 0.947 | 0.929 | 0.952 |
| A3 camera+codec off | 1.093 | 1.080 | 1.019 |
| A2 codec bypass | 0.403 | 0.364 | 0.628 |
| A5 QF-off | 0.411 | 0.364 | 0.624 |
| A4 4D-1b | 0.362 | 0.322 | 0.599 |

Standing facts: camera ladder is the dominant quality cost (counterfactually
proven: 0.362 → 0.947 without it); QF costs ≈12% of remaining H1; the
stage-1 q92 costs ≈10%; 4D-1b is a no-op mechanism (10/12 fail-closed,
mass 0.48% mean).

## 4. Frozen-recipe floor results (corrected, complete)

Source-relative recipe; ceilings: luma ≤5%, chroma ≤5%, rho rise ≤0.03,
protected ≥0.98, ESF overshoot +0.02/+0.03, zero second peaks.

| Arm | luma | chroma | rho1 | rho2 | protected | smooth floors | ESF |
|---|---|---|---|---|---|---|---|
| A1 | −8.86% | +2.53% | +0.005 | **+0.085** | 1.325 | FAIL (rho2) | FAIL |
| A2 | +5.61% | **+8.72%** | −0.014 | +0.027 | 1.016 | FAIL | FAIL |
| A3 | −8.31% | **+6.68%** | −0.000 | **+0.056** | 1.382 | FAIL | FAIL |
| A5 | **+10.40%** | **+5.49%** | −0.009 | −0.022 | 1.013 | FAIL | FAIL |
| A6 | −8.94% | −11.78% | +0.004 | **+0.062** | 1.352 | FAIL (rho2) | FAIL |
| A4 | 0 | 0 | 0 | 0 | 1.000 | PASS | PASS |

ESF details per arm are in `round-4d-ar1/m2-results.json`
(median/worst-pair overshoot, width worsening, OOT deltas, second peaks,
edge counts).

## 5. Disposition (frozen)

All five structural arms fail §7.2; A4 passes but is rejected for selection
under §7.3 (measured no-op). **No challenger exists → no panel, no
candidate freeze, no Hive calls.** The 84 outputs and the energy findings
are preserved and hash-indexed. Hive remains locked.

## 6. Possible next steps (each requires a new frozen commission)

1. Stop here and accept the frozen result.
2. New pre-registered §7.2 amendment (e.g., ESF profile-domain eligibility
   and/or rho definition), justified from these corrected distributions,
   hash-indexed before any panel.
3. New commission on the energy findings (e.g., minimum useful camera
   component decomposition per the §9 decision table).
Track B (Linux replay recovery) is unaffected and remains pending owner ops.
