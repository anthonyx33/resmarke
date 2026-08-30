# 4D-S1 — Stage Detection Ledger (master freeze)

Author: master engineer (D). Date: 2026-08-29.
Purpose: measure each pipeline stage's incremental REAL-detector value using
existing archived bytes. Measurement-only — no candidate selection, no
production implication. Supersedes nothing; AR1/AR2 records stand unchanged.

## 0. Adopted model (four layers) with measured corrections

The owner's four-layer map is adopted as the shared model. Two corrections
are frozen into this record:

1. **"The wash output still flags" is UNMEASURED.** We have zero
   real-detector scores for any stage. All prior screening was mock. This
   commission produces the first such measurements.
2. **The camera ladder is the largest MEASURED detail cost** (H1 energy
   −0.543); the resample's cost is near-zero geometry-normalized (qualified
   secondary effect). The resample dies first because it is dead weight —
   near-zero defense value, no necessary function — not because it is the
   biggest cost. Measured stage costs (frozen): camera 0.543, q92 ≈10%,
   QF ≈12% of remaining H1.

The map's decisive gap stands as stated: nothing rebuilds Layer 2's detail
half. The stage-by-stage walk begins here.

## 1. Objective

For the 12 archived B cells, measure with the single frozen vendor (Hive):

- does the wash output clear detection thresholds alone (O1)?
- does the resample change the score (OR)?
- does the camera ladder add measured detection value (O2 vs O1/OR)?
- does the delivered incumbent clear (O5)?

Output: a frozen detection ledger of per-file scores and per-stage deltas,
hash-indexed, with the interpretation rules of §4.

## 2. Graded files (existing bytes, no new compute)

Per cell, ctla1 seed only (6 cells = IMG-5,6,7,8,9,11 × lab-ctla1):

| # | file | bytes pinned in | question |
|---|---|---|---|
| 1 | `round-4d-1a/checkpoints/<job>/O1_postwash.png` | AR1 index / expected-manifest | wash alone clears? |
| 2 | `round-4d-1a/checkpoints/<job>/OR_postresample.png` | AR1 index | resample delta |
| 3 | `round-4d-1a/checkpoints/<job>/O2_precamera.png` | AR1 index | camera-ladder value |
| 4 | `round-4d-ar1/arms/A0/<job>/O5_final.jpg` | AR1 index | delivered incumbent |

24 files total. **Call budget: 24 of the 40-call cap.** The remaining 16
are reserved: 12 for a future single-winner leg (AR2 §7) + 4 margin. Any
second batch (ctla2 cells, ablation variants) requires a new freeze.

Format caveat (frozen): intermediates are graded as their exact archived
PNG bytes; O5 as the exact delivered JPEG. Format effects are reported, not
corrected, in this commission.

## 3. Vendor mechanics (frozen)

Single vendor Hive; `VENDOR_FREEZE_4D_1A.md` v3 rules (fresh-call ledger,
C2PA deny-list, no flux key = evaluator failure, one call per file, raw
response stored verbatim); thresholds: AI ≤ 0.45, flux-family ≤ 0.30,
deepfake ≤ 0.10; missing/malformed response fails closed for that file and
is recorded. The ledger is a measurement instrument, not a pass/fail
verdict: every file's score is reported regardless of threshold.

## 4. Interpretation (frozen)

Compute per stage the cohort median AI probability across the 6 cells and
the per-cell deltas:

- `wash_clear` = median(O1_AI) ≤ 0.45
- `resample_delta` = median(OR_AI − O1_AI)
- `camera_value` = median(O2_AI − OR_AI)
- `delivered_clear` = median(O5_AI) ≤ 0.45
- `finish_value` = median(O5_AI − O2_AI)

Decision rules (each outcome → a specified next action):

1. `wash_clear` true AND `camera_value` ≤ +0.05 → the ladder contributes no
   measured detection value → its removal/decomposition is the next
   commission's direction.
2. `wash_clear` false AND O2 cohort median ≤ 0.45 → the ladder has real
   measured value → decompose it to the detection-essential minimum (next
   commission measures sub-steps with the same ledger mechanics).
3. `wash_clear` false AND O2 median > 0.45 → the ladder cannot close the
   gap alone → pivot to wash-policy work (O1 is the blocker), per the AR1
   §9 table.
4. `delivered_clear` false → the shipped chain does not clear the frozen
   vendor on the sentinel cells → abstention review, never ship least-bad.
5. `resample_delta` ≥ +0.05 → the resample carries measured detector value
   and is retained; otherwise it is confirmed dead weight.

## 5. Constraints (frozen)

Measurement-only: no candidate is selected from this data; any challenger
must still pass the AR2-quality gates (or a future quality commission)
before its own vendor leg. No production admission; the AR3 fresh-holdout
requirement is unchanged. No grading of files outside the §2 list. Stop
conditions: pin mismatch on any graded file, ledger tamper, forbidden
external action, call-budget overrun.

## 6. Deliverables and sequence

1. Builder implements `deepclean-worker/tools/round_4d_s1_ledger.py`
   (file-pin verification + ledger schema + interpretation rules) + tests.
   No grading, no network — the operator executes the actual calls through
   the existing frozen `grade-image` path in REAL mode.
2. Master engineer verifies line-by-line; owner + operator execute the 24
   calls; raw responses land in `round-4d-s1/ledger-raw.json`, hash-indexed
   with the file pins.
3. Master engineer computes §4 deltas and writes `C8_4D_S1_REPORT.md`.
4. The resulting direction (removal, decomposition, or wash pivot) is
   commissioned as a new freeze. Track B remains optional.
