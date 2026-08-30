# FLASH OPERATOR PROMPT — PRESET TEST BATTERY (RUNBOOK)

Role: mechanical operator. You execute this runbook exactly. You make no
engineering decisions, change no thresholds, skip no cell, and interpret no
result. Every field below in `< >` is filled by the master engineer before
each battery.

## 0. This battery's parameters

- Preset under test: `<PRESET_NAME>` (e.g., ReMint 1.01)
- Settings marker required on every output: `<SEQ_MARKER>` (e.g., SEQ-1.01-<hash>)
- Sentinel images: IMG-5, IMG-6, IMG-7, IMG-8, IMG-9, IMG-11
- Fixed seed for every cell: `<SEED>` (e.g., lab-ctla1)
- Detector mode for Phase 1: **MOCK only**
- Hive calls authorized for Phase 2: `<CALLS>` (12 = full leg per vendor freeze v3), ledgered before start

## 1. Pre-flight (P0)

1. Open /relab, confirm signed in as the owner account.
2. Confirm the preset `<PRESET_NAME>` is selectable and that its exported
   settings code begins with `<SEQ_MARKER>`.
3. Confirm Config A is NOT active when running the new preset (one preset at
   a time; pairs only in Phase 2).
4. Record current credit balance. Write it in the ledger.

## 2. Phase 1 — live MOCK screen (6 cells)

For each sentinel image, in order:

1. Load the image into the corpus queue.
2. Ensure the active preset is `<PRESET_NAME>` and detector = MOCK.
3. Run the cell with fixed seed `<SEED>`. Wait for completion.
4. Record in the ledger: image name, job id, settings code shown on the
   result (must start with `<SEQ_MARKER>`), mock verdict (ai / flux /
   deepfake scores shown in the UI), credits consumed, timestamp.
5. Download the delivered file. Save it as
   `<PRESET_NAME>_<IMG-N>_<SEED>.jpg` in the battery folder. Note its size.
6. Any cell that errors, returns a mismatched settings code, or produces no
   file → **STOP**. Report the cell; do not continue to the next cell.

After all 6: export the completed ledger, list all 6 delivered files with
names, and run the visual checklist (Section 4). Then STOP and hand off to
the master engineer. **Phase 2 never starts without explicit authorization.**

## 3. Phase 2 — Hive leg (only on master-engineer authorization)

Per vendor freeze v3, mechanics only — no interpretation:

1. Re-fetch the 6 incumbent delivered files (Config A, same 6 images) from
   storage; record their SHA-256 into the ledger BEFORE any grading call
   (hash-pinned).
2. Confirm the 6 new-preset delivered files from Phase 1 are hash-pinned in
   the ledger as well.
3. For each of the 12 files (6 incumbent + 6 new-preset), submit one grade
   call in the ledger order. Record the vendor's response verbatim into the
   ledger — ai, flux family, deepfake if returned, plus any vendor_error.
4. Do not retry a call, do not re-order, do not drop a file. A failed or
   missing flux key = evaluator failure, recorded as such.
5. No file may carry C2PA metadata; if any does, record it and stop the leg.

## 4. Visual checklist (both phases, per before/after pair)

For each pair, tick exactly one of OK / FLAG per row. Write a one-line note
only when FLAG.

| Item | OK | FLAG | Note |
|---|---|---|---|
| Blur / softness vs source | | | |
| Edge ringing / halos | | | |
| Banding in smooth areas | | | |
| Grain uniformity (no patchy noise) | | | |
| Color fidelity vs source | | | |
| Gross artifacts (smear, ghost, moiré) | | | |

## 5. Stop conditions (any one → stop and report)

- Any cell error or settings-code mismatch.
- Any credit-balance surprise beyond the expected cost.
- Any attempt to run Phase 2 without authorization.
- Any threshold, seed, or preset value differs from this runbook.

## 6. Declaration (required with the handoff)

"I ran exactly the cells and steps in this runbook, in order, with the preset
`<PRESET_NAME>` and marker `<SEQ_MARKER>`, detector MOCK in Phase 1, and made
no engineering decisions. Ledger and files are complete and unmodified."

Signed: Flash operator
Date / time: `<FILL>`
