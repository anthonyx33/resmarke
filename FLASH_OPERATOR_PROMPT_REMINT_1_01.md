# FLASH OPERATOR PROMPT — ReMint 1.01 TEST BATTERY (FILLED RUNBOOK)

Role: mechanical operator. Execute exactly. No engineering decisions, no
threshold changes, no skipped cells, no interpretation. This is the R1
Standing Rule battery for ReMint 1.01, per
`FLASH_OPERATOR_PROMPT_PRESET_TEST_BATTERY.md` with parameters filled.

## 0. Battery parameters (filled by master engineer)

- Preset under test: **ReMint 1.01** (label on the toggle)
- Required settings code on every result: **`SEQ-1.01-yg63qja3got4`**
  (unseeded reference `SEQ-1.01-sywgbtfbjwhg`)
- Sentinel images (run in this order): IMG-5, IMG-6, IMG-7, IMG-8, IMG-9,
  IMG-11
- Fixed seed for every cell: **`lab-ctla1`**
- Detector mode: **MOCK only**
- Hive calls authorized: **0** (Phase 2 not authorized in this run)
- Wash process-cap arm: **BLOCKED — not run in this battery** (no UI
  surface emits `regen_process_cap`; pending a lab hook. Do not improvise.)

## 1. Pre-flight (P0)

1. Open /relab, confirm signed in as the owner account.
2. Confirm the **ReMint 1.01** preset exists and toggles; when ON, Config A
   must be OFF (exclusivity).
3. Confirm the detector mode shows **MOCK** and the MOCK badge is visible.
4. Record the credit balance before starting. Write it in the ledger.

## 2. Phase 1 — live MOCK screen (6 cells)

For each sentinel image, in order, exactly:

1. Load the image into the corpus queue.
2. Ensure preset = **ReMint 1.01**, detector = MOCK, fixed seed =
   `lab-ctla1`.
3. Run the cell. Wait for completion. Do not run another cell in parallel.
4. Record in the ledger, per cell: image name, job id, settings code shown
   on the result (**must be exactly `SEQ-1.01-yg63qja3got4`**), mock verdict
   (ai / flux / deepfake shown in the UI), credits consumed, timestamp.
5. Download the **delivered** file and the **source** file. Save as:
   - `<IMG-N>_source.<ext>` (the original uploaded file)
   - `1.01_<IMG-N>_lab-ctla1.jpg` (delivered)
6. Any cell error, wrong settings code, or missing file → **STOP**. Report
   the cell. Do not continue.

After all 6: complete the visual checklist (Section 4) for each pair, export
the ledger, and hand off to the master engineer. Phase 2 never starts
without explicit authorization.

## 3. Phase 2 — Hive leg (NOT AUTHORIZED IN THIS RUN)

Do not submit any real grading call. Phase 2 becomes available only after
the master engineer computes the floor metrics and the owner allocates the
12-call leg in writing.

## 4. Visual checklist (per before/after pair)

Tick exactly one of OK / FLAG per row. Write a one-line note only when FLAG.

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
- A credit-balance surprise beyond the expected cost.
- Any attempt to run Phase 2.
- Any seed, preset, or detector value differs from Section 0.

## 6. Declaration (required with the handoff)

"I ran exactly the 6 cells and steps in this runbook, in order, with preset
ReMint 1.01, marker `SEQ-1.01-yg63qja3got4`, detector MOCK, seed
`lab-ctla1`, and made no engineering decisions. Ledger and files are
complete and unmodified."

Signed: Flash operator
Date / time: `<FILL>`
