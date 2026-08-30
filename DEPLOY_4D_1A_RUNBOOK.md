# DEPLOY RUNBOOK — 4D-1a (OWNER OPS)

Build: accepted by master engineer (`C8_4D_1A_BUILD_ACCEPTANCE.md`).
All steps below are owner actions. Builders never commit/deploy.

## Step 1 — Commit + push

1. Review the working tree: 7 modified tracked files + these new files:
   - `deepclean-worker/transfer_4d_1a.py`
   - `deepclean-worker/tools/transfer_4d_1a_harness.py`
   - `deepclean-worker/tools/transfer_4d_1a_identity_test.ts`
   - `deepclean-worker/tools/transfer_4d_1a_edge_test.ts`
   (Do NOT commit unrelated untracked artifacts.)
2. Commit and push to `main` (anthonyx33/resmarke). Vercel auto-deploys the UI;
   CI builds the worker image on `deepclean-worker/**` paths.

## Step 2 — Deploy edge functions (identity bundle)

```
supabase functions deploy create-deepclean-job corpus-run-intent \
  --project-ref otzjqcnrabfbonjywlye --use-api --jobs 2
```

(create-deepclean-job carries the `4d1a` boundary; corpus-run-intent carries the
identity module for the experiment config_set gate.)

## Step 3 — Deploy worker image to RunPod

- Take the new CI image digest (worker image built from the push).
- Update endpoint `remint-v6` (`2c9528ebg2vzvx`) to the new digest — same
  procedure as every prior deploy.
- Env is already correct; no changes:
  `DEEPCLEAN_CHECKPOINT_DIR=/runpod-volume/deepclean-checkpoints`,
  `DEEPCLEAN_CHECKPOINT_DURABLE=1`, `LAB_FIXED_SEED_ENABLED=1`,
  `GRADE_PROVIDER=mock`. Restore worker scale as usual.

## Step 4 — Deploy verification probes (do these before any cell)

1. Edge boundary: a `create-deepclean-job` call with `4d1a: true` + seed
   `lab-ctla1` + optics absent must pass the settings-code gate and produce
   code `SEQ-4D1A-kqbl35dztkl4`; `4d1a: true` with seed `lab-other` must 400.
2. Worker `/health` ready after deploy; warmup completes.
3. `/relab` shows the `4D-1A — LAB · H1/H2 source transfer α=0.10` preset and
   enforces `lab-ctla1`/`lab-ctla2` seed lock.

## Step 5 — Create the round experiment (before first cell)

- `/corpus` → new fixed-corpus experiment, locked set `Fixed corpus v1`
  (same as 4D-CAM-1), config_set EXACTLY:
  `["A", "SEQ-4D1A-kqbl35dztkl4", "SEQ-4D1A-p3m5qpiorc7b"]`
- No generic `CUSTOM`. Record the experiment id and the ledger constants
  (engine_version, ROI sha, frozen gate numbers from the FINAL brief).

## Step 6 — Round execution

- Master engineer authors `FLASH_OPERATOR_PROMPT_4D_1A.md` (24 cells:
  6 sentinels × 2 seeds × B/C, all MOCK, 552 privacy + 24 deepclean).
- Flash runs cells per the prompt's gates and stop conditions.
- Vendor: 0 calls during screening (single-vendor Hive leg only after
  gates 1–7 pass, per `VENDOR_FREEZE_4D_1A.md` v3).

## Step 7 — Analysis

- Retrieve the 24 checkpoint dirs (same retrieval-pod SOP), pixel-verify
  against the ledger, then master engineer computes gates 1–7 against the
  frozen numbers (G2 ceiling 0.07366275 · G3 0.07951875 · ESF gates · MOCK
  carrier-drift screen).

Stop conditions unchanged: any non-MOCK row, checkpoint/aux failure, code
mismatch, OR-hash mismatch, credit shortfall, or boundary rejection stops the
round immediately.
