# FLASH OPERATOR PROMPT — ReMint 1.01 FULL-CORPUS HIVE PASS

Role: mechanical operator. Execute exactly. No engineering decisions, no
threshold changes, no skipped files, no interpretation. This supersedes the
6-sentinel battery for ReMint 1.01 per the owner's full-corpus directive.

## 0. Parameters (filled by master engineer)

- Preset: **ReMint 1.01** · required settings code on every result:
  **`SEQ-1.01-yg63qja3got4`** · fixed seed **`lab-ctla1`**
- Images: **all 11 corpus sentinels** in this order: IMG-1, IMG-2, IMG-3,
  IMG-4, IMG-5, IMG-6, IMG-7, IMG-8, IMG-9, IMG-10, IMG-11
- Phase A: run each image through the preset, MOCK grades, download files.
- Phase B: **real Hive grades** — counts in Section 0b. Never exceed them.
- Credits: record balance before and after every cell.

## 0b. Call budget (hard — verify before Phase B starts)

- Hive calls authorized for this pass: **22** — eleven fresh OG grades + eleven
  fresh ReMint 1.01 delivered grades, all hash-pinned before any call.
- Owner allocation (written, 2026-08-30): the S1 stage-ledger's reserved 24
  calls are **deferred**; this 22-call paired leg consumes 22 of the 40-call
  reserve, leaving 18 margin. Do not begin Phase B without the master
  engineer confirming the ledger entry.

## 1. Pre-flight (P0)

1. /relab, signed in as owner, ReMint 1.01 ACTIVE (Config A OFF), seed
   `lab-ctla1`, code chip `SEQ-1.01-yg63qja3got4`, credit balance recorded.
2. **Provider check for Phase B:** confirm with the master engineer that the
   real Hive provider is enabled. If the UI shows MOCK as the only grade
   mode, STOP before Phase B and report — do not spend calls on a mock.

## 2. Phase A — run all 11 images through ReMint 1.01

For each image in order (regular /relab runs, NOT the corpus picker, so the
20-output corpus cap does not block IMG-5/6):

1. Upload the source (the canonical sentinel file).
2. Preset ReMint 1.01, seed `lab-ctla1`, run the cell, wait for completion.
3. Record in the ledger: image, job id, settings code (must be exactly
   `SEQ-1.01-yg63qja3got4`), mock verdict, credits, timestamp.
4. Download the delivered file as `1.01_<IMG-N>_lab-ctla1.jpg` and save the
   source as `<IMG-N>_source.<ext>`. Record both SHA-256s in the ledger.
5. Any error or code mismatch → STOP that image, record, continue to the
   next; at the end report all stops.

## 3. Phase B — real Hive grades (22 calls, paired OG vs 1.01)

Per vendor freeze v3 mechanics, no interpretation:

1. Hash-pin all 22 files into the ledger BEFORE any grade call:
   - Group OG: the 11 canonical source files (same bytes as the corpus
     sentinels, e.g. `CFA-REAL-CREATOR-IMG-N.png/jpg`).
   - Group RM: the 11 delivered files `1.01_<IMG-N>_lab-ctla1.jpg` from
     Phase A.
2. Submit in ledger order — for each image: OG first, then its 1.01 result.
   Record every response verbatim (ai, flux family, deepfake if returned,
   any vendor_error). No retries, no re-ordering, no dropped files.
3. C2PA deny-list: if any file carries C2PA metadata, record it and stop.
4. A failed or missing flux key = evaluator failure, recorded as such.
5. Comparison is NOT your job: the master engineer computes the OG-vs-1.01
   comparison from your ledger. Record only.

## 4. Visual checklist — all 11 before/after pairs

Per pair, tick OK / FLAG: blur/softness, edge ringing, banding in smooth
areas, grain uniformity, color fidelity, gross artifacts. One-line note
only when FLAG.

## 5. Stop conditions

- Any code mismatch, provider not REAL before Phase B, any call beyond the
  written allocation, any seed/preset deviation, any C2PA finding.

## 6. Declaration (required with handoff)

"I ran exactly the steps in this runbook, in order, preset ReMint 1.01,
marker `SEQ-1.01-yg63qja3got4`, seed `lab-ctla1`, MOCK grades in Phase A and
only the written number of real Hive calls in Phase B, and made no
engineering decisions. Ledger and files are complete and unmodified."

Signed: Flash operator
Date / time: `<FILL>`
