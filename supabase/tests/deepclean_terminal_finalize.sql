begin;

create extension if not exists pgtap with schema extensions;
set search_path = public, extensions;

select plan(17);

select throws_ok(
  $$ select public.finalize_deepclean_job_terminal('92000000-0000-4000-8000-000000000001', null) $$,
  '22023',
  'Invalid terminal status.',
  'null terminal status is rejected'
);

insert into auth.users (id)
values
  ('91000000-0000-4000-8000-000000000001'),
  ('91000000-0000-4000-8000-000000000002');

update public.creator_profiles
set deepclean_credits = 7
where user_id in (
  '91000000-0000-4000-8000-000000000001',
  '91000000-0000-4000-8000-000000000002'
);

insert into public.deepclean_jobs
  (id, user_id, status, input_path, output_path, credits_reserved)
values
  ('92000000-0000-4000-8000-000000000001', '91000000-0000-4000-8000-000000000001', 'processing', 'in/complete', 'out/complete', 1),
  ('92000000-0000-4000-8000-000000000002', '91000000-0000-4000-8000-000000000002', 'processing', 'in/fail', 'out/fail', 1);

select is(
  (public.finalize_deepclean_job_terminal(
    '92000000-0000-4000-8000-000000000001', 'completed',
    'output-sha', 'input-sha', 'engine', 12, 'gpu', null, '{"public":true}'
  ) ->> 'outcome'),
  'applied',
  'first completed callback applies'
);

select is(
  (select status from public.deepclean_jobs where id = '92000000-0000-4000-8000-000000000001'),
  'completed',
  'completed callback makes the job terminal'
);

select is(
  (select credits_charged from public.deepclean_jobs where id = '92000000-0000-4000-8000-000000000001'),
  1,
  'completed callback captures the reservation'
);

select is(
  (select count(*)::integer from public.credit_ledger where job_id = '92000000-0000-4000-8000-000000000001' and kind = 'deepclean_capture'),
  1,
  'completed callback creates one capture ledger row'
);

select is(
  (public.finalize_deepclean_job_terminal(
    '92000000-0000-4000-8000-000000000001', 'completed',
    'different-output-sha', null, null, null, null, null, '{}'
  ) ->> 'outcome'),
  'duplicate',
  'replayed completed callback is duplicate'
);

select is(
  (select output_sha256 from public.deepclean_jobs where id = '92000000-0000-4000-8000-000000000001'),
  'output-sha',
  'duplicate completed callback cannot overwrite terminal data'
);

select is(
  (select count(*)::integer from public.credit_ledger where job_id = '92000000-0000-4000-8000-000000000001' and kind in ('deepclean_capture', 'deepclean_release')),
  1,
  'duplicate completed callback has one terminal ledger effect'
);

select is(
  (public.finalize_deepclean_job_terminal(
    '92000000-0000-4000-8000-000000000001', 'failed',
    null, null, null, null, null, 'late failure', '{}'
  ) ->> 'outcome'),
  'conflict',
  'failed after completed is a conflict'
);

select is(
  (public.finalize_deepclean_job_terminal(
    '92000000-0000-4000-8000-000000000002', 'failed',
    null, null, 'engine', 7, 'gpu', 'processing failed', '{"failure":true}'
  ) ->> 'outcome'),
  'applied',
  'first failed callback applies'
);

select is(
  (select deepclean_credits from public.creator_profiles where user_id = '91000000-0000-4000-8000-000000000002'),
  8,
  'failed callback releases the reservation once'
);

select is(
  (select count(*)::integer from public.credit_ledger where job_id = '92000000-0000-4000-8000-000000000002' and kind = 'deepclean_release'),
  1,
  'failed callback creates one release ledger row'
);

select is(
  (public.finalize_deepclean_job_terminal(
    '92000000-0000-4000-8000-000000000002', 'failed',
    null, null, null, null, null, 'different failure', '{}'
  ) ->> 'outcome'),
  'duplicate',
  'replayed failed callback is duplicate'
);

select is(
  (select deepclean_credits from public.creator_profiles where user_id = '91000000-0000-4000-8000-000000000002'),
  8,
  'duplicate failed callback cannot double-refund'
);

select is(
  (public.finalize_deepclean_job_terminal(
    '92000000-0000-4000-8000-000000000002', 'completed',
    'late-output', null, null, null, null, null, '{}'
  ) ->> 'outcome'),
  'conflict',
  'completed after failed is a conflict'
);

select is(
  (select status from public.deepclean_jobs where id = '92000000-0000-4000-8000-000000000002'),
  'failed',
  'conflicting callback cannot overwrite terminal status'
);

select throws_ok(
  $$ insert into public.credit_ledger (user_id, job_id, kind, amount) values ('91000000-0000-4000-8000-000000000002', '92000000-0000-4000-8000-000000000002', 'deepclean_capture', 0) $$,
  '23505',
  null,
  'partial unique index forbids a second terminal ledger effect'
);

select * from finish();
rollback;
