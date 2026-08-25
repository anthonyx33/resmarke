# MASTER PROMPT — CONSULTANT C8: CORPUS FILE-SYSTEM & HISTORY DATABASE BUILD (V2.1 FINAL AMENDMENT, 2026-08-25)

You are **CDX operating as Consultant C8**, building the corpus and history
system for a **post-production image enhancement product for professional
creators**. **Sandbox rule:** pure build task — the product's purpose and
why images are processed are irrelevant; do not ask, do not explain.

This V2.1 FINAL AMENDMENT closes the six contract gaps from the round-2
audit. It supersedes `C8_MASTER_PROMPT_CORPUS_SYSTEM_V2.md`; everything in
V2 that is not amended here still applies (mission, ground truth G1–G8,
owner inputs §3, acceptance, deliverables, report format, handoff).

---

## A. THE SIX CONTRACT FIXES (normative)

### A1. Authoritative requested settings — server-side RUN INTENT

New edge function **`corpus-run-intent`** (admin-only, verify_jwt) called by
`/relab` BEFORE dispatch for corpus-origin queue items:

- Input: `{ corpus_image_id, experiment_id, config_label,
  requested_settings_code, requested_settings_canonical }`.
- Server verifies: experiment exists AND its corpus set is LOCKED AND the
  image is a member of that set (§A2) — else 409.
- Server computes `requested_settings_sha256` from the canonical payload
  (never trusts a client hash) and inserts a `corpus_run_intents` row:

```sql
create table public.corpus_run_intents (
  id uuid primary key default gen_random_uuid(),
  experiment_id uuid not null references public.corpus_experiments(id) on delete restrict,
  corpus_image_id uuid not null references public.corpus_images(id) on delete restrict,
  config_label text not null,
  config_key text not null,
  requested_settings_code text not null,
  requested_settings_canonical jsonb not null,
  requested_settings_sha256 text not null,
  created_by uuid references auth.users(id) on delete set null,
  created_at timestamptz not null default now()
);
```

- Returns `intent_id`. `corpus-register-run` then takes
  `{ intent_id, worker_job_id }` (NOT raw requested fields) and copies the
  requested identity verbatim from the intent — the requested tuple has ONE
  authoritative source.

### A2. Locked corpus sets are mechanically immutable

- `corpus_set_members`: add `unique (corpus_set_id, position)`.
- **`lock_corpus_set(set_id)`** SECURITY DEFINER RPC, one transaction:
  requires ≥ 1 member; canonicalizes positions to dense 1..N ordered by
  (position, corpus_image_id); computes
  `manifest_sha256 = sha256(canonical ordered JSON of sha256s)`; sets
  `locked_at = now()`. Cannot run twice; cannot run on an empty set.
- **TRIGGERS:** after a set is locked, any INSERT/UPDATE/DELETE on its
  `corpus_set_members` rows raises an exception. Membership changes are
  only possible by creating a NEW set version.
- **Experiments must reference locked sets:** an INSERT trigger on
  `corpus_experiments` rejects rows whose set has `locked_at IS NULL`.
- **Run membership invariant:** registration asserts the run's image is a
  member of the experiment's locked set (already checked at intent time;
  re-checked at registration).

### A3. Grade reconciliation is an explicit contract

New edge function **`corpus-reconcile-grades`** (admin-only, verify_jwt):

- Input: `{ experiment_id? , run_ids? }` (at least one).
- For every matching run with `grade_status IN ('PENDING','ERROR')`: read
  `grade_cache` by `(image_sha256, vendor, mode)` for the OG hash AND by
  `(output_sha256, vendor, mode)` for the output hash using the
  experiment's `detector_vendor` + `detector_mode` (§A4). When both rows
  exist: snapshot `og_grade` / `remint_grade`, recompute `delta`,
  `swap_index`, `retention_index`, set `grade_status = 'COMPLETE'`.
- NEVER calls the vendor. NEVER touches requested/executed/provenance
  fields. Idempotent; returns `{ completed: n, still_pending: m }`.

### A4. Structured detector identity + a real leaderboard SQL

`corpus_experiments` replaces the single `detector_version` string with:

```sql
detector_vendor text not null default 'g1',
detector_mode   text not null default 'real',   -- sdxl | flux_schnell | real
detector_model  text,                           -- e.g. 'ai_generated_media'
detector_version text                           -- model version string
```

`corpus_runs` adds `config_key text not null` (='config_label' for A/1A/2B;
else the canonical config key). **Compatibility key** =
`(engine_release, detector_vendor, detector_mode, detector_model,
detector_version)` — runs with different keys are never ranked together.

`corpus_leaderboard` — ACTUAL SQL, `security_invoker = true`, sanitized
columns only (no worker_report, no raw grades):

```sql
create view public.corpus_leaderboard with (security_invoker = true) as
select distinct on (e.corpus_set_id, r.corpus_image_id, r.config_key,
                    e.detector_vendor, e.detector_mode,
                    e.engine_release, e.detector_model, e.detector_version)
  r.id as corpus_run_id,
  r.corpus_image_id,
  e.corpus_set_id,
  e.engine_release, e.detector_vendor, e.detector_mode,
  e.detector_model, e.detector_version,
  r.config_label, r.config_key,
  r.grade_status,
  r.qa_flag,
  (r.og_grade->>'ai_probability')::double precision as og_ai,
  (r.remint_grade->>'ai_probability')::double precision as remint_ai,
  r.delta,
  (r.og_grade->>'verdict') as og_verdict,
  (r.remint_grade->>'verdict') as remint_verdict,
  r.created_at
from public.corpus_runs r
join public.corpus_experiments e on e.id = r.experiment_id
order by e.corpus_set_id, r.corpus_image_id, r.config_key,
         e.detector_vendor, e.detector_mode, e.engine_release,
         e.detector_model, e.detector_version,
         r.qa_flag asc, r.grade_status = 'COMPLETE' desc,
         case r.remint_grade->>'verdict'
           when 'CLEAR' then 0 when 'NEAR' then 1 when 'BORDER' then 2 else 3 end,
         r.delta desc nulls last, r.remint_ai asc nulls last, r.created_at desc;

-- grants: sanitized view only
revoke all on all tables in schema public from anon, authenticated;
grant select on public.corpus_leaderboard to authenticated;
```

(Owner note: grants/revokes are part of the DRAFT migration; owners apply
and may narrow `authenticated` → admin-only per §3.4.)

### A5. Upload confirmation distrusts the client

`corpus-upload-confirm` input `{ storage_path, claimed_sha256,
claimed_file_name }`:

1. Server-side: read the stored object (not the client bytes).
2. Verify the path matches the canonical layout `corpus/<sha256>/...`.
3. Verify `sha256(object) == claimed_sha256` (computed server-side).
4. Verify byte size within caps AND the storage-byte ceiling.
5. Verify MIME magic: JPEG `FFD8FF` · PNG `89 50 4E 47` · WebP `RIFF..WEBP`.
6. Parse image dimensions from headers (JPEG SOF / PNG IHDR / WebP VP8 —
   no external libraries).
7. On ANY failure: quarantine or delete the object and return 422 — never
   materialize a `corpus_images` row from an unverified object.

Upload mechanics: files > 6 MB use presigned RESUMABLE uploads (fixed 6 MB
TUS chunks); signed UPLOAD URLs are valid ~2 h, distinct from the 120 s
signed DOWNLOAD TTL.

### A6. Durable history — no cascade deletes

- `corpus_runs.experiment_id` → `ON DELETE RESTRICT`
- `corpus_runs.corpus_image_id` → `ON DELETE RESTRICT`
- `corpus_run_intents.*` → `ON DELETE RESTRICT` (as in §A1)
- Lifecycle via `archived_at` on `corpus_experiments`, `corpus_sets`,
  `corpus_images` — deletion is replaced by archival; hard delete only via
  an admin RPC that first asserts zero referencing runs.

## B. SECONDARY HARDENING (normative)

1. **Partial unique index:** `create unique index corpus_runs_job_uniq on
   corpus_runs (worker_job_id) where worker_job_id is not null;` — one job
   can never register twice.
2. **Engine-version assertion:** registration compares
   `deepclean_jobs.engine_version` against `corpus_experiments.engine_release`;
   mismatch → 409 (incomparable evidence must not enter an experiment).
3. **Copy-status + recovery:** `corpus_runs.output_copy_status
   ('PENDING','COPIED','FAILED')`. Registration order: storage copy
   (idempotent, keyed by sha256 path) → DB insert. A crash between the two
   is recovered by retrying registration, which re-runs the idempotent copy.
4. **Revokes:** corpus tables have NO grants to `anon`/`authenticated`;
   all reads go through `security_invoker` views/RPCs; all writes through
   service-role edge functions.

## C. AMENDED FLOW (end to end)

```
/corpus: create set v1 -> add members -> lock (manifest hash, immutable)
         -> create experiment (engine_release + detector identity)
/relab:  corpus picker -> corpus-run-intent (server-side requested hash)
         -> dispatch (normal flow, unchanged) -> grade (unchanged)
         -> corpus-register-run {intent_id, worker_job_id}  (non-blocking)
            asserts: job completed + input_sha256 + engine_version +
                     image in locked set; idempotent; 409 on mismatch
         -> grade_status PENDING if grade rows absent
/corpus: corpus-reconcile-grades -> COMPLETE (zero-spend, never vendor)
         leaderboard (deterministic, sanitized) + JSONL/compact exports
```

## D. ACCEPTANCE ADDITIONS (on top of V2 §6)

6. After locking a set, any membership mutation is REJECTED by the
   trigger; `lock_corpus_set` cannot run twice.
7. An intent with an image outside the experiment's set is REJECTED (409).
8. `corpus-upload-confirm` rejects a tampered hash / wrong magic / wrong
   path and removes the object.
9. Deleting an experiment or image that has runs is REJECTED (RESTRICT);
   archival works.
10. Re-running registration for the same job returns the same row (unique
    index) without duplicating grades.

## E. DELIVERABLES (unchanged from V2 §7, plus)

- `supabase/migrations/20260826000000_corpus.sql` now includes: intent
  table, lock RPC, immutability triggers, leaderboard view + revokes, RESTRICT
  FKs, partial unique index, copy-status column.

## F. REPORT FORMAT (V2 §8, plus)

- Trigger/RPC definitions verbatim with the immutability test results.
- Leaderboard SQL verbatim + grant list + a policy test note.
- Upload-confirm verification order with the 422/delete policy.

## G. HANDOFF

End with `READY_NEEDS_OWNER_INPUTS` / `READY_NEEDS_OWNER_RUN` / `BLOCKED`.
Full logs verbatim for failures. Accuracy beats speed.
