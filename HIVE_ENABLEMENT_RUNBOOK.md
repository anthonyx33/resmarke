# HIVE ENABLEMENT RUNBOOK — OWNER OPS (Phase B unblock)

Goal: flip the deployed grading loop from the deterministic mock to the real
Hive API, verify it once, then run the frozen 22-call paired leg on the
already hash-pinned ReMint 1.01 files.

## Facts (verified 2026-08-30, master engineer)

- Deployed `GRADE_PROVIDER` secret = `mock` (hash `ec864fe9…` =
  sha256("mock")). Real mode in `grade-image` is `g1`.
- `GRADE_DEFAULT_MODE` = `real` (already correct).
- Real path requires `HIVE_SECRET_KEY` (Bearer to
  `https://api.thehive.ai/api/v3/hive/ai-generated-and-deepfake-content-detection`).
- The old `REAL_G1_PARSER_VERIFIED` gate no longer exists in the deployed
  code; parser tests live in `supabase/functions/grade-image/hive_test.ts`.
- 0 of 22 authorized calls spent; all 22 files hash-pinned in ledger order
  (OG then 1.01 per image) in
  `round-remint-1-01/full-corpus/ledger.jsonl`.

## Step 1 — confirm the Hive key (owner CLI)

```bash
supabase secrets list --project-ref otzjqcnrabfbonjywlye
```

Confirm a `HIVE_SECRET_KEY` entry exists (value is shown hashed; presence is
what matters). If absent, set it:

```bash
supabase secrets set HIVE_SECRET_KEY=<hive-api-key> --project-ref otzjqcnrabfbonjywlye
```

## Step 2 — flip the switch

```bash
supabase secrets set GRADE_PROVIDER=g1 --project-ref otzjqcnrabfbonjywlye
```

## Step 3 — verify with ONE call (the only call outside the leg)

In /relab (signed in as owner, real provider now active): grade one file via
"Run API detection only" on any single image. Then check the ledger row in
the UI — it must show:

- no MOCK badge
- `vendor: g1`
- `provider_calls: 1`
- `mock: false`

If instead you see an error or `vendor: mock`, STOP and report — do not
continue to Phase B.

## Step 4 — hand off to Flash

Re-issue `FLASH_OPERATOR_PROMPT_REMINT_1_01_FULL_CORPUS.md` (Phase B section,
22 calls, Section 0b allocation already written: 22 calls, S1 deferred,
18 margin). All files are already hash-pinned in ledger order — Phase B runs
immediately.

## Stop conditions

- Any grade returns `vendor: mock` after the flip → stop, revert if needed.
- Any call beyond the written 22 → protocol violation.
- Any C2PA metadata found on a graded file → stop the leg.

## After the leg

The master engineer computes the OG-vs-1.01 paired comparison, the
non-amplification check, and the frozen floors verdict, and writes the
1.01 disposition.
