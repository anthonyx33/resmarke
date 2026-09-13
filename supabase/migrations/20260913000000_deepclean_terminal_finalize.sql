-- Atomic, idempotent terminal transitions for DeepClean worker callbacks.

create unique index if not exists credit_ledger_one_deepclean_terminal_effect_per_job
  on public.credit_ledger (job_id)
  where job_id is not null
    and kind in ('deepclean_capture', 'deepclean_release');

create or replace function public.finalize_deepclean_job_terminal(
  p_job_id uuid,
  p_terminal_status text,
  p_output_sha256 text default null,
  p_input_sha256 text default null,
  p_engine_version text default null,
  p_runtime_ms integer default null,
  p_gpu_type text default null,
  p_failure_reason text default null,
  p_report jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
  v_job public.deepclean_jobs%rowtype;
  v_balance integer;
  v_normalized_failure_reason text;
  v_normalized_report jsonb := coalesce(p_report, '{}'::jsonb);
  v_payload_matches boolean := false;
begin
  if p_job_id is null then
    raise exception 'Invalid job ID.' using errcode = '22023';
  end if;
  if p_terminal_status is null or p_terminal_status not in ('completed', 'failed') then
    raise exception 'Invalid terminal status.' using errcode = '22023';
  end if;
  if p_runtime_ms is not null and p_runtime_ms < 0 then
    raise exception 'Invalid runtime.' using errcode = '22023';
  end if;
  if jsonb_typeof(v_normalized_report) <> 'object' then
    raise exception 'Invalid public report.' using errcode = '22023';
  end if;

  if p_terminal_status = 'completed' then
    if p_output_sha256 is null or p_output_sha256 !~ '^[0-9a-f]{64}$' then
      raise exception 'Invalid output SHA-256.' using errcode = '22023';
    end if;
    if p_input_sha256 is null or p_input_sha256 !~ '^[0-9a-f]{64}$' then
      raise exception 'Invalid input SHA-256.' using errcode = '22023';
    end if;
  else
    v_normalized_failure_reason := btrim(coalesce(p_failure_reason, ''));
    if v_normalized_failure_reason = '' or char_length(v_normalized_failure_reason) > 2000 then
      raise exception 'Invalid failure reason.' using errcode = '22023';
    end if;
  end if;

  select *
    into v_job
    from public.deepclean_jobs
    where id = p_job_id
    for update;

  if not found then
    return jsonb_build_object(
      'outcome', 'not_found',
      'job_id', p_job_id,
      'attempted_status', p_terminal_status
    );
  end if;

  if v_job.status in ('completed', 'failed') then
    if v_job.status = p_terminal_status then
      if p_terminal_status = 'completed' then
        v_payload_matches :=
          v_job.output_sha256 is not distinct from p_output_sha256 and
          v_job.input_sha256 is not distinct from p_input_sha256 and
          v_job.engine_version is not distinct from p_engine_version and
          v_job.runtime_ms is not distinct from p_runtime_ms and
          v_job.gpu_type is not distinct from p_gpu_type and
          v_job.report is not distinct from v_normalized_report;
      else
        v_payload_matches :=
          v_job.engine_version is not distinct from p_engine_version and
          v_job.runtime_ms is not distinct from p_runtime_ms and
          v_job.gpu_type is not distinct from p_gpu_type and
          v_job.failure_reason is not distinct from v_normalized_failure_reason and
          v_job.report is not distinct from v_normalized_report;
      end if;

      if not v_payload_matches then
        return jsonb_build_object(
          'outcome', 'conflict',
          'conflict', true,
          'conflict_kind', 'payload',
          'job_id', p_job_id,
          'existing_status', v_job.status,
          'attempted_status', p_terminal_status
        );
      end if;
      return jsonb_build_object(
        'outcome', 'duplicate',
        'duplicate', true,
        'job_id', p_job_id,
        'terminal_status', v_job.status
      );
    end if;
    return jsonb_build_object(
      'outcome', 'conflict',
      'conflict', true,
      'conflict_kind', 'status',
      'job_id', p_job_id,
      'existing_status', v_job.status,
      'attempted_status', p_terminal_status
    );
  end if;

  if p_terminal_status = 'completed' then
    update public.deepclean_jobs
      set status = 'completed',
          credits_charged = v_job.credits_reserved,
          output_sha256 = p_output_sha256,
          input_sha256 = p_input_sha256,
          engine_version = p_engine_version,
          runtime_ms = p_runtime_ms,
          gpu_type = p_gpu_type,
          failure_reason = null,
          report = v_normalized_report,
          updated_at = now(),
          completed_at = now()
      where id = v_job.id;

    insert into public.credit_ledger
      (user_id, job_id, kind, amount, metadata)
    values
      (v_job.user_id, v_job.id, 'deepclean_capture', 0,
       jsonb_build_object('output_sha256', p_output_sha256));
  else
    update public.creator_profiles
      set deepclean_credits = deepclean_credits + v_job.credits_reserved,
          updated_at = now()
      where user_id = v_job.user_id
      returning deepclean_credits into v_balance;

    if not found then
      raise exception 'Creator profile not found.' using errcode = 'P0002';
    end if;

    update public.deepclean_jobs
      set status = 'failed',
          credits_charged = 0,
          failure_reason = v_normalized_failure_reason,
          engine_version = p_engine_version,
          runtime_ms = p_runtime_ms,
          gpu_type = p_gpu_type,
          report = v_normalized_report,
          updated_at = now(),
          completed_at = now()
      where id = v_job.id;

    insert into public.credit_ledger
      (user_id, job_id, kind, amount, balance_after, metadata)
    values
      (v_job.user_id, v_job.id, 'deepclean_release', v_job.credits_reserved,
       v_balance, jsonb_build_object(
         'failure_reason', v_normalized_failure_reason
       ));
  end if;

  return jsonb_build_object(
    'outcome', 'applied',
    'duplicate', false,
    'job_id', p_job_id,
    'terminal_status', p_terminal_status
  );
end;
$$;

revoke all on function public.finalize_deepclean_job_terminal(
  uuid, text, text, text, text, integer, text, text, jsonb
) from public, anon, authenticated;
grant execute on function public.finalize_deepclean_job_terminal(
  uuid, text, text, text, text, integer, text, text, jsonb
) to service_role;
