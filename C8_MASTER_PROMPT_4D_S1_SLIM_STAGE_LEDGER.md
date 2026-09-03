# C8 MASTER PROMPT — 4D S1-SLIM STAGE DETECTION LEDGER (supersedes the 24-call S1 freeze)

Role: C88 builder-architect. Build the frozen ledger tool below. No grading,
no network, no RNG, no regeneration. This commission executes the single
next experiment recommended by the full-matrix consultation and approved by
the owner.

## 0. Context (verified facts you must not re-litigate)

The 5-preset × 11-image real-grade matrix is complete and independently
verified. Config A (qwen/deep, delivery ≤1250) is the best arm (4/11 v3
pass). The central unresolved question: **which pipeline stage carries the
detection signal** for the 7 resistant images. The wash, resample, camera
ladder, stage-1 encoding, and finish have never been graded separately
with a real detector. This ledger resolves that with exactly 18 real Hive
g1 calls on archived bytes.

## 1. Cells and files (exact, hash-pinned)

- Cells: the six archived Config A / A0 sentinel cells with seed
  `lab-ctla1`: **IMG-5, IMG-6, IMG-7, IMG-8, IMG-9, IMG-11**
  (the same six in floors-1.01-live.json).
- Grade exactly three archived files per cell:
  1. `O1_postwash.png` — after qwen/deep wash, before resample
  2. `OR_postresample.png` — after incumbent resample (delivery ≤1250)
  3. `O2_precamera.png` — after camera ladder, before quality finish
- Use archived bytes only. No regeneration, no transcoding, no
  substitution. Pin SHA-256, pixel dims, stage, cell, seed, source before
  any call.
- O5 (delivered) grades are NOT re-bought: reuse the matrix Config A
  delivered grade for a cell only when the archived O5 hash exactly equals
  the matrix delivered-file hash. On mismatch, record `o5_hash_mismatch`
  and do not reuse.

## 2. Grade freeze (18 real calls, vendor freeze v3)

- 18 fresh Hive g1 calls exactly, one per file, in ledger order
  IMG-5..IMG-11 × O1, OR, O2. No retries, no reordering, no drops.
- Record verbatim per row: ai_probability, deepfake_probability, verdict,
  sources (incl. flux-family max), top_source, task_id, model/version,
  session_usage, any vendor_error. C2PA deny-list: any finding → stop the
  leg. Fail-closed on missing fields. Mock rows are forbidden and
  invalidate the leg.

## 3. Frozen computation (tool output, no human math)

For each stage define the per-cell AI probability change and the cohort
decision statistics (median over the 6 cells):

- `wash_clear` = median AI(O1) ≤ 0.45
- `resample_gain` G_R = median( AI(O1) − AI(OR) )   [resample reduces AI]
- `camera_gain`  G_C = median( AI(OR) − AI(O2) )    [camera reduces AI]
- `o2_clear`     = median AI(O2) ≤ 0.45
- `delivered_clear` = median AI(O5) ≤ 0.45 (from hash-verified reused rows)
- Directional consistency: a stage is `material` when |G| ≥ 0.05 AND the
  per-cell value is non-negative in at least 4 of 6 cells AND no cell whose
  O5 passes full v3 (AI ≤ 0.45, flux ≤ 0.30, deepfake ≤ 0.10) has a
  negative per-cell gain for that stage. Mixed signs (a material stage
  that violates either consistency rule) prohibit a universal change.

## 4. Decision table (frozen; report must emit exactly one row)

| Condition | Decision |
|---|---|
| wash_clear AND camera NOT material | Commission camera-ladder removal / minimum strength (AR2 quality gates govern any challenger) |
| NOT wash_clear AND o2_clear AND camera material | Commission camera sub-step decomposition to the minimum passing strength |
| NOT wash_clear AND NOT o2_clear | Stop camera work; commission wash-policy / photo-naturalization / stage-order work |
| resample_gain material | Retain resample as detection-essential |
| resample NOT material | Mark resample dead weight; exclude from future freezes unless AR2 passes without it |
| any material stage with mixed signs | No universal change; a holdout-designed per-image policy is required before any routing |

## 5. Builder deliverables

1. `tools/round_4d_s1_slim_ledger.py` — pins (hash/dims/stage/cell/seed)
   and schema for the 18 rows, the frozen computations in §3, and the
   decision table in §4. No grading, no network, no RNG, overwrite-refusal,
   atomic writes. Accepts a raw grade JSONL (operator-produced) and emits
   `round-4d-s1-slim/{ledger-raw.json, stage-deltas.json, decision.json}`.
2. Tests covering: pin validation, median/sign computations, materiality
   edge cases (|G|=0.05 boundary, 4/6 consistency, passing-cell veto),
   every decision-table branch, overwrite refusal, malformed input.
3. `C8_4D_S1_SLIM_BUILD_REPORT.md` — build summary, test counts, and
   nothing else.

Do not implement any grading call, any detector change, or any preset
change. Analysis and ledger only.

## 6. After the build

Master engineer verifies line-by-line → owner + operator run the 18 real
calls through the existing grade-image path → master engineer computes the
deltas and emits `C8_4D_S1_SLIM_REPORT.md` → next commission per the
decision table. The 18-call budget is hard; do not propose spending beyond
it.

## Addendum 1 (2026-09-03) — preflight findings, frozen before any leg

1. **O5-equivalent source.** Preflight measured: all six archived
   A0-1250 `O5_final.jpg` hashes differ from the full-matrix Config A
   deliveries (the archived arms were produced by the retired worker
   image). The frozen O5-equivalent is therefore the authority-pinned
   matrix Config A delivered grades
   (`round-full-matrix/phase-b-detection-ledger.json`, preset "Config A",
   same six images). `o5_hash_mismatch` is recorded informationally and
   does NOT block computation. `delivered_clear`, the O5 median, and the
   passing-cell veto all use the matrix Config A delivered grades. No O5
   call is re-bought.
2. **Sources invariant.** Real Hive v3 payloads contain no "none" class
   (measured across all verbatim rows). The frozen invariant is: sources
   non-empty, all values finite probabilities, sum within 1e-3 of 1.0,
   at least one flux/auraflow family key, and `flux_family` equal to the
   family maximum. The "none" requirement is removed.
3. **Decision table completed (total function).** Two rows added:
   - wash_clear AND camera material → **camera_retain**: retain the
     ladder (detection-essential); commission wash-policy / stage-1
     encoding work.
   - NOT wash_clear AND o2_clear AND camera NOT material →
     **camera_neutral**: retain camera at minimum strength (neutral);
     commission wash-policy / resample-attribution work.
   All other rows unchanged. The table is now total; the interpreter may
   not raise on any measured combination.
4. **Byte-identical stage pairs.** Preflight pins show IMG-6, IMG-7, and
   IMG-8 `O1_postwash.png` and `OR_postresample.png` share identical
   SHA-256 (sources ≤ 1250 — the incumbent resample is a no-op). Freshness
   rules therefore apply **per unique byte stream**, not per logical row:
   the first row for a byte stream must be `cache_hit: false`,
   `provider_calls: 1`; a duplicate byte-stream row is recorded verbatim
   from the first grade with `cache_hit: true`, `provider_calls: 0`, the
   same task_id and identical probabilities/verdict/sources.
   `session_usage.vendor_calls` advances by one only across fresh
   submissions and repeats on duplicates. The logical ledger remains 18
   rows; the vendor-call budget is 15 fresh calls. Per-cell resample gain
   for an identical pair is 0 by construction.
