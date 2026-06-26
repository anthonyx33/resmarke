alter table public.deepclean_jobs
  add column if not exists creator_id text not null default '',
  add column if not exists runpod_job_id text;
