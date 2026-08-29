# C8 ReMint 1.01 Build — Master Engineer Acceptance & Adjudication

Date: 2026-08-30. Verdict: **BUILD ACCEPTED. HARD STOP UPHELD. 1.01 REMAINS
NON-PRODUCTION. 1800 FLOOR METRICS MOVE TO THE LIVE TIER-1 BATTERY.**

## 1. Verification (all independently re-run)

- Frozen archive preflight: **291/291**.
- New validator tests: **5/5**. AR1 regression: **13/13**. Deno identity
  tests: **8/8**. `tsc` + `vite build`: clean.
- AR1-pinned frozen worker files: **zero-diff**.
- Artifact index: 55 entries, all hashes valid (report entry resolves to the
  root file).
- Calibration cross-check vs archived band map: IMG-5/ctla1 0.398670 vs
  0.398668; IMG-11/ctla1 0.416749 vs 0.416745. Cohort 0.361715423 inside
  0.362 ± 0.001. Chain calibrated.
- Preset surface: `remint-1-01` exposed in /remint and /relab; identity
  predicates exclusive (`defaultOutputTarget` now required for Config
  A/1A/2B/3C/4D tuples so 1800 cannot misclassify); `output_target`
  serialized only when non-null in V8.8/V8.9/V8.9-HD; goldens
  `SEQ-CFA-dtbnbygm5iao` and all prior codes byte-identical.

## 2. Adjudication — brief contradiction

The build contract prohibited tracked-file modification while requiring
preset surfaces in tracked files. **Ruling: the preset requirement controls.**
The five changed files (RemintApp, RelabApp, deepcleanClient,
settingsIdentity, settings_identity_test) are exactly the preset surface; no
AR1-pinned frozen file changed. Accepted as C88 resolved it.

## 3. Adjudication — the 1800 hard stop

Upheld. The archived 4D-1a reports store `creator_id_hash` only (raw
`creator_id` is the camera RNG seed input) and never record the chosen
ladder attempt. Offline replay of the 1800 camera stage would require
inventing one of those — forbidden. C88 stopped correctly; no metrics were
fabricated. The brief's "camera rung per archived attempts choice" was a
spec defect (mine); the validator's provenance gate is the correct
implementation.

## 4. Decision — where the 1800 floors are measured now

The **live Tier-1 battery** carries the floor metrics, because the live
adaptive ladder runs with real provenance (worker records attempts, seeds,
and choices at 1800 with MOCK probes).

- On the 6 sentinel delivered files (ReMint 1.01, seed lab-ctla1, MOCK),
  compute the frozen `metric_record` recipes (geometry-matched source):
  cohort `h1_energy_ratio` floor **0.342**; `protected_eatr_absolute_min`
  floor **0.98**; report H0/H2, texture noise, staircase.
- Optional paired ratios: 6 extra cells running Config A + `output_target
  1800` (CUSTOM tuple) as lattice-matched twins; report-only.
- Wash-process arm (`regen_process_cap 1800`, live ComfyUI only): 6 cells,
  `identify_after` compared against the 1536 arm; report-only, no promotion
  effect.

## 5. Battery parameters for the operator runbook

Preset `ReMint 1.01` · marker `SEQ-1.01-sywgbtfbjwhg` (seeded
`SEQ-1.01-yg63qja3got4`) · sentinels IMG-5…11 · seed `lab-ctla1` · Phase 1
MOCK only · Phase 2 Hive leg NOT authorized until Tier-1 passes and the
owner allocates the 12 calls (16 remain after S1).

## 6. Promotion unchanged

Tier-2 leg per vendor freeze v3: 12 calls = 6 Config A re-fetched
hash-pinned + 6 1.01 delivered; thresholds AI ≤ 0.45 / flux ≤ 0.30 /
deepfake ≤ 0.10; paired non-amplification. 1.01 promotes only if Tier-1
floors, visual checklist, and the leg all pass.

Signed: **Master Engineer (D) · 2026-08-30**
