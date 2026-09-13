-- READ-ONLY PRODUCTION PREFLIGHT. Do not mutate, delete, or repair rows here.
-- Any returned row is a deployment STOP requiring separate data adjudication
-- before 20260913000000_deepclean_terminal_finalize.sql may be applied.

select
  job_id,
  count(*) as terminal_effect_count,
  count(*) filter (where kind = 'deepclean_capture') as capture_count,
  count(*) filter (where kind = 'deepclean_release') as release_count,
  min(created_at) as first_terminal_effect_at,
  max(created_at) as last_terminal_effect_at
from public.credit_ledger
where job_id is not null
  and kind in ('deepclean_capture', 'deepclean_release')
group by job_id
having count(*) > 1
order by job_id;
