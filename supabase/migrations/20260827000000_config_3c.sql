-- Config 3C companion migration (master-engineer authored, OWNER-APPLIED).
-- Widens the config_label CHECKs to accept '3C'. Non-destructive; no data change.
-- Apply AFTER the code build is verified: the new CHECKs only relax, so the
-- app keeps working before application (3C runs would 400 on registration).

alter table public.corpus_run_intents
  drop constraint if exists corpus_run_intents_config_label_check;

alter table public.corpus_run_intents
  add constraint corpus_run_intents_config_label_check
  check (config_label in ('A', '1A', '2B', '3C', 'CUSTOM'));

alter table public.corpus_runs
  drop constraint if exists corpus_runs_config_label_check;

alter table public.corpus_runs
  add constraint corpus_runs_config_label_check
  check (config_label in ('A', '1A', '2B', '3C', 'CUSTOM'));
