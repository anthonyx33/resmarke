-- DRAFT ONLY. Owner approval is required before this migration is applied.
-- Server-side grade cache and per-session vendor-call budget for /relab.

create table if not exists public.grade_cache (
  image_sha256 text not null check (image_sha256 ~ '^[0-9a-f]{64}$'),
  vendor text not null,
  mode text not null check (mode in ('sdxl', 'flux_schnell', 'real')),
  grade_id text not null check (grade_id ~ '^[0-9a-f]{64}$'),
  ai_probability double precision not null check (ai_probability between 0 and 1),
  deepfake_probability double precision not null check (deepfake_probability between 0 and 1),
  verdict text not null check (verdict in ('CLEAR', 'NEAR', 'BORDER', 'FAIL')),
  top_source text,
  sources jsonb not null default '{}'::jsonb,
  raw jsonb not null default '{}'::jsonb,
  mock boolean not null default false,
  created_at timestamptz not null default now(),
  last_accessed_at timestamptz not null default now(),
  primary key (image_sha256, vendor, mode)
);

create index if not exists grade_cache_created_at_idx
  on public.grade_cache (created_at desc);

alter table public.grade_cache enable row level security;

-- Intentionally no browser policies. grade-image accesses this table only
-- through the service-role admin client after authenticating the caller.
revoke all on table public.grade_cache from anon, authenticated;

create table if not exists public.grade_sessions (
  id uuid not null,
  user_id uuid not null references auth.users(id) on delete cascade,
  vendor_calls integer not null default 0 check (vendor_calls >= 0),
  session_cap integer not null check (session_cap > 0),
  started_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  primary key (id, user_id)
);

create index if not exists grade_sessions_user_started_idx
  on public.grade_sessions (user_id, started_at desc);

alter table public.grade_sessions enable row level security;
revoke all on table public.grade_sessions from anon, authenticated;

create or replace function public.reserve_grade_call(
  p_session_id uuid,
  p_user_id uuid,
  p_cap integer
)
returns table (vendor_calls integer, session_cap integer, allowed boolean)
language plpgsql
security definer
set search_path = public
as $$
declare
  next_calls integer;
  effective_cap integer := greatest(1, least(p_cap, 10000));
begin
  insert into public.grade_sessions (id, user_id, session_cap)
  values (p_session_id, p_user_id, effective_cap)
  on conflict (id, user_id) do nothing;

  update public.grade_sessions
  set vendor_calls = grade_sessions.vendor_calls + 1,
      session_cap = least(grade_sessions.session_cap, effective_cap),
      updated_at = now()
  where id = p_session_id
    and user_id = p_user_id
    and grade_sessions.vendor_calls < least(grade_sessions.session_cap, effective_cap)
  returning grade_sessions.vendor_calls, grade_sessions.session_cap
  into next_calls, effective_cap;

  if next_calls is not null then
    return query select next_calls, effective_cap, true;
    return;
  end if;

  return query
    select gs.vendor_calls, gs.session_cap, false
    from public.grade_sessions gs
    where gs.id = p_session_id and gs.user_id = p_user_id;
end;
$$;

revoke all on function public.reserve_grade_call(uuid, uuid, integer) from public, anon, authenticated;
grant execute on function public.reserve_grade_call(uuid, uuid, integer) to service_role;
