begin;

create extension if not exists pgtap with schema extensions;
set search_path = public, extensions;

select plan(9);

insert into public.corpus_images
  (id, sha256, storage_path, file_name, byte_size, content_type, width, height)
values
  ('10000000-0000-4000-8000-000000000001', repeat('a', 64), repeat('a', 64) || '/original.jpg', 'one.jpg', 100, 'image/jpeg', 10, 10),
  ('10000000-0000-4000-8000-000000000002', repeat('b', 64), repeat('b', 64) || '/original.jpg', 'two.jpg', 100, 'image/jpeg', 10, 10);

insert into public.corpus_sets (id, name, version)
values
  ('20000000-0000-4000-8000-000000000001', 'Contract test', 1),
  ('20000000-0000-4000-8000-000000000002', 'Unlocked test', 1);

insert into public.corpus_set_members (corpus_set_id, corpus_image_id, position)
values ('20000000-0000-4000-8000-000000000001', '10000000-0000-4000-8000-000000000001', 8);

select lives_ok(
  $$ select * from public.lock_corpus_set('20000000-0000-4000-8000-000000000001') $$,
  'lock_corpus_set locks a non-empty set'
);

select is(
  (select position from public.corpus_set_members where corpus_set_id = '20000000-0000-4000-8000-000000000001'),
  1,
  'lock_corpus_set canonicalizes membership positions to dense 1..N'
);

select matches(
  (select manifest_sha256 from public.corpus_sets where id = '20000000-0000-4000-8000-000000000001'),
  '^[0-9a-f]{64}$',
  'lock_corpus_set records a SHA-256 manifest'
);

select throws_ok(
  $$ select * from public.lock_corpus_set('20000000-0000-4000-8000-000000000001') $$,
  '23514',
  'Corpus set is already locked.',
  'a corpus set cannot be locked twice'
);

select throws_ok(
  $$ insert into public.corpus_set_members (corpus_set_id, corpus_image_id, position) values ('20000000-0000-4000-8000-000000000001', '10000000-0000-4000-8000-000000000002', 2) $$,
  '23514',
  'Corpus set 20000000-0000-4000-8000-000000000001 is locked and immutable.',
  'locked-set membership INSERT is rejected'
);

select throws_ok(
  $$ update public.corpus_set_members set position = 2 where corpus_set_id = '20000000-0000-4000-8000-000000000001' $$,
  '23514',
  'Corpus set 20000000-0000-4000-8000-000000000001 is locked and immutable.',
  'locked-set membership UPDATE is rejected'
);

select throws_ok(
  $$ delete from public.corpus_set_members where corpus_set_id = '20000000-0000-4000-8000-000000000001' $$,
  '23514',
  'Corpus set 20000000-0000-4000-8000-000000000001 is locked and immutable.',
  'locked-set membership DELETE is rejected'
);

select throws_ok(
  $$ insert into public.corpus_experiments (corpus_set_id, engine_release, config_set) values ('20000000-0000-4000-8000-000000000002', 'test-engine', '["A"]') $$,
  '23514',
  'Experiments require a locked, active corpus set.',
  'experiments cannot reference an unlocked set'
);

insert into public.corpus_experiments
  (id, corpus_set_id, engine_release, detector_vendor, detector_mode, config_set)
values
  ('30000000-0000-4000-8000-000000000001', '20000000-0000-4000-8000-000000000001', 'test-engine', 'g1', 'real', '["A"]');

select throws_ok(
  $$ insert into public.corpus_run_intents (experiment_id, corpus_image_id, config_label, config_key, requested_settings_code, requested_settings_canonical, requested_settings_sha256) values ('30000000-0000-4000-8000-000000000001', '10000000-0000-4000-8000-000000000002', 'A', 'A', 'SEQ-CFA-test', '{}', repeat('c', 64)) $$,
  '23514',
  'Image is not a member of the experiment corpus set.',
  'run intent rejects an image outside the experiment set'
);

select * from finish();
rollback;
