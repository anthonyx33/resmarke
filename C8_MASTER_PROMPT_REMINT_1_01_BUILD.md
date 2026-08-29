# C8 MASTER PROMPT — ReMint 1.01 BUILD (DELIVERY 1800 + TEST BATTERY)

Role: builder (code access). Deliverable: the ReMint 1.01 preset definition,
its offline validation tool, and a signed replay report. **No commit, no
push, no deploy, no RunPod/Supabase action, no grading, no live cell, no
vendor call.** Live execution is owner/operator work under Standing Rule R1.

## 1. Mission

ReMint 1.01 = Config A with exactly one variable moved: `output_target`
`null → 1800` (delivery long edge). Everything else in the tuple is
byte-identical to Config A: wash qwen / regen_level 8 / process_cap 1536,
adaptive camera ladder, color_restore 0.8, tone lock 0.8, stage-1 q92 4:2:0,
QF strong + q97 4:4:4, iPhone EXIF, stripped pass-through finalize.

Justification (frozen): 1250 delivered 37% of a 2048px source's pixels; 1800
delivers 77%; 1800 stays below the 2000px zone where the stage-1 codec was
measured detection-coupled.

## 2. Frozen inputs (reuse, do not regenerate)

- Checkpoints: `round-4d-1a/checkpoints/<job>/` — O0, O1 (2048² wash output),
  OR (1250), O2, O3, O4, O5, per cell-settings.json (pin
  `17691de31256b5a5f6db99bc0b94560606556e10b40a04fbb805340dffa439f6`).
- Offline recipes: reuse the A0-incumbent replay path from
  `deepclean-worker/tools/round_4d_ar1_factorial.py` (tone-lock via
  `_histogram_match`, `apply_quality_finish`, camera rung per archived
  `engine.attempts` choice) and the frozen metric recipes from
  `round_4d_ar1_metrics.py` / `checkpoint_attribution.py`.
- Tracked frozen files: **zero-diff** (same list as the AR1 freeze,
  FROZEN_FILE_PINS; the current hashes in evidence-pins.json remain valid).
- Calibration requirement: replaying A0 at 1250 must reproduce the archived
  cohort `h1_energy_ratio` 0.362 (AR1 measured 0.3617) before any 1800
  number is trusted. Mismatch > ±0.001 → stop and report.

## 3. Preset definition (code, no deploy)

1. New preset **ReMint 1.01** in the /remint and /relab preset surface, same
   mechanics as Config A/1A/2B: toggle, exclusivity predicates, settings
   code emission **`SEQ-1.01-<hash>`** where `<hash>` is the standard
   settings-tuple hash.
2. Tuple: Config A with `output_target: 1800`. Serialization must carry
   `output_target` in **both** `ds_remint_v8_8` and `ds_remint_v8_9` blocks
   when non-null (client + settings identity). `regen_process_cap` is NOT
   serialized for the shipped preset (it stays default 1536); the 1800
   process-cap is a test arm only (§5).
3. **Hash stability regression:** adding 1.01 must not change Config A's
   code `SEQ-CFA-dtbnbygm5iao` or any existing preset's code. Test this
   explicitly.
4. No other preset, default, or routing changes. Config A remains incumbent
   until 1.01 passes R1.

## 4. Offline validation tool (new file only)

`deepclean-worker/tools/round_remint_1_01_validate.py` + tests
(`test_round_remint_1_01_validate.py`):

- Arm `A0-1250`: incumbent replay (calibration, §2).
- Arm `1.01-1800`: same pipeline, `output_target=1800` at the delivery
  resample, from archived O1 (2048²) → Lanczos 1800 → camera rung per
  archived attempts → tone-lock → q92 → QF → q97.
- Metrics per cell and cohort, frozen recipes, geometry-matched source:
  `h1_energy_ratio`, `h0/h2_energy_ratio`, `texture_h1_energy`,
  `eatr_p95`, source-relative texture luma/chroma residual RMS ×255 and
  rho1, band H0/H1/H2 residual RMS, staircase, per-ROI protected EATR.
- Outputs: `round-remint-1-01/` artifacts, hash-indexed; report
  `C8_REMINT_1_01_REPLAY_REPORT.md` with per-cell and cohort tables.
- Deterministic, no network, no RNG, atomic writes, refuse overwrite.

Replay floors (frozen): cohort `h1_energy_ratio`(1800) ≥ 0.362 − 0.02;
protected EATR ≥ 0.98; no metric domain surprises (report, don't gate).

## 5. Live Tier-1 battery (owner + Flash operator, R1 runbook)

After my line-by-line verification of §3–§4:

- 6 sentinel cells (IMG-5…11, seed `lab-ctla1`) through the 1.01 preset in
  lab mode, detector MOCK: ledger per cell (job id, `SEQ-1.01-<hash>` code,
  mock verdicts, credits), files downloaded and hash-pinned.
- Paired wash-process arm: the same 6 images with `regen_process_cap 1800`
  (requires live ComfyUI wash — NOT offline-replayable), lab mode MOCK,
  `identify_after` recorded for both arms.
- Visual checklist per pair per the R1 runbook. Stop on any settings-code
  mismatch or cell error.

## 6. Tier-2 promotion gate (owner-authorized only)

Hive leg per vendor freeze v3: 12 calls = 6 incumbent Config A re-fetched
hash-pinned + 6 1.01 delivered. Thresholds AI ≤ 0.45 / flux ≤ 0.30 /
deepfake ≤ 0.10; paired non-amplification; median = mean of 3rd+4th sorted;
fresh-call ledger; C2PA deny-list. Budget: 16 calls remain after the S1
ledger — this leg consumes 12. 1.01 promotes to production candidate only
if every Tier-1 item passes and the leg passes.

## 7. Stop conditions

Any replay calibration mismatch, any floor failure, any frozen-file diff,
any R1 battery stop, or any failed leg → 1.01 remains non-production and
the record stands as measured. No post-hoc threshold changes.

## 8. Allowlist / forbidden

New files: `deepclean-worker/tools/round_remint_1_01_validate.py` +
tests + `round-remint-1-01/` artifacts + root report. No modification of
existing tracked files; frozen files zero-diff; no external/live/vendor
action by the builder.

## 9. Deliverable + declaration

`C8_REMINT_1_01_REPLAY_REPORT.md` (signed, dated): calibration, per-cell
1800 metrics, floors verdict, hash index, declaration that only the pinned
archive was used and no forbidden action occurred. The master engineer
verifies every line before any live step.
