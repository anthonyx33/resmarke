-- DRAFT ONLY — owner approval and application required.
-- Fixed-corpus registry, immutable set manifests, comparable experiments,
-- durable run provenance, and a sanitized deterministic leaderboard.

create extension if not exists "pgcrypto";

insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values (
  'corpus',
  'corpus',
  false,
  26214400,
  array['image/jpeg', 'image/png', 'image/webp']
)
on conflict (id) do update
set public = false,
    file_size_limit = excluded.file_size_limit,
    allowed_mime_types = excluded.allowed_mime_types;

create table public.corpus_images (
  id uuid primary key default gen_random_uuid(),
  sha256 text not null unique check (sha256 ~ '^[0-9a-f]{64}$'),
  storage_path text not null unique,
  file_name text not null,
  byte_size bigint not null check (byte_size > 0 and byte_size <= 26214400),
  content_type text not null check (content_type in ('image/jpeg', 'image/png', 'image/webp')),
  width integer not null check (width > 0),
  height integer not null check (height > 0),
  created_by uuid references auth.users(id) on delete set null,
  archived_at timestamptz,
  created_at timestamptz not null default now()
);

create table public.corpus_sets (
  id uuid primary key default gen_random_uuid(),
  name text not null check (length(btrim(name)) between 1 and 120),
  version integer not null check (version > 0),
  manifest_sha256 text check (manifest_sha256 is null or manifest_sha256 ~ '^[0-9a-f]{64}$'),
  locked_at timestamptz,
  created_by uuid references auth.users(id) on delete set null,
  archived_at timestamptz,
  created_at timestamptz not null default now(),
  unique (name, version),
  check ((locked_at is null and manifest_sha256 is null) or
         (locked_at is not null and manifest_sha256 is not null))
);

create table public.corpus_set_members (
  corpus_set_id uuid not null references public.corpus_sets(id) on delete restrict,
  corpus_image_id uuid not null references public.corpus_images(id) on delete restrict,
  position integer not null check (position > 0),
  created_at timestamptz not null default now(),
  primary key (corpus_set_id, corpus_image_id),
  constraint corpus_set_members_position_uniq
    unique (corpus_set_id, position) deferrable initially immediate
);

create table public.corpus_experiments (
  id uuid primary key default gen_random_uuid(),
  corpus_set_id uuid not null references public.corpus_sets(id) on delete restrict,
  engine_release text not null check (length(btrim(engine_release)) between 1 and 300),
  detector_vendor text not null default 'g1' check (length(btrim(detector_vendor)) between 1 and 80),
  detector_mode text not null default 'real' check (detector_mode in ('sdxl', 'flux_schnell', 'real')),
  detector_model text,
  detector_version text,
  config_set jsonb not null check (jsonb_typeof(config_set) in ('array', 'object')),
  notes text,
  created_by uuid references auth.users(id) on delete set null,
  archived_at timestamptz,
  created_at timestamptz not null default now()
);

create table public.corpus_run_intents (
  id uuid primary key default gen_random_uuid(),
  experiment_id uuid not null references public.corpus_experiments(id) on delete restrict,
  corpus_image_id uuid not null references public.corpus_images(id) on delete restrict,
  config_label text not null check (config_label in ('A', '1A', '2B', 'CUSTOM')),
  config_key text not null check (length(btrim(config_key)) between 1 and 120),
  requested_settings_code text not null,
  requested_settings_canonical jsonb not null check (jsonb_typeof(requested_settings_canonical) = 'object'),
  requested_settings_sha256 text not null check (requested_settings_sha256 ~ '^[0-9a-f]{64}$'),
  created_by uuid references auth.users(id) on delete set null,
  registered_at timestamptz,
  created_at timestamptz not null default now()
);

create table public.corpus_runs (
  id uuid primary key default gen_random_uuid(),
  intent_id uuid not null unique references public.corpus_run_intents(id) on delete restrict,
  experiment_id uuid not null references public.corpus_experiments(id) on delete restrict,
  corpus_image_id uuid not null references public.corpus_images(id) on delete restrict,
  config_label text not null check (config_label in ('A', '1A', '2B', 'CUSTOM')),
  config_key text not null,
  requested_settings_code text not null,
  requested_settings_canonical jsonb not null,
  requested_settings_sha256 text not null check (requested_settings_sha256 ~ '^[0-9a-f]{64}$'),
  executed_settings_snapshot jsonb not null default '{}'::jsonb,
  executed_settings_sha256 text check (executed_settings_sha256 is null or executed_settings_sha256 ~ '^[0-9a-f]{64}$'),
  worker_report_snapshot jsonb not null default '{}'::jsonb,
  worker_report_sha256 text check (worker_report_sha256 is null or worker_report_sha256 ~ '^[0-9a-f]{64}$'),
  worker_job_id uuid references public.deepclean_jobs(id) on delete set null,
  actual_engine_version text not null,
  runtime_ms integer check (runtime_ms is null or runtime_ms >= 0),
  output_sha256 text not null check (output_sha256 ~ '^[0-9a-f]{64}$'),
  output_storage_path text not null,
  output_byte_size bigint not null check (output_byte_size > 0 and output_byte_size <= 26214400),
  output_copy_status text not null default 'PENDING'
    check (output_copy_status in ('PENDING', 'COPIED', 'FAILED')),
  grade_status text not null default 'PENDING'
    check (grade_status in ('PENDING', 'COMPLETE', 'ERROR')),
  og_grade jsonb,
  remint_grade jsonb,
  delta double precision,
  swap_index double precision check (swap_index is null or swap_index between 0 and 1),
  retention_index double precision check (retention_index is null or retention_index between 0 and 1),
  qa_flag boolean not null default false,
  created_by uuid references auth.users(id) on delete set null,
  created_at timestamptz not null default now(),
  check ((grade_status = 'COMPLETE' and og_grade is not null and remint_grade is not null and delta is not null)
      or grade_status <> 'COMPLETE')
);

create unique index corpus_runs_job_uniq
  on public.corpus_runs (worker_job_id) where worker_job_id is not null;
create index corpus_set_members_image_idx on public.corpus_set_members (corpus_image_id);
create index corpus_experiments_set_idx on public.corpus_experiments (corpus_set_id, created_at desc);
create index corpus_intents_experiment_idx on public.corpus_run_intents (experiment_id, created_at desc);
create index corpus_runs_experiment_idx on public.corpus_runs (experiment_id, created_at desc);
create index corpus_runs_image_created_idx on public.corpus_runs (corpus_image_id, created_at desc);
create index corpus_runs_output_sha_idx on public.corpus_runs (output_sha256);
create index corpus_runs_grade_pending_idx on public.corpus_runs (experiment_id, grade_status)
  where grade_status in ('PENDING', 'ERROR');

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

create or replace function public.guard_locked_corpus_set_identity()
returns trigger
language plpgsql
set search_path = public
as $$
begin
  if old.locked_at is not null and (
    new.name is distinct from old.name or
    new.version is distinct from old.version or
    new.locked_at is distinct from old.locked_at or
    new.manifest_sha256 is distinct from old.manifest_sha256
  ) then
    raise exception 'Locked corpus set identity cannot be changed.' using errcode = '23514';
  end if;
  return new;
end;
$$;

create trigger corpus_sets_guard_identity
before update on public.corpus_sets
for each row execute function public.guard_locked_corpus_set_identity();

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

create or replace function public.require_locked_experiment_set()
returns trigger
language plpgsql
set search_path = public
as $$
begin
  if not exists (
    select 1 from public.corpus_sets s
    where s.id = new.corpus_set_id and s.locked_at is not null and s.archived_at is null
  ) then
    raise exception 'Experiments require a locked, active corpus set.' using errcode = '23514';
  end if;
  return new;
end;
$$;

create trigger corpus_experiments_require_locked_set
before insert or update of corpus_set_id on public.corpus_experiments
for each row execute function public.require_locked_experiment_set();

create or replace function public.guard_experiment_identity()
returns trigger
language plpgsql
set search_path = public
as $$
begin
  if new.corpus_set_id is distinct from old.corpus_set_id or
     new.engine_release is distinct from old.engine_release or
     new.detector_vendor is distinct from old.detector_vendor or
     new.detector_mode is distinct from old.detector_mode or
     new.detector_model is distinct from old.detector_model or
     new.detector_version is distinct from old.detector_version or
     new.config_set is distinct from old.config_set then
    raise exception 'Experiment compatibility identity is immutable.' using errcode = '23514';
  end if;
  return new;
end;
$$;

create trigger corpus_experiments_guard_identity
before update on public.corpus_experiments
for each row execute function public.guard_experiment_identity();

create or replace function public.require_run_membership()
returns trigger
language plpgsql
set search_path = public
as $$
begin
  if not exists (
    select 1
    from public.corpus_experiments e
    join public.corpus_sets s on s.id = e.corpus_set_id and s.locked_at is not null
    join public.corpus_set_members m on m.corpus_set_id = e.corpus_set_id
    where e.id = new.experiment_id and m.corpus_image_id = new.corpus_image_id
  ) then
    raise exception 'Image is not a member of the experiment corpus set.' using errcode = '23514';
  end if;
  return new;
end;
$$;

create trigger corpus_intents_require_membership
before insert or update of experiment_id, corpus_image_id on public.corpus_run_intents
for each row execute function public.require_run_membership();

create trigger corpus_runs_require_membership
before insert or update of experiment_id, corpus_image_id on public.corpus_runs
for each row execute function public.require_run_membership();

create or replace function public.guard_run_provenance()
returns trigger
language plpgsql
set search_path = public
as $$
begin
  if new.intent_id is distinct from old.intent_id or
     new.experiment_id is distinct from old.experiment_id or
     new.corpus_image_id is distinct from old.corpus_image_id or
     new.config_label is distinct from old.config_label or
     new.config_key is distinct from old.config_key or
     new.requested_settings_code is distinct from old.requested_settings_code or
     new.requested_settings_canonical is distinct from old.requested_settings_canonical or
     new.requested_settings_sha256 is distinct from old.requested_settings_sha256 or
     new.executed_settings_snapshot is distinct from old.executed_settings_snapshot or
     new.executed_settings_sha256 is distinct from old.executed_settings_sha256 or
     new.worker_report_snapshot is distinct from old.worker_report_snapshot or
     new.worker_report_sha256 is distinct from old.worker_report_sha256 or
     (new.worker_job_id is distinct from old.worker_job_id and new.worker_job_id is not null) or
     new.actual_engine_version is distinct from old.actual_engine_version or
     new.runtime_ms is distinct from old.runtime_ms or
     new.output_sha256 is distinct from old.output_sha256 or
     new.output_storage_path is distinct from old.output_storage_path or
     new.output_byte_size is distinct from old.output_byte_size or
     new.created_by is distinct from old.created_by or
     new.created_at is distinct from old.created_at then
    raise exception 'Corpus run provenance is immutable.' using errcode = '23514';
  end if;
  return new;
end;
$$;

create trigger corpus_runs_guard_provenance
before update on public.corpus_runs
for each row execute function public.guard_run_provenance();

create or replace function public.register_corpus_image(
  p_sha256 text,
  p_storage_path text,
  p_file_name text,
  p_byte_size bigint,
  p_content_type text,
  p_width integer,
  p_height integer,
  p_created_by uuid,
  p_max_images integer,
  p_storage_byte_limit bigint
)
returns public.corpus_images
language plpgsql
security definer
set search_path = public
as $$
declare
  v_row public.corpus_images;
  v_count integer;
  v_bytes bigint;
  v_output_bytes bigint;
begin
  perform pg_advisory_xact_lock(hashtextextended('corpus-storage-ledger', 0));
  perform pg_advisory_xact_lock(hashtextextended('corpus-image-registry', 0));

  select * into v_row from public.corpus_images where sha256 = p_sha256;
  if found then return v_row; end if;

  select count(*)::integer, coalesce(sum(byte_size), 0)
    into v_count, v_bytes from public.corpus_images;
  select coalesce(sum(output_byte_size), 0) into v_output_bytes
  from (
    select distinct output_storage_path, output_byte_size from public.corpus_runs
  ) outputs;
  if v_count >= p_max_images then
    raise exception 'Corpus image cap reached (%).', p_max_images using errcode = '23514';
  end if;
  if v_bytes + v_output_bytes + p_byte_size > p_storage_byte_limit then
    raise exception 'Corpus storage-byte ceiling reached.' using errcode = '23514';
  end if;

  insert into public.corpus_images (
    sha256, storage_path, file_name, byte_size, content_type, width, height, created_by
  ) values (
    p_sha256, p_storage_path, p_file_name, p_byte_size, p_content_type, p_width, p_height, p_created_by
  ) returning * into v_row;
  return v_row;
end;
$$;

create or replace function public.register_corpus_run(
  p_payload jsonb,
  p_max_outputs integer,
  p_storage_byte_limit bigint
)
returns public.corpus_runs
language plpgsql
security definer
set search_path = public
as $$
declare
  v_row public.corpus_runs;
  v_job_id uuid := (p_payload->>'worker_job_id')::uuid;
  v_image_id uuid := (p_payload->>'corpus_image_id')::uuid;
  v_count integer;
  v_used_bytes bigint;
  v_new_bytes bigint := (p_payload->>'output_byte_size')::bigint;
  v_output_path text := p_payload->>'output_storage_path';
begin
  perform pg_advisory_xact_lock(hashtextextended('corpus-storage-ledger', 0));
  perform pg_advisory_xact_lock(hashtextextended(v_image_id::text, 0));

  select * into v_row from public.corpus_runs where worker_job_id = v_job_id;
  if found then return v_row; end if;

  select count(*)::integer into v_count
  from public.corpus_runs where corpus_image_id = v_image_id;
  if v_count >= p_max_outputs then
    raise exception 'Corpus output cap reached for this image (%).', p_max_outputs using errcode = '23514';
  end if;

  select
    coalesce((select sum(byte_size) from public.corpus_images), 0) +
    coalesce((select sum(output_byte_size) from (
      select distinct output_storage_path, output_byte_size from public.corpus_runs
    ) outputs), 0)
  into v_used_bytes;
  if not exists (select 1 from public.corpus_runs where output_storage_path = v_output_path) and
     v_used_bytes + v_new_bytes > p_storage_byte_limit then
    raise exception 'Corpus storage-byte ceiling reached.' using errcode = '23514';
  end if;

  insert into public.corpus_runs (
    intent_id, experiment_id, corpus_image_id, config_label, config_key,
    requested_settings_code, requested_settings_canonical, requested_settings_sha256,
    executed_settings_snapshot, executed_settings_sha256,
    worker_report_snapshot, worker_report_sha256, worker_job_id,
    actual_engine_version, runtime_ms, output_sha256, output_storage_path,
    output_byte_size, output_copy_status, grade_status, og_grade, remint_grade,
    delta, swap_index, retention_index, qa_flag, created_by
  ) values (
    (p_payload->>'intent_id')::uuid,
    (p_payload->>'experiment_id')::uuid,
    v_image_id,
    p_payload->>'config_label',
    p_payload->>'config_key',
    p_payload->>'requested_settings_code',
    p_payload->'requested_settings_canonical',
    p_payload->>'requested_settings_sha256',
    coalesce(p_payload->'executed_settings_snapshot', '{}'::jsonb),
    nullif(p_payload->>'executed_settings_sha256', ''),
    coalesce(p_payload->'worker_report_snapshot', '{}'::jsonb),
    nullif(p_payload->>'worker_report_sha256', ''),
    v_job_id,
    p_payload->>'actual_engine_version',
    nullif(p_payload->>'runtime_ms', '')::integer,
    p_payload->>'output_sha256',
    p_payload->>'output_storage_path',
    (p_payload->>'output_byte_size')::bigint,
    coalesce(p_payload->>'output_copy_status', 'COPIED'),
    coalesce(p_payload->>'grade_status', 'PENDING'),
    p_payload->'og_grade',
    p_payload->'remint_grade',
    nullif(p_payload->>'delta', '')::double precision,
    nullif(p_payload->>'swap_index', '')::double precision,
    nullif(p_payload->>'retention_index', '')::double precision,
    coalesce((p_payload->>'qa_flag')::boolean, false),
    (p_payload->>'created_by')::uuid
  ) returning * into v_row;

  update public.corpus_run_intents set registered_at = now()
  where id = v_row.intent_id and registered_at is null;

  return v_row;
end;
$$;

create or replace function public.hard_delete_corpus_image(p_id uuid)
returns void language plpgsql security definer set search_path = public as $$
begin
  if exists (select 1 from public.corpus_runs where corpus_image_id = p_id) or
     exists (select 1 from public.corpus_run_intents where corpus_image_id = p_id) or
     exists (select 1 from public.corpus_set_members where corpus_image_id = p_id) then
    raise exception 'Corpus image is referenced and cannot be hard-deleted.' using errcode = '23503';
  end if;
  delete from public.corpus_images where id = p_id;
end;
$$;

create or replace function public.hard_delete_corpus_experiment(p_id uuid)
returns void language plpgsql security definer set search_path = public as $$
begin
  if exists (select 1 from public.corpus_runs where experiment_id = p_id) or
     exists (select 1 from public.corpus_run_intents where experiment_id = p_id) then
    raise exception 'Experiment is referenced and cannot be hard-deleted.' using errcode = '23503';
  end if;
  delete from public.corpus_experiments where id = p_id;
end;
$$;

create or replace function public.hard_delete_corpus_set(p_id uuid)
returns void language plpgsql security definer set search_path = public as $$
begin
  if exists (select 1 from public.corpus_experiments where corpus_set_id = p_id) then
    raise exception 'Corpus set is referenced and cannot be hard-deleted.' using errcode = '23503';
  end if;
  if exists (select 1 from public.corpus_sets where id = p_id and locked_at is not null) then
    raise exception 'Locked corpus sets cannot be hard-deleted.' using errcode = '23514';
  end if;
  delete from public.corpus_set_members where corpus_set_id = p_id;
  delete from public.corpus_sets where id = p_id;
end;
$$;

create or replace function public.corpus_storage_usage()
returns table (original_bytes bigint, output_bytes bigint, total_bytes bigint)
language sql
security definer
set search_path = public
stable
as $$
  with originals as (
    select coalesce(sum(byte_size), 0)::bigint as bytes from public.corpus_images
  ), outputs as (
    select coalesce(sum(output_byte_size), 0)::bigint as bytes
    from (select distinct output_storage_path, output_byte_size from public.corpus_runs) unique_outputs
  )
  select originals.bytes, outputs.bytes, originals.bytes + outputs.bytes
  from originals cross join outputs;
$$;

create or replace function public.corpus_run_counts()
returns table (corpus_image_id uuid, run_count bigint, pending_count bigint)
language sql
security definer
set search_path = public
stable
as $$
  select r.corpus_image_id,
         count(*)::bigint,
         count(*) filter (where r.grade_status in ('PENDING', 'ERROR'))::bigint
  from public.corpus_runs r
  group by r.corpus_image_id;
$$;

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

alter table public.corpus_images enable row level security;
alter table public.corpus_sets enable row level security;
alter table public.corpus_set_members enable row level security;
alter table public.corpus_experiments enable row level security;
alter table public.corpus_run_intents enable row level security;
alter table public.corpus_runs enable row level security;

-- First release is admin-only. No browser policies and no raw-table grants.
-- Edge Functions authenticate the allowlisted owner then use service_role.
revoke all on table public.corpus_images from anon, authenticated;
revoke all on table public.corpus_sets from anon, authenticated;
revoke all on table public.corpus_set_members from anon, authenticated;
revoke all on table public.corpus_experiments from anon, authenticated;
revoke all on table public.corpus_run_intents from anon, authenticated;
revoke all on table public.corpus_runs from anon, authenticated;
revoke all on table public.corpus_leaderboard from anon, authenticated;

revoke all on function public.lock_corpus_set(uuid) from public, anon, authenticated;
revoke all on function public.register_corpus_image(text, text, text, bigint, text, integer, integer, uuid, integer, bigint) from public, anon, authenticated;
revoke all on function public.register_corpus_run(jsonb, integer, bigint) from public, anon, authenticated;
revoke all on function public.hard_delete_corpus_image(uuid) from public, anon, authenticated;
revoke all on function public.hard_delete_corpus_experiment(uuid) from public, anon, authenticated;
revoke all on function public.hard_delete_corpus_set(uuid) from public, anon, authenticated;
revoke all on function public.corpus_storage_usage() from public, anon, authenticated;
revoke all on function public.corpus_run_counts() from public, anon, authenticated;

grant execute on function public.lock_corpus_set(uuid) to service_role;
grant execute on function public.register_corpus_image(text, text, text, bigint, text, integer, integer, uuid, integer, bigint) to service_role;
grant execute on function public.register_corpus_run(jsonb, integer, bigint) to service_role;
grant execute on function public.hard_delete_corpus_image(uuid) to service_role;
grant execute on function public.hard_delete_corpus_experiment(uuid) to service_role;
grant execute on function public.hard_delete_corpus_set(uuid) to service_role;
grant execute on function public.corpus_storage_usage() to service_role;
grant execute on function public.corpus_run_counts() to service_role;
grant select on table public.corpus_leaderboard to service_role;

-- Storage remains private. No browser storage policies are created.
