-- ResMarke production schema.
-- Paste this into the Supabase SQL Editor for the resmarke-prod project.
-- Safe to run more than once.

create extension if not exists "pgcrypto";

insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values
  ('deepclean-inputs', 'deepclean-inputs', false, 26214400, array['image/jpeg', 'image/png', 'image/webp']),
  ('deepclean-outputs', 'deepclean-outputs', false, 26214400, array['image/jpeg'])
on conflict (id) do nothing;

create table if not exists public.creator_profiles (
  user_id uuid primary key references auth.users(id) on delete cascade,
  privacy_exports_remaining integer not null default 3 check (privacy_exports_remaining >= 0),
  deepclean_credits integer not null default 0 check (deepclean_credits >= 0),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.credit_ledger (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  job_id uuid,
  kind text not null check (kind in ('grant', 'privacy_spend', 'deepclean_reserve', 'deepclean_capture', 'deepclean_release', 'refund')),
  amount integer not null,
  balance_after integer,
  metadata jsonb not null default '{}',
  created_at timestamptz not null default now()
);

create table if not exists public.deepclean_jobs (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  creator_id text not null default '',
  status text not null default 'queued' check (status in ('queued', 'uploading', 'processing', 'completed', 'failed')),
  profile text not null default 'standard' check (profile in ('standard', 'strong', 'max', 'max-jitter')),
  output_mode text not null default 'sealed' check (output_mode in ('stripped', 'sealed', 'sealed-stamped')),
  input_path text not null,
  output_path text not null,
  runpod_job_id text,
  input_sha256 text,
  output_sha256 text,
  credits_reserved integer not null default 1,
  credits_charged integer not null default 0,
  engine_version text,
  runtime_ms integer,
  gpu_type text,
  failure_reason text,
  report jsonb not null default '{}',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  completed_at timestamptz
);

alter table public.deepclean_jobs
  add column if not exists creator_id text not null default '',
  add column if not exists runpod_job_id text;

alter table public.deepclean_jobs
  drop constraint if exists deepclean_jobs_profile_check;

alter table public.deepclean_jobs
  add constraint deepclean_jobs_profile_check
  check (profile in ('standard', 'strong', 'max', 'max-jitter'));

alter table public.creator_profiles enable row level security;
alter table public.credit_ledger enable row level security;
alter table public.deepclean_jobs enable row level security;

drop policy if exists "Users can read own profile" on public.creator_profiles;
create policy "Users can read own profile"
  on public.creator_profiles for select
  using (auth.uid() = user_id);

drop policy if exists "Users can read own ledger" on public.credit_ledger;
create policy "Users can read own ledger"
  on public.credit_ledger for select
  using (auth.uid() = user_id);

drop policy if exists "Users can read own deepclean jobs" on public.deepclean_jobs;
create policy "Users can read own deepclean jobs"
  on public.deepclean_jobs for select
  using (auth.uid() = user_id);

create or replace function public.ensure_creator_profile()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  insert into public.creator_profiles (user_id)
  values (new.id)
  on conflict (user_id) do nothing;
  return new;
end;
$$;

drop trigger if exists on_auth_user_created_creator_profile on auth.users;
create trigger on_auth_user_created_creator_profile
after insert on auth.users
for each row execute function public.ensure_creator_profile();
