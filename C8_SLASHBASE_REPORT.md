# C8 SlashBase Build Report

Date: 2026-08-30 (Australia/Sydney)  
Route: `/slashbase`

## Design rationale

SlashBase is built as a high-contrast editorial gallery: a short promise, a
three-item stats bar, one horizontal preset filter, then large before/after
cards. Warm paper, black type, and a single acid-green accent keep attention on
the images; verdict colour is reserved for CLEAR / NEAR / BORDER / FAIL. Each
card header contains only image name, preset, SEQ code, and date. Both sides
show one dominant AI percentage with deepfake percentage beneath, and either
image opens the same side-by-side lightbox. Config A, 1A, 2B, and 3C deliberately
show a plain empty state because no real rows exist for them. Desktop and mobile
were locally rendered at 1440 px and 390 px widths.

## Implementation

- `src/main.tsx` lazy-loads `SlashBaseApp` for `/slashbase` and nested paths.
- `src/SlashBaseApp.tsx`, `src/slashbase.css`, and `src/slashbaseData.ts` provide
  the feed, filters, stats, paired assets, responsive layout, and lightbox.
- `src/lib/slashbaseSeed.ts` imports only `phase_b_grade` rows and fails the
  complete import if an imported row is mock, non-`g1`, or non-real.
- `src/lib/slashbaseClient.ts` has the only UI grading path. One explicit Grade
  click makes one `grade-image` invocation with `provider: "g1"` and `mode:
  "real"`; the response must be `vendor: "g1"`, `mock: false`, and contain a
  valid task id before it is displayed or appended in the existing
  detection-only ledger format.
- The page reads no credit state, session-cap value, corpus registration, or
  corpus output limit. It contains no timer, polling loop, or automatic grade
  trigger.

## Seed import verification

The canonical `round-remint-1-01/full-corpus/ledger.jsonl` import and
`phase-b-detection-ledger.json` cross-check produced:

| Check | Result |
|---|---:|
| Imported real grade rows | 22 |
| Images | 11 |
| Original rows | 11 |
| ReMint 1.01 rows | 11 |
| `vendor: g1` | 22 |
| `mock: true` | 0 |
| Hash/task matches in full detection ledger | 22/22 |
| SEQ code | `SEQ-1.01-yg63qja3got4` (22/22) |

The detection ledger contains one earlier real verification record in addition
to the 22 page rows; timestamp + file hash + task id matching prevents that
record from being double-imported.

## Verification

- `npm test` — PASS, 3/3. Covers the 22-row artifact cross-check and hard-fail
  cases for mock phase rows and mock detection rows.
- `npm run check` — PASS (`tsc --noEmit`).
- `npm run build` — PASS (`tsc && vite build`, Vite 7.3.6, 1,822 modules).
- `git diff --check` — PASS.
- Frozen tracked worker, grading-function, grader-client, grade-ledger, and
  corpus UI files — zero diff.

## Signed declaration

I, Codex (builder/designer), declare that I made no commit, push, deployment,
Supabase mutation, grading call, grading-vendor call, or live cell run while
performing this commission. I did not change secrets or owner operations. The
cancelled corpus-feed matrix scope was not implemented. Only local source
inspection, parser/tests, compilation, production build, and local visual
rendering were performed.

Signed: **Codex — 2026-08-30, Australia/Sydney**
