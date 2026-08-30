# FLASH OPERATOR PROMPT — 4D-1a SCREENING ROUND (24 CELLS)

Operator: DeepSeek Flash Max (mechanical, per this prompt)
Round: 4D-1a — sealed H1/H2 source transfer α=0.10 (ON) vs incumbent (OFF)
Date: 2026-08-27

## 0. Frozen round identity (do not alter)

- **Experiment id**: `ba947d6b-2c21-4740-9d20-2b60fc9123cc`
- **Locked set**: `Fixed corpus v1` (`df0573b9-2aff-4fbc-b49f-efbf2f64bfc6`)
- **config_set**: `["A","SEQ-4D1A-kqbl35dztkl4","SEQ-4D1A-p3m5qpiorc7b"]`
- **ROI manifest sha256**: `5b0d73779e2855e5deafff5534d01aca647342e2b21370bf8664f9571ad3d329`
- **Codes**: B/ctla1 `SEQ-CFA-lhbmeve33nn3` · B/ctla2 `SEQ-CFA-cyi3altqyaaq` ·
  C/ctla1 `SEQ-4D1A-kqbl35dztkl4` · C/ctla2 `SEQ-4D1A-p3m5qpiorc7b`
- **Frozen gates (master engineer computes post-retrieval)**: G2
  `mean(L_C) ≤ 0.07366275` · G3 `≤ 0.07951875` · G4 +0.04 / +8% / 5-of-6 · G5
  0.98× / +5% / +0.03 · G6 ESF (absolute, source-relative) · G7 MOCK carrier
  screen. Vendor leg: single-vendor Hive A/B, 12 calls, AFTER gates 1–7
  (`VENDOR_FREEZE_4D_1A.md` v3). Zero vendor calls during screening.
- **Budget**: 24 cells × 23 = **552 privacy** + **24 deepclean**. Record both
  balances before cell 1; never exceed.

## P1–P5 pre-round gates (all must pass before cell 1)

- **P1** Experiment exists with the exact `config_set` above; no generic
  `CUSTOM` entry.
- **P2** `/relab` shows preset `4D-1A — LAB · H1/H2 source transfer α=0.10`;
  selecting it requires seed `lab-ctla1` or `lab-ctla2` (LOCKED warning
  otherwise).
- **P3** `round-4d-cam-1/roi-manifest.json` exists, `"FINAL": true`, sha256
  matches the frozen value.
- **P4** Credits: privacy ≥ 552 + headroom, deepclean ≥ 24.
- **P5** Ledger clean slate: zero rows with `settings_code` starting
  `SEQ-4D1A-`.

## Cell plan (24 cells, two phases, B then C per pair)

Phase 1 — seed `lab-ctla1` (12 cells): IMG-5, IMG-6, IMG-7, IMG-8, IMG-9,
IMG-11, each B (Config A) then C (4D-1A).
Phase 2 — seed `lab-ctla2` (12 cells): same image order, B then C.

For every cell:

1. Dispatch from `/relab` with the frozen experiment selected.
2. Wait for the ledger row: `status grading → completed`.
3. Verify the row, stop immediately on any failure:
   - B arm: `settings_code` = the seed's `SEQ-CFA-*` code; C arm: the seed's
     `SEQ-4D1A-*` code.
   - `mock: true`, `provider_calls: 0`, mode results from MOCK only.
   - `executed.full.expert_refinement` has the right seed and (C only)
     `4d1a: true`; B has no `4d1a`.
   - `checkpoints.status == "captured"`, 6 files, `errors == []` (both arms).
   - `auxiliary_checkpoints.status == "captured"`: B = `OR_postresample.png`
     only; **C = `OR_postresample.png` + `O2_transfer.png`**, errors `[]`.
   - C report contains `transfer_4d_1a` with `alpha_requested` 0.10 and
     `applied` true/false recorded; B report contains NO `transfer_4d_1a`.
   - Within each image/seed pair: B and C `OR_postresample.png` pixel hashes
     EQUAL; B and C `O2_precamera.png` pixel hashes EQUAL (transfer is
     strictly post-O2).
4. Record: cell #, image, arm, seed, settings_code, job_id, run_id,
   cp_status, aux_status, OR sha, O2 sha, O2_transfer sha (C), transfer
   applied, mock, credits_after (privacy/deepclean).

## Stop conditions (any one stops the round)

- Any ledger row for this round that is not MOCK, or with checkpoint/aux
  errors, code mismatch, missing `O2_transfer.png` on C, extra aux on B,
  `transfer_4d_1a` present on B or absent on C, or OR/O2 hash mismatch within
  a pair.
- Any 4D-1A boundary rejection at dispatch (e.g., 400).
- Credit shortfall, session expiry, or any cell needing a third dispatch
  attempt.

## Declaration (operator)

At completion, sign: all 24 cells MOCK; zero vendor calls; no ROI/experiment
edits; no cells re-run outside this plan; no direct Supabase/RunPod actions;
all raw facts recorded per cell for the master engineer's gate computation.
Report as `ROUND_4D_1A_CELLS.md` (workspace root).
