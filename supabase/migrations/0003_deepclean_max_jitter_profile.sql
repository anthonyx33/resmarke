alter table public.deepclean_jobs
  drop constraint if exists deepclean_jobs_profile_check;

alter table public.deepclean_jobs
  add constraint deepclean_jobs_profile_check
  check (profile in ('standard', 'strong', 'max', 'max-jitter'));
