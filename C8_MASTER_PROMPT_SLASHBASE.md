# C8 MASTER PROMPT — SLASHBASE (VISUAL REAL-RESULTS PAGE)

**Supersedes and STOPS the corpus-feed matrix commission**
(`C8_MASTER_PROMPT_CORPUS_FEED_REAL_GRADE_MATRIX.md`) — that build is
cancelled. If you started it, stop and discard that scope.

Role: builder/designer (code access). You design the page. Deliverable: a
new route **`/slashbase`** — SlashBase. **No commit, no push, no deploy, no
Supabase mutation, no grading calls, no vendor calls, no live cells.** The
owner deploys after the master engineer verifies.

## 0. What SlashBase is

The visual home of REAL results. One page where every processed image shows
its before → after, with real AI-detection scores from the live Hive
connection. Nothing else.

Hard product rules from the owner:

1. **Zero mock.** No mock rows, no mock badges, no mock mode, ever. The
   page only ever shows `vendor: g1` grades. If a grade is not real, it
   does not exist on this page.
2. **Simple and visual.** Big images, big numbers. A visitor understands
   everything in five seconds. No engineering jargon — no thresholds, no
   cohorts, no H1/H0, no floors, no "cache hit" talk. Those stay in the
   engineer's layer, never on this page.
3. **No caps.** No session call cap, no remint credit cap, no corpus
   output caps on this flow. Every real grade is still written to the
   existing grade ledger as a record (history is not a cap).

## 1. Data

- Seed with the 22 REAL rows that exist today
  (`round-remint-1-01/full-corpus/ledger.jsonl`, `phase_b_grade` rows,
  `phase-b-detection-ledger.json`): 11 images × {OG, ReMint 1.01} with
  verbatim g1 grades, task ids, and file hashes. Import parser must
  **reject any row with `mock: true`** — hard fail, not a warning.
- Future rows: a **Grade** button on each card calls `grade-image` with
  provider g1 (the deployed real path). The page records the response into
  the same ledger format. No other grading path exists in the UI.

## 2. The page design (you decide the details — these are the musts)

- **Feed of cards.** One card per (image × preset). Left: the original.
  Right: the delivered result. Hover/click to enlarge, side-by-side.
- **On each side:** one big number — AI % — and a color chip:
  CLEAR / NEAR / BORDER / FAIL. Deepfake % in small text under it.
- **Card header:** image name, preset name, `SEQ-*` code, date. That's it.
- **Preset filter** across the top (Config A · 1A · 2B · 3C · ReMint 1.01
  — shown when they have real rows; ungraded presets show empty-state, not
  zeroes).
- **Stats bar:** total real grades, images covered, last grade time.
  No other numbers by default.
- The page is self-explanatory. No legend longer than one line.

## 3. No-caps implementation (owner ops + build split)

- Owner ops (not you): `GRADE_SESSION_CAP` secret set to a very large
  number (the code falls back to 40 if unset — it must be SET high, not
  removed), and remint credit gates relaxed for SlashBase-originated jobs.
- Your side: SlashBase reads/records grades without consulting any credit
  or cap state. Corpus experiment registration is not used on this page —
  jobs are regular runs, so corpus output caps cannot block anything.

## 4. Build constraints

- New route wired in `main.tsx` + new component file(s) + a small client
  module. Frozen tracked files zero-diff.
- `tsc` + `vite build` green; tests for the import parser (real-only
  enforcement: mock rows must throw).
- No automatic re-grading loops. The Grade button is one click = one real
  call, shown and ledgered.

## 5. Deliverable

`C8_SLASHBASE_REPORT.md`: design rationale (half page max), route, seed
import verification (22 rows imported, 0 mock), tests, signed declaration
of no deploy/grading/vendor action. The master engineer verifies
line-by-line, then the owner deploys.

Keep it beautiful and keep it dumb-simple. That is the brief.
