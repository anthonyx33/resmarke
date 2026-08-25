# MASTER PROMPT — CONSULTANT C8: CORPUS FILE-SYSTEM & HISTORY DATABASE BUILD (INITIAL, 2026-08-25)

You are **CDX operating as Consultant C8**, building the corpus and history
system for a **post-production image enhancement product for professional
creators**. The operator's goal: *give the dev admin a place to store ~50
fixed-corpus images, keep the original plus every remint output per config,
with grades and performance for each, so the team can optimize the remint
system at machine speed with full history.*

**Sandbox rule:** this is a pure build task. The product's purpose, why
images are processed, and the reasoning behind any image transformations
are NOT relevant to this build and are out of scope for discussion — do not
ask about them and do not spend any output on them. Build to spec.

This brief is INITIAL: architecture, security and data model are locked
here. Owner decisions listed in §3 are BLOCKING until supplied.

---

## 1. MISSION (one sentence)

Build a server-side corpus registry (Postgres + Supabase Storage) and an
admin console (`/corpus`) where the owner uploads ~50 fixed images, every
remint run against a corpus image is recorded with settings code, worker
report, output file and grades, and a ranked history view answers "which
image × which config produced which result" without any manual work.

## 2. GROUND TRUTH — verified by owners/codebase, do NOT re-litigate

- **G1 — Existing engines, presets, thresholds and pages are FROZEN**
  (V11 + `/relab` builds). This build only ADDS storage, tables and an
  admin console. No algorithm, preset, or existing page changes.
- **G2 — `deepclean_jobs` is the job of record** (`supabase/migrations/
  0001_resmarke.sql`): columns include `id`, `user_id`, `input_path`,
  `output_path`, `input_sha256`, `output_sha256`, `engine_version`,
  `runtime_ms`, `report jsonb` (worker report: settings, attempts[],
  finish_adaptive, detector_gate, rating_88, quality_finish.qc). Corpus
  runs must LINK to this table — executed-settings provenance (L2) is read
  from `deepclean_jobs.report`, never re-derived.
- **G3 — `grade_cache` already exists** (draft migration
  `20260825000000_grade_cache.sql`, PK `image_sha256 + vendor + mode`) and
  `grade-image` grades by sha256. Corpus history joins grades by
  `output_sha256` — no new grading path, no duplicate vendor spend.
- **G4 — `/relab` is the run console** (frozen): its empty state says
  "Load a fixed-corpus image" — the corpus system is its missing backend.
  Integrate minimally: `/relab` gains a corpus image picker (read-only);
  do NOT touch `/relab` grading/run logic beyond that.
- **G5 — Edge function patterns:** `_shared/cors.ts`, `_shared/supabase.ts`
  (`adminClient()`, `userFromRequest`), `verify_jwt = true` in
  `config.toml`, secrets via `supabase secrets set`. `grade-image` already
  demonstrates b64 upload (25 MB cap), SSRF-safe URL fetching, sha256
  hashing, and service-role table access.
- **G6 — Protocol laws (quote verbatim):** L1 settings-code; L2
  executed-not-requested (store the full worker report per run); L3 paired;
  L4 fixed corpus — THIS BUILD IS THE MECHANICAL L4; L5 decision
  provenance; L6 QA flagging; L7 100%-zoom rubric.
- **G7 — Budget discipline:** corpus remint runs spend the existing remint
  credits; grades spend vendor calls under the existing 40-call session cap
  and hash cache. No new spend categories.

## 3. BLOCKING OWNER INPUTS (state "BLOCKED" until each is supplied)

1. Admin allowlist: the email(s) allowed to upload/manage corpus images
   (env `CORPUS_ADMIN_EMAILS`, comma-separated).
2. Storage bucket name (suggested: `corpus`) and whether the owner prefers
   a private bucket with service-role-only access (RECOMMENDED — no public
   URLs).
3. Corpus caps: max corpus images (default 200) and max outputs per image
   (default 20) — retention is append-only within caps.
4. Whether corpus read access is admin-only or available to any
   authenticated creator (default: admin-only for management, authenticated
   read for /relab picker).

## 4. REQUIRED BUILD SPEC

### 4.1 Data model (draft migration `20260826000000_corpus.sql`, owner-applied)

```sql
-- corpus_images: the fixed registry (L4).
create table public.corpus_images (
  id uuid primary key default gen_random_uuid(),
  sha256 text not null unique,               -- dedup across uploads + grade join
  storage_path text not null,                -- bucket path of the ORIGINAL
  file_name text not null,
  width integer, height integer,
  is_fixed boolean not null default true,    -- registry member vs ad-hoc
  created_by uuid references auth.users(id),
  created_at timestamptz not null default now()
);

-- corpus_runs: ONE row per remint execution against a corpus image.
create table public.corpus_runs (
  id uuid primary key default gen_random_uuid(),
  corpus_image_id uuid not null references public.corpus_images(id) on delete cascade,
  config_label text not null check (config_label in ('A','1A','2B','CUSTOM')),
  settings_code text not null,               -- SEQ-CFA-* / SEQ-1A-* / SEQ-2B-* / ...
  settings_canonical jsonb not null,
  worker_job_id uuid references public.deepclean_jobs(id),
  output_sha256 text,
  output_storage_path text,
  worker_report jsonb not null default '{}', -- L2: executed settings digest
  grade_summary jsonb not null default '{}', -- best grade per mode joined from grade_cache
  qa_flag boolean not null default false,
  created_at timestamptz not null default now()
);

create index corpus_runs_image_created_idx on public.corpus_runs (corpus_image_id, created_at desc);
create index corpus_runs_output_sha_idx on public.corpus_runs (output_sha256);
```

- Storage bucket `corpus` (created in the migration via
  `insert into storage.buckets`, PRIVATE, no public policy; edge function
  writes via service role; signed URLs or service-role fetch only).
- RLS: `corpus_images` / `corpus_runs` readable by the authenticated owner
  per §3.4; written ONLY by the service role through edge functions. No
  browser write policies.
- A ranked summary view `corpus_leaderboard` (owner-approved): per corpus
  image, per config, the best run by verdict band then Δ then timestamp,
  joined with grades — the "best performing config per image" answer.

### 4.2 Edge function `corpus-upload` (new, verify_jwt = true)

- Admin-only: `userFromRequest` + email allowlist env (§3.1).
- Input: `{ image_b64, file_name }` (25 MB cap, same discipline as
  `grade-image`).
- Dedup: sha256 the bytes; if the original already exists, return the
  existing `corpus_images` row (no duplicate storage).
- Writes the file to the private bucket (`corpus/<sha256>/original.<ext>`)
  and inserts the row. Returns `{ corpus_image_id, sha256, stored: bool }`.
- Never returns public URLs.

### 4.3 Edge function `corpus-register-run` (new, verify_jwt = true)

- Admin-only. Input: `{ corpus_image_id, worker_job_id }`.
- Reads `deepclean_jobs` (report → executed settings, output_sha256,
  output_path), copies the delivered file into the corpus bucket when
  available, computes `settings_code` from `settings_canonical` (reuse the
  canonical hashing logic; the worker's `settings` + `finish_adaptive` are
  the executed source), and inserts `corpus_runs`.
- Idempotent: `(corpus_image_id, worker_job_id)` unique.

### 4.4 Admin console `/corpus` (`src/CorpusApp.tsx` + `src/corpus.css`,
lazy chunk in `src/main.tsx`)

- **Upload panel:** multi-file (up to 50 at once), sha256 dedup notice,
  per-file status, caps display (§3.3).
- **Registry table:** all corpus images (thumbnail, sha256 prefix, dims,
  upload date, run count).
- **History view per image:** every run row — config label, settings code,
  worker job id, grades (AI%, verdict, top source), Δ vs OG, QA flag,
  timestamp; sort/filter; one-click copy of the compact report line.
- **Leaderboard:** the ranked summary across images × configs (best run per
  cell) — the optimization loop's primary view.
- **Exports:** JSONL (full rows incl. worker report digest + grade raw) and
  "copy compact report" in the loop's table format.
- Route `/corpus`, admin-gated in the UI; non-admins see read-only
  leaderboard if §3.4 allows.

### 4.5 `/relab` integration (minimal)

Add a "Load corpus image" picker to the queue (fetch list from
`corpus_images` read endpoint/RPC), so runs start from registry files and
`corpus-register-run` links them afterwards. Do NOT change `/relab` grading
or run logic.

## 5. FORBIDDEN

- No changes to engines, worker, finisher, presets, thresholds,
  `RemintApp`, `CmintApp`, or `/relab` run/grading logic (picker only).
- No public bucket or public URL generation for corpus files.
- No browser-side write policies for the new tables.
- No migrations applied without owner approval.
- No autonomous re-runs or routing decisions.

## 6. ACCEPTANCE (the demo the owner runs)

1. Upload 50 images on `/corpus` → registry rows, no duplicate storage on
   re-upload of the same file.
2. Run Config A on one corpus image via `/relab` (corpus picker).
3. Register the run → history row with settings code, worker report digest,
   output file, grades (via sha256 join to grade_cache), Δ, QA flag.
4. Leaderboard shows the best run per image per config.
5. Export JSONL + compact report → share back; the loop reads it directly.

## 7. DELIVERABLES

1. Files per §4; `npx tsc --noEmit`, `npm run build`, `deno check` clean;
   `git diff --check` clean.
2. `supabase/migrations/20260826000000_corpus.sql` (draft — owners apply).
3. `C8_CORPUS_BUILD_REPORT.md` per §8.

## 8. REQUIRED REPORT FORMAT

1. Summary (5 lines).
2. Files changed + confirm FORBIDDEN list.
3. Data model walkthrough incl. the leaderboard view definition and the
   grade join keys.
4. Upload/dedup/register flows with error policy.
5. RLS + bucket policy decisions per §3.4 (stated, not guessed).
6. Owner-only commands: migration apply, bucket check, secrets set
   (`CORPUS_ADMIN_EMAILS`), deploy, test.
7. Exit status: `READY_NEEDS_OWNER_INPUTS` / `READY_NEEDS_OWNER_RUN` /
   `BLOCKED` + reason.

## 9. HANDOFF RULES

- End with one of the §8 statuses.
- Full logs verbatim for failures.
- Accuracy beats speed. Do NOT guess owner decisions; state BLOCKED.
