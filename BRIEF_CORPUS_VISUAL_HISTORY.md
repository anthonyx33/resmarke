# BRIEF — CORPUS VISUAL RUN HISTORY (before/after browser)

Date: 2026-08-26 · Master engineer · for C8 (or Flash) build
Sibling: `EXPERT_TESTING_SYSTEM.md`, `C8_MASTER_PROMPT_LAB_PILOT.md`

## 0. Mission

Give the owner a **visual track record** of every remint run: an 80×80 preview
grid across ALL experiments and images, each clickable into a full-size
before/after viewer with the run's settings, grades, and metadata. Server-backed —
never browser-local.

## 1. Current facts (verified, do not re-litigate)

- Data already exists: `corpus_runs` (67 rows: settings code/canonical, worker
  report snapshot, input/output sha256, grades, config_label), `corpus_run_intents`,
  `corpus_leaderboard` view, `corpus_images` (originals, sha256 unique),
  `corpus_experiments` (2), locked set "Fixed corpus v1".
- Images: originals in bucket `corpus/<sha>/original` (content-addressed), outputs
  in `corpus/<sha>/outputs/<hash>.jpg`. `/corpus` already renders signed URLs for
  outputs (TTL 120 s pattern in `corpus-read`/existing Run history links).
- The current Run history table is text-only, filtered to ONE selected image.
- The `/relab` "Detection-only ledger" is localStorage — do NOT touch it.

## 2. Build requirements

### A. Server: new edge function `corpus-run-history` (admin-only, verify_jwt)
- Input: optional `experiment_id`, `corpus_image_id`, `config_label`, `limit` (≤100), `offset`.
- Returns run rows across ALL experiments by default, newest first, each with:
  `run_id, created_at, config_label, config_key, settings_code, requested_settings_canonical,
  og_sha256, output_sha256, og_grade {ai_probability, verdict...}, remint_grade {...}, delta,
  verdict, qa_flag, mock, engine_version/release, job_id`
  plus **signed URLs**: `og_url` (original object, 120 s) and `output_url` (output object, 120 s).
- Use the existing signed-URL helper pattern from `corpus-read`/`corpus-register-run`; no new storage buckets; no vendor calls; no caching of signed URLs beyond response lifetime.

### B. Client: CorpusApp "Run history" upgrade
- New panel **"Visual history"** (or upgrade Run history): server rows from A.
- Grid rows: **80×80 OG thumbnail** + **80×80 remint thumbnail** + `config_label` chip +
  settings code (short) + `OG% → RM%` + verdict badge + timestamp.
- Click a row → **modal**: side-by-side full-size OG vs remint (fit-to-viewport,
  toggle "swap/overlay" optional), below: full settings code, canonical settings JSON
  (collapsed), both grade breakdowns, swap/retention, verdict/QA flag, run id + job id,
  buttons: "Open output", "Copy compact report line".
- Filters: experiment (All + each), image (All + 11), config (All/A/1A/2B/3C/CUSTOM).
- Pagination: 20/page; lazy-load images; thumbnails via CSS scaling of the signed URLs.
- Empty/loading/error states; admin-only (already enforced server-side).

### C. (Optional, separate approval) One-click round runner
- `/relab` "Run full corpus with current preset" button: adds all 11 locked images to the
  queue with the selected preset + optional lab seed. Queue cap is 20 — 11 fits. Mark as
  OPTIONAL in the build report; owner approves separately.

## 3. Forbidden (zero diff)

`src/RemintApp.tsx`, `src/CmintApp.tsx`, all CSS except new CorpusApp styles within
`src/corpus` conventions, `dispatch-deepclean-job/**`, `grade-image/**`,
`get-deepclean-job/**`, `supabase/migrations/**`, all worker Python files,
`IMG-REMINT-v1/`.

## 4. Acceptance gates (master engineer verifies before any deploy)

1. `npx tsc --noEmit` + `npm run build` green; deno check on new function; `git diff --check`.
2. Forbidden-list zero diff.
3. New function returns the 67 existing rows with valid signed URLs; pagination and filters correct.
4. Browser smoke: grid renders 80×80 thumbnails; modal opens full before/after for a pilot row (e.g. 3C `SEQ-3C-nzzomjahxuyi`); no vendor call, no credit change.
5. No commit/push/deploy by the builder. `README`-style notes in the build report only.

## 5. Deliverables

- `corpus-run-history/index.ts` (+ `_shared` reuse, no new dependencies)
- CorpusApp visual history panel + modal
- Build report: files changed, validation log, screenshots of grid + modal
- No commit; master engineer verifies and commits.
