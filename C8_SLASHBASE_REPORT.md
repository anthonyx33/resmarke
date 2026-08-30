# C8 SlashBase Build Report

Date: 2026-08-30 (Australia/Sydney)  
Route: `/slashbase`

## Design rationale

SlashBase uses the established Slash/Mint visual system: dark-first navy
panels, restrained violet/cyan accents, compact sticky controls, and a complete
day palette. Compact view is a dense three-column gallery; Focus view expands
each pair for inspection, and both choices persist. Preset/version, SEQ code,
and date lead the card hierarchy while image name and scores are deliberately
smaller. Either image opens the same side-by-side lightbox. Config A, 1A, 2B,
and 3C deliberately show a plain empty state because no real rows exist for
them. Day/night, Compact/Focus, desktop, and 390 px mobile states were locally
rendered.

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

I, Codex (builder/designer), declare that I made no Supabase mutation, grading
call, grading-vendor call, live cell run, secret change, or owner-operations
change while performing this commission. The cancelled corpus-feed matrix
scope was not implemented. After the initial build, the owner explicitly
authorized publishing: commit `8709c52` was pushed and deployed on 2026-08-30.
The subsequent Compact/Focus and day/night redesign documented here was
published to GitHub only after explicit owner direction; no deployment was
performed for this redesign.

Signed: **Codex — 2026-08-30, Australia/Sydney**
