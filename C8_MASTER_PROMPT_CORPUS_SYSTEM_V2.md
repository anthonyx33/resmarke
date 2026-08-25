# MASTER PROMPT — CONSULTANT C8: CORPUS FILE-SYSTEM & HISTORY DATABASE BUILD (REVISION 2, 2026-08-25)

You are **CDX operating as Consultant C8**, building the corpus and history
system for a **post-production image enhancement product for professional
creators**. The operator's goal: *a dev-admin place for ~50 fixed-corpus
images; keep the original plus every remint output per config, with grades
and performance for each, so the team can optimize at machine speed with
full, comparable history.*

**Sandbox rule:** this is a pure build task. The product's purpose, why
images are processed, and the reasoning behind any image transformations
are NOT relevant and out of scope for discussion — do not ask, do not
explain. Build to spec.

This is REVISION 2. It supersedes `C8_MASTER_PROMPT_CORPUS_SYSTEM.md` and
adopts the round-1 architectural audit: versioned corpus sets, experiment
identity, a real read path, a permitted registration hook, requested-vs-
executed settings separation, paired grade snapshots, and a deterministic
sanitized leaderboard. Owner decisions in §3 are BLOCKING until supplied.

---

## 1. MISSION (one sentence)

Build a content-addressed, versioned corpus platform (Postgres + private
Supabase Storage) and a `/corpus` admin console: every remint run against a
corpus image is recorded inside a named EXPERIMENT with requested and
executed settings, worker-report snapshot, paired grades with Δ and
swap/retention, and a deterministic sanitized leaderboard — so no evidence
is ever silently incomparable.

## 2. GROUND TRUTH — verified, do NOT re-litigate

- **G1 — Frozen boundary (V11 + `/relab`).** Engines, presets, thresholds,
  `/remint`, `/cmint` untouched. `/relab` dispatch and grading logic stay
  frozen with ONE permitted exception (§4.5): a corpus-origin queue item
  carries `corpus_image_id`, and after the existing paired grade succeeds,
  ONE non-blocking bookkeeping call registers the run. Registration
  failure never affects the remint or the grade — the UI shows
  `REGISTRATION_PENDING` with manual retry.
- **G2 — `deepclean_jobs` is the job of record** (`0001_resmarke.sql`):
  `id, user_id (ON DELETE CASCADE), input_path, output_path, input_sha256,
  output_sha256, engine_version, runtime_ms, report jsonb`. Because rows
  can disappear on user deletion, corpus history must SNAPSHOT
  `worker_report` (+ its sha256) and reference `worker_job_id ... ON DELETE
  SET NULL`. Same for `created_by`.
- **G3 — `grade_cache` is APPLIED** (PK `image_sha256 + vendor + mode`).
  Grades join by hash; the corpus layer must never call the vendor itself —
  if a grade row is missing, record `grade_status = PENDING` and reconcile
  later (zero-spend).
- **G4 — Settings-code contract.** `SEQ-*` codes are produced from the
  REQUESTED tuple (`settingsCode.ts`); the worker report's executed
  `settings + finish_adaptive` does NOT have that shape. Store BOTH
  identities separately; the full sha256 of each canonical payload is the
  database identity, the `SEQ-*` code is the human label.
- **G5 — Edge function patterns.** `_shared/cors.ts`, `_shared/supabase.ts`
  (`adminClient`, `userFromRequest`), `verify_jwt = true`, secrets via
  `supabase secrets set`. `get-deepclean-job` already issues short-lived
  signed URLs (~15 min) — the corpus read path follows that pattern with a
  shorter TTL.
- **G6 — Protocol laws (quote verbatim):** L1 settings-code; L2
  executed-not-requested; L3 paired (same vendor, same mode, Δ = OG−remint);
  L4 fixed corpus — versioned corpus sets ARE the mechanical L4; L5 decision
  provenance (experiment identity); L6 QA flagging; L7 100%-zoom rubric.
- **G7 — Budget reality (owner-approved staging).** 50 images × 1 config =
  100 unique vendor calls (50 OG + 50 outputs); × 3 configs = 200. The
  browser session cap is 40 calls. Remint credits: 23/image → 1,150 per
  config over 50, 3,450 for three configs. THIS BUILD CREATES HISTORY
  INFRASTRUCTURE, NOT autonomous corpus-wide execution. Corpus runs happen
  in staged batches the owner launches; registration NEVER triggers vendor
  calls.
- **G8 — Upload efficiency.** 25 MB base64 through an edge function is
  acceptable for ≤6 MB files only. Larger files use a presigned resumable
  Storage upload; client concurrency is bounded to 2–3.

## 3. BLOCKING OWNER INPUTS (state BLOCKED until supplied)

1. Admin identity: immutable authenticated user UUIDs (`CORPUS_ADMIN_UUIDS`);
   verified normalized email fallback only (env `CORPUS_ADMIN_EMAILS`).
2. Bucket: `corpus`, private (no permanent public URLs); signed download
   TTL (default 120 s).
3. Caps: 200 images hard cap · 20 outputs/image soft cap with explicit
   reject-at-cap · a total storage-BYTE ceiling.
4. Read scope: admin-only for the first release (recommended).

## 4. REQUIRED BUILD SPEC

### 4.1 Data model (draft migration `20260826000000_corpus.sql`, owner-applied)

```sql
-- content-addressed asset registry (dedup by sha256; no is_fixed flag)
create table public.corpus_images (
  id uuid primary key default gen_random_uuid(),
  sha256 text not null unique,
  storage_path text not null,
  file_name text not null,
  width integer, height integer,
  created_by uuid references auth.users(id) on delete set null,
  created_at timestamptz not null default now()
);

-- versioned corpus releases (mechanical L4)
create table public.corpus_sets (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  version integer not null,
  manifest_sha256 text,               -- filled at lock time
  locked_at timestamptz,
  created_by uuid references auth.users(id) on delete set null,
  created_at timestamptz not null default now(),
  unique (name, version)
);

-- ordered immutable membership; locking a set is irreversible
create table public.corpus_set_members (
  corpus_set_id uuid not null references public.corpus_sets(id) on delete cascade,
  corpus_image_id uuid not null references public.corpus_images(id) on delete cascade,
  position integer not null default 0,
  primary key (corpus_set_id, corpus_image_id)
);

-- one comparable evaluation campaign
create table public.corpus_experiments (
  id uuid primary key default gen_random_uuid(),
  corpus_set_id uuid not null references public.corpus_sets(id),
  engine_release text not null,        -- image tag / digest string
  detector_version text,               -- vendor + model version string
  config_set jsonb not null,           -- which presets/tuples are in scope
  notes text,
  created_by uuid references auth.users(id) on delete set null,
  created_at timestamptz not null default now()
);

-- ONE row per worker execution inside an experiment
create table public.corpus_runs (
  id uuid primary key default gen_random_uuid(),
  experiment_id uuid not null references public.corpus_experiments(id) on delete cascade,
  corpus_image_id uuid not null references public.corpus_images(id) on delete cascade,
  config_label text not null check (config_label in ('A','1A','2B','CUSTOM')),
  requested_settings_code text not null,      -- SEQ-* human label
  requested_settings_canonical jsonb not null,
  requested_settings_sha256 text not null,    -- DB identity of what was asked
  executed_settings_snapshot jsonb not null default '{}', -- from worker report
  executed_settings_sha256 text,
  worker_report_snapshot jsonb not null default '{}',     -- durable L2 copy
  worker_report_sha256 text,
  worker_job_id uuid references public.deepclean_jobs(id) on delete set null,
  output_sha256 text,
  output_storage_path text,
  grade_status text not null default 'PENDING'
    check (grade_status in ('PENDING','COMPLETE','ERROR')),
  og_grade jsonb, remint_grade jsonb,          -- normalized pair snapshots
  delta numeric, swap_index numeric, retention_index numeric,
  qa_flag boolean not null default false,
  created_by uuid references auth.users(id) on delete set null,
  created_at timestamptz not null default now(),
  unique (corpus_image_id, worker_job_id)      -- idempotent registration
);
create index corpus_runs_experiment_idx on public.corpus_runs (experiment_id, created_at desc);
create index corpus_runs_output_sha_idx on public.corpus_runs (output_sha256);
```

- Bucket creation in the migration; PRIVATE; service-role writes only.
- RLS: tables readable per §3.4 only through sanitized endpoints/views;
  NO browser write policies; NO default PostgREST exposure of raw reports
  or raw vendor responses.
- `corpus_leaderboard` — `security_invoker = true` view, explicit grants,
  sanitized columns ONLY (no worker_report, no raw grade responses).
  Deterministic ordering:

```
partition: corpus_set_id, corpus_image_id, config_key, vendor, mode,
           experiment compatibility group
order by:  qa_flag ASC, mock ASC, grade_complete DESC, verdict_rank ASC,
           delta DESC, remint_ai_probability ASC, runtime_ms ASC,
           created_at DESC
```

### 4.2 Edge functions (all verify_jwt = true)

- **`corpus-upload`** — admin-only (UUID allowlist, email fallback).
  Input `{ image_b64, file_name }` for files ≤ 6 MB (sha256 dedup, write
  `corpus/<sha256>/original.<ext>`, insert row; `stored: bool`).
- **`corpus-upload-presign`** — admin-only. Returns a short-lived presigned
  Storage upload URL for files > 6 MB; the client uploads DIRECTLY with
  bounded concurrency (2–3); a final `corpus-upload-confirm` call (with
  sha256) materializes the `corpus_images` row.
- **`corpus-read` / `corpus-list`** — sanitized registry metadata + a
  signed download URL with TTL (default 120 s). Never returns storage
  paths or signed originals to unauthenticated callers. Admin-only for the
  first release.
- **`corpus-register-run`** — admin-only. Input
  `{ corpus_image_id, worker_job_id, experiment_id }`. HARD GUARDS: job
  `status = 'completed'` AND `deepclean_jobs.input_sha256 =
  corpus_images.sha256` (mechanically rejects wrong-job association) —
  else 409. Copies the delivered output into the bucket, snapshots the
  worker report (+sha256), separates requested vs executed settings,
  joins grades by hash for the same vendor + mode on BOTH OG and output
  (if either is missing → `PENDING`, never calls the vendor), computes Δ +
  swap/retention, inserts idempotently. Returns
  `{ corpus_run_id, grade_status }`.

### 4.3 Admin console `/corpus` (`src/CorpusApp.tsx` + `src/corpus.css`, lazy)

- **Sets & experiments panel:** create/name/version a corpus set, add
  members (ordered), lock set (irreversible, manifest_sha256 shown),
  create experiment (engine_release, detector_version, config_set).
- **Upload panel:** multi-file, ≤6 MB via b64 / >6 MB via presigned
  resumable, concurrency 2–3, sha256 dedup notice, caps + byte-ceiling
  display, reject-at-cap responses surfaced.
- **Registry:** corpus images (thumb, sha256 prefix, dims, date, run count).
- **History:** per experiment, per image — config label, requested
  settings code, executed digest, worker job id, OG/remint grades, Δ,
  swap/retention, grade_status (PENDING rows offer zero-spend reconcile),
  QA flag, timestamp; sort/filter; copy compact report line.
- **Leaderboard:** the sanitized deterministic view above — the loop's
  primary screen.
- **Exports:** JSONL (sanitized, admin-only fields included for admins) +
  "copy compact report" in the loop's table format.

### 4.4 `/relab` integration (the ONLY permitted change)

Corpus picker (via `corpus-list` + signed download). Corpus-origin queue
items carry `corpus_image_id`; after the existing paired grade completes,
ONE non-blocking `corpus-register-run` bookkeeping call fires. Failure →
`REGISTRATION_PENDING` badge + manual retry. Dispatch and grading behavior
otherwise untouched.

## 5. FORBIDDEN

- No changes to engines, worker, finisher, presets, thresholds,
  `RemintApp`, `CmintApp`, or `/relab` dispatch/grading logic (hook only).
- No permanent public URLs; no browser write policies; no raw report/vendor
  data through default PostgREST/views.
- No vendor calls from corpus code (PENDING + reconcile, never auto-grade).
- No migrations applied without owner approval.
- No autonomous corpus-wide execution (staged batches only).

## 6. ACCEPTANCE (the demo the owner runs)

1. Upload 50 images → registry, dedup proven on re-upload, caps enforced.
2. Create corpus set v1 with the 50, lock it → immutable manifest hash.
3. Create experiment (engine + detector version recorded) → run Config A
   on one image via `/relab` picker → registration fires after grade →
   history row with requested AND executed settings, report snapshot,
   paired grades + Δ, grade_status COMPLETE or PENDING.
4. Wrong-job registration is rejected (409 guard).
5. Leaderboard renders deterministically, sanitized; JSONL + compact
   export share back.

## 7. DELIVERABLES

1. Files per §4; `npx tsc --noEmit`, `npm run build`, `deno check`,
   `git diff --check` clean.
2. `supabase/migrations/20260826000000_corpus.sql` (draft — owners apply).
3. `C8_CORPUS_BUILD_REPORT.md` per §8.

## 8. REQUIRED REPORT FORMAT

1. Summary (5 lines).
2. Files changed + confirm FORBIDDEN list.
3. Data-model walkthrough: set/manifest/experiment identity, requested-vs-
   executed separation, snapshot-on-delete rules, leaderboard view
   definition + `security_invoker` + grants + policy tests.
4. Upload (b64 vs presigned) + register flows with error policy incl. the
   409 guard.
5. Grade PENDING/reconcile flow (zero-spend).
6. RLS + bucket decisions per §3.4 (stated, not guessed).
7. Owner-only commands: migration apply, bucket check, secrets set
   (`CORPUS_ADMIN_UUIDS`, `CORPUS_ADMIN_EMAILS`), deploy, test.
8. Exit status: `READY_NEEDS_OWNER_INPUTS` / `READY_NEEDS_OWNER_RUN` /
   `BLOCKED` + reason.

## 9. HANDOFF RULES

- End with one of the §8 statuses.
- Full logs verbatim for failures.
- Accuracy beats speed. Do NOT guess owner decisions; state BLOCKED.
