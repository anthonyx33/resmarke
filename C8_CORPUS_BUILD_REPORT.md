# C8 Corpus Build Report

Build date: 2026-08-25  
Consultant: C8

## 1. Summary

- Added the private `/corpus` administration console, fixed-image registry, immutable corpus sets, compatible experiments, history, leaderboard, exports, and zero-spend grade reconciliation.
- Added nine authenticated, admin-allowlisted Edge Functions for verified upload, private read, management, authoritative run intent, guarded registration, and reconciliation.
- Added the draft `20260826000000_corpus.sql` migration with content-addressed assets, irreversible manifests, durable provenance snapshots, RESTRICT history, RLS, revokes, RPCs, triggers, and a sanitized leaderboard.
- Added only the permitted `/relab` corpus picker plus pre-dispatch intent and non-blocking post-grade registration/retry hook; dispatch, worker, grading, presets, engines, and thresholds are unchanged.
- Client TypeScript, production build, all Edge Function checks, settings-code/image-header tests, dependency audit, and diff checks pass; deployment still needs the four owner inputs and owner-approved migration application.

Protocol laws (verbatim): **L1 settings-code; L2 executed-not-requested (store the full worker report per run); L3 paired; L4 fixed corpus — THIS BUILD IS THE MECHANICAL L4; L5 decision provenance; L6 QA flagging; L7 100%-zoom rubric.**

## 2. Files changed and forbidden-scope confirmation

New application files:

- `src/CorpusApp.tsx` — admin authentication gate, uploads, registry, set locking, experiment creation, history, reconciliation, leaderboard, and exports.
- `src/corpus.css` — isolated `/corpus` console presentation.
- `src/lib/corpusClient.ts` — typed Edge Function client, SHA-256 upload dedup, bounded TUS upload, management, intent, registration, reconciliation, JSONL, and compact-report helpers.

New server files:

- `supabase/migrations/20260826000000_corpus.sql` — draft only; not applied.
- `supabase/functions/_shared/corpus.ts` — allowlist, environment, validation, canonical JSON, hashing, and safe HTTP errors.
- `supabase/functions/_shared/corpus_image.ts` — JPEG/PNG/WebP magic and header-dimension verification.
- `supabase/functions/_shared/corpus_grades.ts` — paired cache snapshots and swap/retention calculation.
- `supabase/functions/_shared/settings_code.ts` — server-side copy of the frozen settings-code contract, guarded by golden parity tests.
- `supabase/functions/corpus-upload/index.ts`.
- `supabase/functions/corpus-upload-presign/index.ts`.
- `supabase/functions/corpus-upload-confirm/index.ts`.
- `supabase/functions/corpus-list/index.ts`.
- `supabase/functions/corpus-read/index.ts`.
- `supabase/functions/corpus-manage/index.ts`.
- `supabase/functions/corpus-run-intent/index.ts`.
- `supabase/functions/corpus-register-run/index.ts`.
- `supabase/functions/corpus-reconcile-grades/index.ts`.
- `supabase/functions/_shared/corpus_test.ts` — settings-code golden values and image-header unit tests.
- `supabase/tests/corpus_contract.sql` — pgTAP lock/membership contract tests for the owner-applied database.

Modified integration files:

- `src/main.tsx` — lazy `/corpus` route.
- `src/RelabApp.tsx` — corpus picker, authoritative run-intent call, non-blocking registration status, and manual retry only.
- `src/relab.css` — corpus-picker/registration styles only.
- `supabase/config.toml` — all nine new functions use `verify_jwt = true`.
- `package.json`, `package-lock.json` — `tus-js-client` plus the Node type package needed for checked Deno tests.
- `deno.lock` — checked remote dependencies.

Forbidden-scope confirmation: `src/RemintApp.tsx`, `src/CmintApp.tsx`, `deepclean-worker/**`, engines, finisher, frozen presets, thresholds, and every existing Supabase function have zero diff. No migration was applied. No autonomous run, rerun, routing decision, vendor call, public bucket, public URL, browser write policy, API key, token, or secret was added.

## 3. Data model and integrity mechanics

### Registry, sets, and experiment compatibility

- `corpus_images` is content-addressed by unique SHA-256 and records verified byte size, MIME type, dimensions, private path, creator, and archive state.
- `corpus_sets` provides `(name, version)`, a one-shot `locked_at`, and `manifest_sha256` over the ordered image hashes.
- `corpus_set_members` has unique image membership and a DEFERRABLE unique `(corpus_set_id, position)` constraint. Locking canonicalizes positions to dense `1..N` before hashing.
- `corpus_experiments` binds a locked set to `engine_release`, detector vendor/mode/model/version, and the allowed config set. That compatibility identity is immutable.
- `corpus_run_intents` is written before dispatch. The server recomputes the full requested-settings SHA-256 and verifies the `SEQ-*` code and config identity.
- `corpus_runs` copies requested identity from the intent, snapshots executed settings and the complete worker report plus hashes, stores actual engine version/runtime/output identity, and snapshots paired normalized grades.
- Run-facing image, experiment, and intent FKs are `ON DELETE RESTRICT`; `worker_job_id` alone is `ON DELETE SET NULL` because the worker report and hashes are durable snapshots.
- One worker job and one intent can each produce at most one corpus run. Output count and total-storage ceilings are serialized through advisory-lock RPCs.

Compatibility key: `(engine_release, detector_vendor, detector_mode, detector_model, detector_version)`. Runs across different compatibility keys are never ranked together.

### Mechanical lock RPC and mutation trigger

The applied migration contains this lock RPC verbatim:

```sql
create or replace function public.lock_corpus_set(p_set_id uuid)
returns table (id uuid, manifest_sha256 text, locked_at timestamptz, member_count integer)
language plpgsql
security definer
set search_path = public, extensions
as $$
declare
  v_locked_at timestamptz;
  v_manifest text;
  v_count integer;
begin
  select s.locked_at into v_locked_at
  from public.corpus_sets s
  where s.id = p_set_id
  for update;

  if not found then
    raise exception 'Corpus set not found.' using errcode = 'P0002';
  end if;
  if v_locked_at is not null then
    raise exception 'Corpus set is already locked.' using errcode = '23514';
  end if;

  select count(*)::integer into v_count
  from public.corpus_set_members m
  where m.corpus_set_id = p_set_id;
  if v_count < 1 then
    raise exception 'An empty corpus set cannot be locked.' using errcode = '23514';
  end if;

  set constraints corpus_set_members_position_uniq deferred;
  with ordered as (
    select m.corpus_image_id,
           row_number() over (order by m.position, m.corpus_image_id)::integer as dense_position
    from public.corpus_set_members m
    where m.corpus_set_id = p_set_id
  )
  update public.corpus_set_members m
  set position = ordered.dense_position
  from ordered
  where m.corpus_set_id = p_set_id
    and m.corpus_image_id = ordered.corpus_image_id;

  select encode(digest(convert_to(jsonb_agg(i.sha256 order by m.position)::text, 'UTF8'), 'sha256'), 'hex')
  into v_manifest
  from public.corpus_set_members m
  join public.corpus_images i on i.id = m.corpus_image_id
  where m.corpus_set_id = p_set_id;

  update public.corpus_sets s
  set manifest_sha256 = v_manifest,
      locked_at = now()
  where s.id = p_set_id;

  return query
  select s.id, s.manifest_sha256, s.locked_at, v_count
  from public.corpus_sets s where s.id = p_set_id;
end;
$$;
```

The membership guard and trigger are:

```sql
create or replace function public.guard_locked_corpus_membership()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
declare
  v_set_id uuid;
begin
  if tg_op in ('UPDATE', 'DELETE') then
    v_set_id := old.corpus_set_id;
    if exists (select 1 from public.corpus_sets where id = v_set_id and locked_at is not null) then
      raise exception 'Corpus set % is locked and immutable.', v_set_id using errcode = '23514';
    end if;
  end if;
  if tg_op = 'INSERT' then
    v_set_id := new.corpus_set_id;
    if exists (select 1 from public.corpus_sets where id = v_set_id and locked_at is not null) then
      raise exception 'Corpus set % is locked and immutable.', v_set_id using errcode = '23514';
    end if;
  elsif tg_op = 'UPDATE' and new.corpus_set_id is distinct from old.corpus_set_id then
    v_set_id := new.corpus_set_id;
    if exists (select 1 from public.corpus_sets where id = v_set_id and locked_at is not null) then
      raise exception 'Corpus set % is locked and immutable.', v_set_id using errcode = '23514';
    end if;
  end if;
  if tg_op = 'DELETE' then return old; end if;
  return new;
end;
$$;

create trigger corpus_members_guard_locked
before insert or update or delete on public.corpus_set_members
for each row execute function public.guard_locked_corpus_membership();
```

Additional migration triggers, all enabled before any data API is exposed:

- `corpus_sets_guard_identity` — locked name/version/manifest/lock timestamp cannot change.
- `corpus_experiments_require_locked_set` — rejects experiments against unlocked or archived sets.
- `corpus_experiments_guard_identity` — prevents compatibility-key or config-set drift.
- `corpus_intents_require_membership` and `corpus_runs_require_membership` — recheck image membership against the experiment set.
- `corpus_runs_guard_provenance` — reconciliation may change only grade/copy state; requested, executed, worker, output, engine, creator, and timestamp provenance cannot be rewritten. The sole allowed provenance transition is FK-driven `worker_job_id → NULL`.

The complete RPC and trigger definitions are in the draft migration; `register_corpus_image` and `register_corpus_run` additionally serialize cap checks with transaction-scoped advisory locks. Hard-delete RPCs reject referenced data; the console uses archival by default.

### Leaderboard SQL and grants

The migration definition is:

```sql
create view public.corpus_leaderboard with (security_invoker = true) as
select distinct on (
  e.corpus_set_id, r.corpus_image_id, r.config_key,
  e.detector_vendor, e.detector_mode, e.engine_release,
  e.detector_model, e.detector_version
)
  r.id as corpus_run_id,
  r.experiment_id,
  r.corpus_image_id,
  i.file_name,
  e.corpus_set_id,
  e.engine_release,
  e.detector_vendor,
  e.detector_mode,
  e.detector_model,
  e.detector_version,
  r.config_label,
  r.config_key,
  r.requested_settings_code,
  r.grade_status,
  r.qa_flag,
  coalesce((r.og_grade->>'mock')::boolean, true) as mock,
  (r.og_grade->>'ai_probability')::double precision as og_ai,
  (r.remint_grade->>'ai_probability')::double precision as remint_ai,
  r.delta,
  r.swap_index,
  r.retention_index,
  r.og_grade->>'top_source' as og_top_source,
  r.remint_grade->>'top_source' as remint_top_source,
  r.og_grade->>'verdict' as og_verdict,
  r.remint_grade->>'verdict' as remint_verdict,
  r.runtime_ms,
  r.created_at
from public.corpus_runs r
join public.corpus_experiments e on e.id = r.experiment_id
join public.corpus_sets s on s.id = e.corpus_set_id
join public.corpus_images i on i.id = r.corpus_image_id
where s.archived_at is null and e.archived_at is null and i.archived_at is null
order by
  e.corpus_set_id, r.corpus_image_id, r.config_key,
  e.detector_vendor, e.detector_mode, e.engine_release,
  e.detector_model, e.detector_version,
  r.qa_flag asc,
  coalesce((r.og_grade->>'mock')::boolean, true) asc,
  (r.grade_status = 'COMPLETE') desc,
  case r.remint_grade->>'verdict'
    when 'CLEAR' then 0 when 'NEAR' then 1 when 'BORDER' then 2 else 3
  end asc,
  r.delta desc nulls last,
  (r.remint_grade->>'ai_probability')::double precision asc nulls last,
  r.runtime_ms asc nulls last,
  r.created_at desc,
  r.id desc;
```

Grant list: every corpus table and the view is revoked from `anon` and `authenticated`; all privileged RPCs are revoked from `public`, `anon`, and `authenticated`, then granted only to `service_role`. The sanitized view is also granted only to `service_role`. This intentionally implements the owner-input default of admin-only reads through authenticated allowlisted Edge Functions; it does not guess an authenticated-creator read policy.

The pgTAP contract at `supabase/tests/corpus_contract.sql` proves dense lock ordering, manifest generation, irreversible locking, rejection of INSERT/UPDATE/DELETE membership changes, rejection of experiments on unlocked sets, and rejection of intents for non-members. It is supplied but not executed because the migration is draft/unapplied and Docker/Postgres is unavailable in this workspace. The owner command is in §7.

## 4. Upload, deduplication, read, and registration flows

### Upload and verification

- Files up to 6 MB: browser reads base64, authenticated `corpus-upload` decodes server-side, verifies size/magic/dimensions, hashes bytes, checks dedup, writes the private object, and materializes the row through the atomic cap RPC.
- Files above 6 MB and up to 25 MB: browser computes SHA-256, `corpus-upload-presign` checks allowlist/dedup/preflight caps and returns a two-hour signed upload token. `tus-js-client` uploads directly to the storage hostname in fixed 6 MB chunks, with only 2–3 concurrent uploads.
- `corpus-upload-confirm` never trusts browser claims. Verification order is: authenticated admin → canonical path → server download → 25 MB ceiling → JPEG/PNG/WebP magic → header-parsed dimensions and pixel safety limit → server SHA-256 → MIME/path agreement → atomic registry/storage-cap RPC.
- Any confirm failure removes the unregistered object and returns 422. A previously materialized object is never removed by cleanup. Uploads never use upsert, so immutable content paths cannot be silently overwritten.
- Re-uploading identical bytes returns the existing SHA row without new storage.
- `corpus-list` and `corpus-read` expose only sanitized data plus 120-second signed URLs. Neither endpoint returns permanent public URLs or bucket paths.

### Run intent and registration

1. A corpus-origin `/relab` item records `corpus-run-intent` after the normal job is created but before upload/dispatch.
2. The server verifies locked-set membership, allowed config, exact client/server `SEQ-*` agreement, and computes the requested canonical SHA-256.
3. Existing dispatch and grading run unchanged.
4. After paired grading, a non-blocking `corpus-register-run {intent_id, worker_job_id}` call executes. Failure displays `REGISTRATION_PENDING`/failed state with manual retry; the remint result remains completed.
5. Registration rejects any non-completed job, cross-user job, wrong input SHA, image outside the locked set, or engine-version mismatch with HTTP 409.
6. The delivered output is read from the private output bucket, hashed against `deepclean_jobs.output_sha256`, header-verified, and copied into a content-addressed corpus output path. Retry verifies/reuses an existing copy.
7. The server snapshots requested identity from the intent, executed settings and full report from `deepclean_jobs.report`, hashes both snapshots, and inserts through the serialized output-cap RPC.

A crash after copy but before insert is recoverable: retry finds and verifies the same content-addressed object, then inserts. A crash after insert but before response returns the existing run by the unique worker-job constraint.

## 5. Paired grades, PENDING, reconciliation, and budget

- Corpus code never invokes `grade-image` and never calls the vendor.
- Registration joins OG and output by `(image_sha256, experiment.detector_vendor, experiment.detector_mode)`.
- Both cache rows present: normalized rows including redacted raw response are snapshotted, Δ is `OG − remint`, swap/retention is recomputed against the OG top three, BORDER becomes the QA flag, and status is `COMPLETE`.
- Either cache row absent: the run is stored as `PENDING` with provenance/output intact.
- `corpus-reconcile-grades` accepts an experiment or up to 500 run IDs, batch-fetches cache rows in groups of 100, and updates only grade fields. It is idempotent and returns `{completed, still_pending}`.
- Reconciliation cannot mutate requested/executed/report/output provenance because the database trigger rejects those changes.

Budget reality: the first detector mode over 50 new originals can require 50 OG calls, then one call per unique output. A full three-config round is approximately 200 calls and 3,450 remint credits at 23 credits/output. Hash caching prevents duplicate calls but does not eliminate first-time spend. This build adds no corpus-wide run button, scheduler, or autonomous rerun.

## 6. RLS, bucket, and owner decisions

Secure build defaults, pending owner confirmation:

- Bucket: `corpus`, private, 25 MB object cap, JPEG/PNG/WebP only. The migration is draft so the owner may change the name before apply; `CORPUS_BUCKET` must match.
- Management/read scope: admin-only. UUID allowlist is authoritative; normalized email fallback requires a verified email.
- Raw corpus tables: RLS enabled, no browser policies, no `anon`/`authenticated` grants.
- Raw worker reports and grade responses: accessible only through allowlisted server endpoints; the public PostgREST surface cannot read them.
- Signed original/output downloads: default 120 seconds; permanent public URLs do not exist.
- Lifecycle: archive by default. Hard-delete RPCs require zero references; image hard deletion removes the private original after the database assertion succeeds.

Still required from the owner:

1. `CORPUS_ADMIN_UUIDS` and optional verified fallback `CORPUS_ADMIN_EMAILS`.
2. Confirm `CORPUS_BUCKET=corpus` and private service-role-only storage.
3. Confirm max images, max outputs/image, and supply `CORPUS_STORAGE_BYTE_LIMIT_BYTES`.
4. Confirm first-release read scope remains admin-only or provide an authenticated-creator policy for a later migration.

## 7. Owner-only commands

No command below has been executed against production.

```bash
# Authenticate/link without placing database passwords or secrets in source.
supabase login
supabase link --project-ref <PROJECT_REF>

# Review first; migration is owner-applied only.
supabase db push --linked --include-all --dry-run
supabase db push --linked --include-all

# Install server-only corpus policy. Use real UUID/email/byte values.
supabase secrets set \
  CORPUS_ADMIN_UUIDS=<UUID_1,UUID_2> \
  CORPUS_ADMIN_EMAILS=<VERIFIED_EMAIL_1,VERIFIED_EMAIL_2> \
  CORPUS_BUCKET=corpus \
  CORPUS_MAX_IMAGES=200 \
  CORPUS_MAX_OUTPUTS_PER_IMAGE=20 \
  CORPUS_STORAGE_BYTE_LIMIT_BYTES=<OWNER_APPROVED_BYTES> \
  CORPUS_DOWNLOAD_TTL_SECONDS=120 \
  --project-ref <PROJECT_REF>

# Deploy only the new functions; JWT verification remains enabled in config.toml.
supabase functions deploy \
  corpus-upload corpus-upload-presign corpus-upload-confirm \
  corpus-list corpus-read corpus-manage corpus-run-intent \
  corpus-register-run corpus-reconcile-grades \
  --project-ref <PROJECT_REF> --use-api --jobs 3

# Check the private bucket in the SQL editor.
select id, name, public, file_size_limit, allowed_mime_types
from storage.buckets where id = 'corpus';

# Run the supplied database contract after the migration is approved/applied.
supabase test db --linked supabase/tests/corpus_contract.sql
```

Owner smoke test:

1. Sign in at `/corpus`; upload the same image twice and confirm the second is deduplicated.
2. Create set v1, add at least one image, lock it, then confirm membership controls are disabled and the manifest is shown.
3. Create an experiment with an exact engine release from the discovered completed-job list.
4. Open `/relab`, load that experiment/image through **Corpus**, run Config A, and observe non-blocking registration become registered.
5. Return to `/corpus`, reconcile if PENDING, inspect history/leaderboard, and export JSONL plus the compact table.

## 8. Verification and failure logs

Passing checks:

```text
npx tsc --noEmit
PASS

npm run build
PASS — /corpus emitted as its own lazy JS/CSS chunk

deno check [all nine new Edge Function entrypoints]
PASS

deno test supabase/functions/_shared/corpus_test.ts
ok | 4 passed | 0 failed

npm audit
found 0 vulnerabilities

git diff --check
PASS

Vite route smoke
/corpus 200 text/html
/relab 200 text/html
```

Database lint could not execute because this workspace has neither a running local Supabase Postgres instance nor Docker. Full log verbatim:

```text
Connecting to local database...
{"_tag":"Error","error":{"code":"LegacyDbConnectError","message":"failed to connect to postgres: effect/sql/SqlError: PgClient: Failed to connect"}}
```

The initial Edge Function check found two new-code type errors; both were corrected and the complete re-check passed. Full initial log verbatim:

```text
Check supabase/functions/corpus-upload/index.ts
Check supabase/functions/corpus-upload-presign/index.ts
Check supabase/functions/corpus-upload-confirm/index.ts
Check supabase/functions/corpus-list/index.ts
Check supabase/functions/corpus-read/index.ts
Check supabase/functions/corpus-manage/index.ts
Check supabase/functions/corpus-run-intent/index.ts
Check supabase/functions/corpus-register-run/index.ts
Check supabase/functions/corpus-reconcile-grades/index.ts
TS2345 [ERROR]: Argument of type 'Uint8Array<ArrayBufferLike>' is not assignable to parameter of type 'BufferSource'.
  Type 'Uint8Array<ArrayBufferLike>' is not assignable to type 'ArrayBufferView<ArrayBuffer>'.
    Types of property 'buffer' are incompatible.
      Type 'ArrayBufferLike' is not assignable to type 'ArrayBuffer'.
        Type 'SharedArrayBuffer' is missing the following properties from type 'ArrayBuffer': resizable, resize, detached, transfer, transferToFixedLength
  const digest = await crypto.subtle.digest("SHA-256", source);
                                                       ~~~~~~
    at file:///Users/a/Documents/NOSYNF/supabase/functions/_shared/corpus.ts:87:56

TS2345 [ERROR]: Argument of type 'keyof Map<"image/jpeg" | "image/png" | "image/webp", "jpg" | "png" | "webp">' is not assignable to parameter of type '"image/jpeg" | "image/png" | "image/webp"'.
  Type 'unique symbol' is not assignable to type '"image/jpeg" | "image/png" | "image/webp"'.
    const extension = MIME_EXTENSIONS.get(contentType as keyof typeof MIME_EXTENSIONS);
                                          ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    at file:///Users/a/Documents/NOSYNF/supabase/functions/corpus-upload-presign/index.ts:32:43

Found 2 errors.

error: Type checking failed.
```

The checked Deno unit test initially exposed a missing development-only Node type package required by the newly installed TUS types. `@types/node` was added; the checked test now passes. Full initial log verbatim:

```text
Check supabase/functions/_shared/corpus_test.ts
error: Error: Could not find a matching package for 'npm:@types/node' in the node_modules directory. Ensure you have all your JSR and npm dependencies listed in your deno.json or package.json, then run `deno install`. Alternatively, turn on auto-install by specifying `"nodeModulesDir": "auto"` in your deno.json file.
    at Object.resolveTypeReferenceDirectiveReferences (ext:deno_cli_tsc/97_ts_host.js:517:26)
    at ext:deno_cli_tsc/97_ts_host.js:749:49
    at spanned (ext:deno_cli_tsc/97_ts_host.js:16:12)
    at Object.host.<computed> [as resolveTypeReferenceDirectiveReferences] (ext:deno_cli_tsc/97_ts_host.js:749:14)
    at resolveTypeReferenceDirectiveNamesWorker (ext:deno_cli_tsc/00_typescript.js:128306:20)
    at resolveNamesReusingOldState (ext:deno_cli_tsc/00_typescript.js:128422:14)
    at resolveTypeReferenceDirectiveNamesReusingOldState (ext:deno_cli_tsc/00_typescript.js:128393:12)
    at processTypeReferenceDirectives (ext:deno_cli_tsc/00_typescript.js:129685:156)
    at findSourceFileWorker (ext:deno_cli_tsc/00_typescript.js:129618:9)
    at findSourceFile (ext:deno_cli_tsc/00_typescript.js:129476:20)
```

## 9. Exit status

The implementation is complete, locally verified, security-gated, and ready for an owner-reviewed migration/deployment. Production operation is intentionally unavailable until the allowlist, private bucket confirmation, caps/storage-byte ceiling, and read scope are supplied.

**READY_NEEDS_OWNER_INPUTS**
