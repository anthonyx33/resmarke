# C8 MASTER PROMPT — CORPUS FEED + REAL-GRADE MATRIX (RECALIBRATION DASHBOARD)

Role: builder (code access). Deliverable: a visual corpus feed dashboard +
per-image per-preset real-grade stats matrix, plus a migration draft the
owner applies. **No commit, no push, no deploy, no Supabase mutation, no
grading, no vendor calls, no live cells.** The owner deploys; the operator
populates data only through authorized legs.

## 0. Why now (context you must build against)

- The real Hive provider (`GRADE_PROVIDER=g1`) is now LIVE. The first 22
  real grades exist (`round-remint-1-01/full-corpus/ledger.jsonl`,
  `phase-b-detection-ledger.json`): 11 OG sources + 11 ReMint 1.01
  delivered files, all `vendor: g1`, hash-pinned.
- **All previous MOCK grades are detection-meaningless** (measured: MOCK
  called IMG-5/6/7 CLEAR where the real vendor FAILs). The dashboard must
  therefore treat mock rows as mechanics-only and never mix them with real
  grades. MOCK rows must be visibly labeled or excluded from detection
  stats.
- The owner's directive: visual before/after feed for every processed
  image, and real results recorded from scratch for every preset.

## 1. Data model (draft tables/views — owner applies migration)

One row per (corpus image × preset × role):

- `role`: `og` | `rm`
- `image`: source file identity (sha256 + file name + dims)
- `preset`: settings label + `SEQ-*` settings code + seed
- `job_id`: deepclean job id (for rm rows); null for og
- `grade`: vendor (`g1`), `mock` flag, `ai_probability`,
  `deepfake_probability`, `flux_family` sum, verdict, top_source,
  `task_id`, `provider_calls`, `cache_hit`, timestamp
- `quality`: frozen recipe metrics computed by the master engineer
  (`h1_energy_ratio`, `h0/h2_energy_ratio`, `texture_h1_energy`,
  `protected_eatr_ratio_vs_A0`, texture luma/chroma residual, staircase)
- `files`: delivered/original storage refs + sha256
- `ledger_ref`: pointer to the authoritative ledger row

Requirements:
- Rows must support **regular /relab runs** (no corpus experiment
  registration) — IMG-5/6 are at the 20-output corpus cap and future rows
  will be regular runs.
- Hash-pin every file reference; the dashboard verifies sha on render where
  possible and shows a mismatch badge otherwise.
- No grading logic in the dashboard: all grades come from `grade-image`
  with the freeze-v3 ledger. The dashboard is read + import only.

## 2. Import of existing real data

- Import the 22 `phase_b_grade` ledger rows as seed rows (IMG-1..11 ×
  {OG, RM 1.01}), with their verbatim grades, task ids, and cache-hit
  provenance.
- Import the 11 delivered quality metrics from
  `round-remint-1-01/full-corpus/floors-1.01-live.json` for the RM rows.

## 3. UI (the feed)

- **Feed view:** grid of before/after pairs (OG left, RM right), hover/
  click to enlarge, per-pair header: image name, preset, settings code,
  real-grade deltas (OG AI → RM AI, verdict arrows), flux-family, quality
  badge (floors pass/fail per frozen values).
- **Matrix view:** table — rows = 11 corpus images, columns = presets
  (Config A, 1A, 2B, 3C, ReMint 1.01 as they get graded); cells show
  real AI%, verdict chip (CLEAR/NEAR/BORDER/FAIL), df%, flux-family;
  per-preset column footer = thresholds-pass count + non-amplification
  count. Ungraded cells show "—" (never a mock value).
- **Filter:** mock vs real toggle (default: real only for detection stats).
- **Stats bar:** calls ledger (vendor calls used / cap), grades returned,
  cache hits, last leg timestamp.

## 4. Build constraints (hard)

- Frozen tracked files zero-diff. New files only: frontend route/component,
  `src/lib/corpusFeedClient.ts`, `supabase/functions/_shared/*` additions,
  migration SQL under `supabase/migrations/` (owner applies).
- No network call to any vendor. No automatic re-grading. No threshold
  changes. The 40-call governance stays exactly as written.
- `deno test` for identity/schema code, `tsc` + `vite build` green, tests
  for the import parser against the real phase-b ledger file.

## 5. Deliverable

`C8_CORPUS_FEED_REPORT.md`: schema, seed-import results (row counts and
hash checks against the ledger), UI screens, tests, signed declaration
that no deploy/grading/vendor action occurred. The master engineer
verifies line-by-line before the owner deploys.

## 6. Out of scope (do not build)

Auto-grading loops, preset changes, detection logic, vendor failover,
budget changes. Population happens only through master-engineer-authorized
operator legs.

Signed, for the record: the builder receives this prompt unmodified.
