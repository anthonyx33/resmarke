begin;

create extension if not exists pgtap with schema extensions;
set search_path = public, extensions;

select plan(36);

select throws_ok(
  $$ select public.finalize_deepclean_job_terminal('92000000-0000-4000-8000-000000000001', null) $$,
  '22023',
  'Invalid terminal status.',
  'null terminal status is rejected'
);

select throws_ok(
  $$ select public.finalize_deepclean_job_terminal(
    '92000000-0000-4000-8000-000000000001', 'completed',
    'not-a-sha', 'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb'
  ) $$,
  '22023',
  'Invalid output SHA-256.',
  'completed output SHA-256 is validated in the RPC'
);

select throws_ok(
  $$ select public.finalize_deepclean_job_terminal(
    '92000000-0000-4000-8000-000000000001', 'completed',
    'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa', 'NOT-LOWERCASE-SHA'
  ) $$,
  '22023',
  'Invalid input SHA-256.',
  'completed input SHA-256 is validated in the RPC'
);

select throws_ok(
  $$ select public.finalize_deepclean_job_terminal(
    '92000000-0000-4000-8000-000000000001', 'completed',
    'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
    'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb',
    null, -1
  ) $$,
  '22023',
  'Invalid runtime.',
  'negative runtime is rejected in the RPC'
);

select throws_ok(
  $$ select public.finalize_deepclean_job_terminal(
    '92000000-0000-4000-8000-000000000001', 'failed',
    null, null, 'engine', 7, 'gpu', '   ', '[]'::jsonb
  ) $$,
  '22023',
  'Invalid public report.',
  'non-object public report is rejected in the RPC'
);

select throws_ok(
  $$ select public.finalize_deepclean_job_terminal(
    '92000000-0000-4000-8000-000000000001', 'failed',
    null, null, 'engine', 7, 'gpu', '   ', '{}'::jsonb
  ) $$,
  '22023',
  'Invalid failure reason.',
  'blank failed reason is rejected in the RPC'
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
    'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
    'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb',
    'engine', 12, 'gpu', null, '{"public":true}'
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
    'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
    'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb',
    'engine', 12, 'gpu', null, '{"public":true}'
  ) ->> 'outcome'),
  'duplicate',
  'exact completed replay is duplicate'
);

select is(
  (public.finalize_deepclean_job_terminal(
    '92000000-0000-4000-8000-000000000001', 'completed',
    'cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc',
    'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb',
    'engine', 12, 'gpu', null, '{"public":true}'
  ) ->> 'conflict_kind'),
  'payload',
  'same completed status with different output SHA is a payload conflict'
);

select is(
  (public.finalize_deepclean_job_terminal(
    '92000000-0000-4000-8000-000000000001', 'completed',
    'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
    'dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd',
    'engine', 12, 'gpu', null, '{"public":true}'
  ) ->> 'outcome'),
  'conflict',
  'same completed status with different input SHA is conflict'
);

select is(
  (public.finalize_deepclean_job_terminal(
    '92000000-0000-4000-8000-000000000001', 'completed',
    'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
    'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb',
    'other-engine', 12, 'gpu', null, '{"public":true}'
  ) ->> 'outcome'),
  'conflict',
  'same completed status with different engine is conflict'
);

select is(
  (public.finalize_deepclean_job_terminal(
    '92000000-0000-4000-8000-000000000001', 'completed',
    'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
    'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb',
    'engine', 13, 'gpu', null, '{"public":true}'
  ) ->> 'outcome'),
  'conflict',
  'same completed status with different runtime is conflict'
);

select is(
  (public.finalize_deepclean_job_terminal(
    '92000000-0000-4000-8000-000000000001', 'completed',
    'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
    'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb',
    'engine', 12, 'other-gpu', null, '{"public":true}'
  ) ->> 'outcome'),
  'conflict',
  'same completed status with different GPU is conflict'
);

select is(
  (public.finalize_deepclean_job_terminal(
    '92000000-0000-4000-8000-000000000001', 'completed',
    'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
    'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb',
    'engine', 12, 'gpu', null, '{"public":false}'
  ) ->> 'outcome'),
  'conflict',
  'same completed status with different public report is conflict'
);

select is(
  (select output_sha256 from public.deepclean_jobs where id = '92000000-0000-4000-8000-000000000001'),
  'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
  'completed payload conflicts cannot overwrite terminal data'
);

select is(
  (select count(*)::integer from public.credit_ledger where job_id = '92000000-0000-4000-8000-000000000001' and kind in ('deepclean_capture', 'deepclean_release')),
  1,
  'completed replays and payload conflicts keep one terminal ledger effect'
);

select is(
  (public.finalize_deepclean_job_terminal(
    '92000000-0000-4000-8000-000000000001', 'failed',
    null, null, 'engine', 12, 'gpu', 'late failure', '{}'
  ) ->> 'conflict_kind'),
  'status',
  'failed after completed is a status conflict'
);

select is(
  (public.finalize_deepclean_job_terminal(
    '92000000-0000-4000-8000-000000000002', 'failed',
    null, null, 'engine', 7, 'gpu', '  processing failed  ', '{"failure":true}'
  ) ->> 'outcome'),
  'applied',
  'first failed callback applies'
);

select is(
  (select status from public.deepclean_jobs where id = '92000000-0000-4000-8000-000000000002'),
  'failed',
  'failed callback makes the job terminal'
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
    null, null, 'engine', 7, 'gpu', 'processing failed', '{"failure":true}'
  ) ->> 'outcome'),
  'duplicate',
  'normalized exact failed replay is duplicate'
);

select is(
  (public.finalize_deepclean_job_terminal(
    '92000000-0000-4000-8000-000000000002', 'failed',
    null, null, 'other-engine', 7, 'gpu', 'processing failed', '{"failure":true}'
  ) ->> 'outcome'),
  'conflict',
  'same failed status with different engine is conflict'
);

select is(
  (public.finalize_deepclean_job_terminal(
    '92000000-0000-4000-8000-000000000002', 'failed',
    null, null, 'engine', 8, 'gpu', 'processing failed', '{"failure":true}'
  ) ->> 'outcome'),
  'conflict',
  'same failed status with different runtime is conflict'
);

select is(
  (public.finalize_deepclean_job_terminal(
    '92000000-0000-4000-8000-000000000002', 'failed',
    null, null, 'engine', 7, 'other-gpu', 'processing failed', '{"failure":true}'
  ) ->> 'outcome'),
  'conflict',
  'same failed status with different GPU is conflict'
);

select is(
  (public.finalize_deepclean_job_terminal(
    '92000000-0000-4000-8000-000000000002', 'failed',
    null, null, 'engine', 7, 'gpu', 'different failure', '{"failure":true}'
  ) ->> 'conflict_kind'),
  'payload',
  'same failed status with different reason is payload conflict'
);

select is(
  (public.finalize_deepclean_job_terminal(
    '92000000-0000-4000-8000-000000000002', 'failed',
    null, null, 'engine', 7, 'gpu', 'processing failed', '{"failure":false}'
  ) ->> 'outcome'),
  'conflict',
  'same failed status with different public report is conflict'
);

select is(
  (select failure_reason from public.deepclean_jobs where id = '92000000-0000-4000-8000-000000000002'),
  'processing failed',
  'failed payload conflicts cannot overwrite normalized terminal data'
);

select is(
  (select deepclean_credits from public.creator_profiles where user_id = '91000000-0000-4000-8000-000000000002'),
  8,
  'failed replays and payload conflicts cannot double-refund'
);

select is(
  (select count(*)::integer from public.credit_ledger where job_id = '92000000-0000-4000-8000-000000000002' and kind in ('deepclean_capture', 'deepclean_release')),
  1,
  'failed replays and payload conflicts keep one terminal ledger effect'
);

select is(
  (public.finalize_deepclean_job_terminal(
    '92000000-0000-4000-8000-000000000002', 'completed',
    'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
    'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb',
    'engine', 7, 'gpu', null, '{}'
  ) ->> 'conflict_kind'),
  'status',
  'completed after failed is a status conflict'
);

select throws_ok(
  $$ insert into public.credit_ledger (user_id, job_id, kind, amount) values ('91000000-0000-4000-8000-000000000002', '92000000-0000-4000-8000-000000000002', 'deepclean_capture', 0) $$,
  '23505',
  null,
  'partial unique index forbids a second terminal ledger effect'
);

select is(
  (public.finalize_deepclean_job_terminal(
    '92000000-0000-4000-8000-000000000099', 'completed',
    'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
    'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb'
  ) ->> 'outcome'),
  'not_found',
  'valid terminal callback for a missing job is factual not-found'
);

select * from finish();
rollback;
