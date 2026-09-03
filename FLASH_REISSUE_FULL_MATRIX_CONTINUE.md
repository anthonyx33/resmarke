# FLASH — REISSUE: FULL MATRIX CONTINUE (P0 cap resolved)

The P0 stop from the previous issue is RESOLVED and verified live by the
master engineer. Resume with the same runbook
(`FLASH_OPERATOR_PROMPT_FULL_MATRIX.md`) plus the items below.

## Verified facts (do not re-verify these)

- `GRADE_SESSION_CAP=10000` is set (secret hash matches sha256 of "10000").
- The deployed grade-image function now returns `session_usage.cap = 10000`
  on a live call, `vendor: g1`, `mock: false`.
- Your earlier stop was correct; it is cleared. 10000 covers the matrix
  (44 grades + 1 verification) with huge margin.

## Do this IN ORDER

1. **Open a FRESH /relab browser tab.** Never reuse the old tab — its grade
   session is permanently capped at 40 (session caps only ever lower).
2. Sign in as owner (`anthonyx33@proton.me`). Balance must read **991264**.
3. **P0 step 3 provider verification** (one tiny test image, detection
   only). The response must show `session_usage.cap == 10000` and the panel
   counter must render `/10000`-style. Also required: `vendor: g1`,
   `mock: false`, `provider_calls: 1`. If the new tab still shows 40 →
   STOP and report.
4. **Leave the 2 existing queue leftovers untouched**
   (`IMG-11_source.jpeg`, `1.01_IMG-11_lab-ctla1.jpg`). Add the 44 matrix
   cells as new queue entries. Regular runs only — NO corpus registration.
5. **Phase A** per runbook §2: 44 cells, presets in order Config A →
   Config 1A → Config 2B → Config 3C, images IMG-1 … IMG-11 in order,
   seed `lab-ctla1`, marker-code hard-check against the table below,
   download + SHA-256 pin every delivered file.
6. **Phase B** per runbook §3: 44 real g1 grades in the same order,
   verbatim ledger. OG grades and ReMint 1.01 grades are REUSED — never
   re-graded. C2PA deny-list, visual checklist on all 44 pairs.
7. Stop conditions, ledger mechanics, and the signed declaration are
   unchanged from the runbook.

## Marker codes (unchanged, hard-check every cell)

| Preset | Required code (lab-ctla1) |
|---|---|
| Config A | `SEQ-CFA-lhbmeve33nn3` |
| Config 1A | `SEQ-1A-tpxokpv5c53f` |
| Config 2B | `SEQ-2B-vr6sikgjt3ap` |
| Config 3C | `SEQ-3C-nzzomjahxuyi` |

## Ledger note

The master engineer made one standalone verification grade (outside the
matrix, separate grade session). It does not appear in your session
counter and must NOT be entered into the matrix ledger.
