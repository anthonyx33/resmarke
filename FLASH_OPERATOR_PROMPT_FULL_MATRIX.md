# FLASH OPERATOR PROMPT — FULL MATRIX (ALL PRESETS × ALL IMAGES, REAL ONLY)

Role: mechanical operator. Execute exactly. No engineering decisions, no
threshold changes, no skipped cells, no mock grades, no interpretation.
This run records every remaining preset against all 11 images with REAL
Hive grades and feeds the SlashBase ledger.

## 0. Parameters (filled by master engineer)

- Presets to run: **Config A · Config 1A · Config 2B · Config 3C**
  (ReMint 1.01 is ALREADY DONE — 11 real grades exist; do not re-run it.)
- Images: IMG-1 … IMG-11, in that order, every preset.
- Fixed seed for every cell: **`lab-ctla1`**
- Detector for grading: **REAL g1 only.** Any mock row = stop.
- Expected settings code per preset (seeded lab-ctla1, exact, hard-check):

| Preset | Required code |
|---|---|
| Config A | `SEQ-CFA-lhbmeve33nn3` |
| Config 1A | `SEQ-1A-tpxokpv5c53f` |
| Config 2B | `SEQ-2B-vr6sikgjt3ap` |
| Config 3C | `SEQ-3C-nzzomjahxuyi` |
| ReMint 1.01 (reference) | `SEQ-1.01-yg63qja3got4` — already recorded |

## 1. Pre-flight (P0)

1. /relab signed in as owner; credit balance recorded in the ledger.
2. **No-caps check:** the vendor counter must show a `10000`-style cap
   (the exact secret is `GRADE_SESSION_CAP=10000` — values above 10000
   are silently rejected by the function and fall back to 40). The cap is
   stored per grade session at first call and can only lower — a session
   that ever saw cap 40 stays at 40 forever. So this run REQUIRES a fresh
   browser tab (new sessionStorage `grade-session` id) opened AFTER the
   owner sets the secret. Verify via the P0 step 3 call: its
   `session_usage.cap` must equal 10000, else STOP and report.
3. Provider check: grade ONE tiny test image via detection-only; the row
   must be `vendor: g1`, `mock: false`, `provider_calls: 1`. (This single
   verification call is outside the matrix.)
4. Worker check: the updated worker image is live — if any job dispatch
   errors during the run, stop and report; do not retry-loop.

## 2. Phase A — run all 44 cells (4 presets × 11 images)

For each preset in order (Config A → 1A → 2B → 3C), for each image in
order (IMG-1 … IMG-11):

1. Regular /relab file-add run (NOT the corpus picker — no registration).
2. Preset active, seed `lab-ctla1`, run, wait for completion.
3. Ledger per cell: image, preset, job id, settings code shown — **must
   equal the required code above exactly** — credits consumed, timestamp.
4. Download the delivered file as
   `<PRESET>_<IMG-N>_lab-ctla1.jpg` in the matrix folder; record SHA-256.
5. Any error or code mismatch → stop that cell, record it, continue to the
   next; report all stops at the end.

## 3. Phase B — 44 real grades (4 presets × 11 RM)

Per vendor freeze v3 mechanics, no interpretation:

1. Hash-pin all 44 delivered files into the ledger BEFORE any grade call.
2. Submit in order: preset by preset, IMG-1 … IMG-11, detection-only mode.
3. Record every response verbatim: ai, deepfake, flux-family, verdict,
   top_source, task_id, vendor_error (if any). No retries, no re-ordering,
   no dropped files.
4. C2PA deny-list: any C2PA finding → record and stop the leg.
5. OG grades: already real (11 rows from today's leg) — REUSE, do not
   re-grade originals.

## 4. Visual checklist — 44 before/after pairs

Per pair, tick OK / FLAG: blur/softness, edge ringing, banding, grain
uniformity, color fidelity, gross artifacts. One-line note only on FLAG.

## 5. Stop conditions (any one → stop and report)

- Any settings-code mismatch · any mock row · session cap still enforced ·
  worker dispatch errors · any call beyond the written 44 · any seed or
  preset deviation · any C2PA finding.

## 6. Declaration (required with handoff)

"I ran exactly the 44 cells and 44 grades in this runbook, in order,
presets Config A/1A/2B/3C with seed `lab-ctla1`, marker codes as listed,
detector REAL g1 only, and made no engineering decisions. Ledger and files
are complete and unmodified."

Signed: Flash operator
Date / time: `<FILL>`

## After the run

The master engineer computes the frozen quality metrics on all 44
delivered files, the per-preset matrix comparison against the real OG
grades, and publishes the SlashBase rows.
