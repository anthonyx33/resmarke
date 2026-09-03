# FLASH OPERATOR PROMPT — 4D S1-SLIM STAGE LEDGER (15 fresh vendor calls)

Role: mechanical operator. Execute exactly. The stage ledger is the frozen
next experiment; the interpreter (`deepclean-worker/tools/round_4d_s1_slim_ledger.py`)
has been master-verified (37/37 tests, 194/194 preflight checks).

## 0. What you grade

18 logical rows = 6 cells × 3 stages, in this frozen order:
IMG-5, IMG-6, IMG-7, IMG-8, IMG-9, IMG-11 — each `O1_postwash.png`,
`OR_postresample.png`, `O2_precamera.png`.

The files are archived bytes under `round-4d-1a/checkpoints/<job>/<file>`.
Get the exact contract (paths, SHA-256, dims, order) with:

```bash
cd /Users/a/Documents/NOSYNF
python3 deepclean-worker/tools/round_4d_s1_slim_ledger.py --print-contract
```

**15 fresh vendor calls, not 18.** IMG-6, IMG-7, and IMG-8 have byte-identical
`O1` and `OR` (sources ≤ 1250 — resample is a no-op). For those three pairs:
submit the file ONCE (O1), then record the OR row as a verbatim copy of the
O1 row with `cache_hit: true`, `provider_calls: 0`, same task_id, same
probabilities/verdict/sources, same `session_usage`. Never re-submit the
same bytes.

## 1. Pre-flight (fresh session)

1. Open a FRESH /relab tab (session caps only lower; never reuse old tabs).
   Sign in as owner. Balance must be 990252 (this leg spends zero remint
   credits — detection-only).
2. Panel counter must render `/10000`-style after the first call. If any
   `/40` appears → STOP.
3. Optional single provider-check call is allowed BEFORE the leg; it does
   not disturb the leg's relative vendor_calls sequence.

## 2. The leg (exact order, no retries)

1. Add the 18 files to the queue via regular file-add, in contract order
   (bypass duplicate submission for the three identical pairs as above).
2. For each fresh file: detection-only grade, ONE call, no retry, no
   reorder, no drops. Record the RAW response (use the standalone JSON /
   ledger copy buttons — probabilities must be UNROUNDED, with full
   `sources`, `task_id`, `session_usage`).
3. Write exactly 18 JSONL lines to
   `/Users/a/Documents/NOSYNF/round-4d-s1-slim-raw/grades.jsonl` in
   contract order. Required fields per row (see `--print-contract`
   `required_grade_fields`): logical_id, image, job, seed, source
   {path, sha256}, stage, file (exact pin object), attempt_number 1,
   submitted_sha256, ai_probability, deepfake_probability, verdict,
   sources, flux_family, top_source, task_id, model
   `hive/ai-generated-and-deepfake-content-detection`, version `1`,
   vendor `g1`, mode `real`, mock false, cache_hit, provider_calls,
   session_usage {vendor_calls, cap}, vendor_error null, c2pa (the raw
   response's `algorithmic_tags.c2pa` mapping, or the string
   "absent (no algorithmic_tags.c2pa in response)").
4. Fresh rows: `cache_hit: false`, `provider_calls: 1`, unique task_id,
   vendor_calls advancing by one. Duplicate rows: verbatim copies of
   their byte-identical partner row.
5. C2PA deny-list: any `actions_digital_source_type` =
   `trainedAlgorithmicMedia` → STOP the leg.

## 3. Stop conditions

Any mock row · any cache hit on a fresh row · a fresh call on duplicate
bytes · vendor error · cap not 10000 · out-of-order submission · any call
beyond the 15 fresh · any dropped file. On any stop: report, do not fix.

## 4. Handoff

Report: 15 fresh calls made, 3 verbatim duplicate rows, ledger JSONL path,
session usage total, zero stops. The master engineer runs the interpreter
(`--input round-4d-s1-slim-raw/grades.jsonl`) which publishes
`round-4d-s1-slim/{ledger-raw.json, stage-deltas.json, decision.json}`
and then writes the S1-slim report.
