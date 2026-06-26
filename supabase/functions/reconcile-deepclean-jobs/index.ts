import { corsHeaders, jsonResponse } from "../_shared/cors.ts";
import { adminClient, userFromRequest } from "../_shared/supabase.ts";

type ReconcileBody = {
  dry_run?: boolean;
  older_than_minutes?: number;
  timeout_minutes?: number;
  limit?: number;
};

type DeepcleanJob = {
  id: string;
  user_id: string;
  status: string;
  output_path: string;
  input_path: string;
  runpod_job_id: string | null;
  credits_reserved: number;
  updated_at: string;
  created_at: string;
  report: Record<string, unknown> | null;
};

type RunpodStatus = {
  id?: string;
  status?: string;
  output?: {
    ok?: boolean;
    job_id?: string;
    runtime_ms?: number;
    error?: string;
    [key: string]: unknown;
  };
  error?: string;
  [key: string]: unknown;
};

Deno.serve(async (request) => {
  if (request.method === "OPTIONS") return new Response("ok", { headers: corsHeaders });
  if (request.method !== "POST") return jsonResponse({ error: "Method not allowed" }, 405);

  try {
    await assertAuthorized(request);

    const body = (await request.json().catch(() => ({}))) as ReconcileBody;
    const dryRun = body.dry_run === true;
    const olderThanMinutes = clampInt(body.older_than_minutes ?? 20, 5, 24 * 60);
    const timeoutMinutes = clampInt(body.timeout_minutes ?? 60, olderThanMinutes, 24 * 60);
    const limit = clampInt(body.limit ?? 25, 1, 100);

    const client = adminClient();
    const cutoff = new Date(Date.now() - olderThanMinutes * 60_000).toISOString();

    const { data: jobs, error: jobsError } = await client
      .from("deepclean_jobs")
      .select("*")
      .eq("status", "processing")
      .lt("updated_at", cutoff)
      .order("updated_at", { ascending: true })
      .limit(limit);

    if (jobsError) throw jobsError;

    const results = [];
    for (const job of (jobs ?? []) as DeepcleanJob[]) {
      try {
        results.push(await reconcileJob(job, { dryRun, timeoutMinutes }));
      } catch (error) {
        results.push({
          job_id: job.id,
          runpod_job_id: job.runpod_job_id,
          action: "status_check_error",
          error: error instanceof Error ? error.message : "Unknown reconciliation error"
        });
      }
    }

    return jsonResponse({
      ok: true,
      dry_run: dryRun,
      checked: results.length,
      results
    });
  } catch (error) {
    return jsonResponse(
      { error: error instanceof Error ? error.message : "Could not reconcile jobs." },
      error instanceof ReconcileError ? error.status : 500
    );
  }
});

async function assertAuthorized(request: Request) {
  const authorization = request.headers.get("authorization") ?? "";
  const token = authorization.replace(/^Bearer\s+/i, "");
  const serviceKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");
  if (token && serviceKey && token === serviceKey) return;

  const { user } = await userFromRequest(request);
  const admins = (Deno.env.get("ADMIN_EMAILS") ?? "")
    .split(",")
    .map((item) => item.trim().toLowerCase())
    .filter(Boolean);

  if (!admins.length) throw new ReconcileError("ADMIN_EMAILS is not configured.", 403);
  if (!admins.includes((user.email ?? "").toLowerCase())) {
    throw new ReconcileError("Not authorized for reconciliation.", 403);
  }
}

async function reconcileJob(
  job: DeepcleanJob,
  options: { dryRun: boolean; timeoutMinutes: number }
) {
  const ageMinutes = Math.floor((Date.now() - Date.parse(job.created_at)) / 60_000);

  if (!job.runpod_job_id) {
    if (!options.dryRun) {
      await failAndRelease(job, "RunPod job id is missing during reconciliation.", null);
    }
    return {
      job_id: job.id,
      action: options.dryRun ? "would_fail_missing_runpod_id" : "failed_missing_runpod_id"
    };
  }

  let status: RunpodStatus;
  try {
    status = await getRunpodStatus(job.runpod_job_id);
  } catch (error) {
    const reason = error instanceof Error ? error.message : "RunPod status check failed.";
    if (ageMinutes >= options.timeoutMinutes) {
      if (!options.dryRun) await failAndRelease(job, reason, null);
      return {
        job_id: job.id,
        runpod_job_id: job.runpod_job_id,
        action: options.dryRun ? "would_release_status_error" : "released_status_error",
        reason
      };
    }
    return {
      job_id: job.id,
      runpod_job_id: job.runpod_job_id,
      action: "status_check_deferred",
      reason
    };
  }

  const normalized = normalizeRunpodStatus(status.status);

  if (normalized === "completed") {
    if (status.output?.ok === false) {
      const reason = status.output.error || "RunPod completed with failed worker output.";
      if (!options.dryRun) await failAndRelease(job, reason, status);
      return {
        job_id: job.id,
        runpod_job_id: job.runpod_job_id,
        runpod_status: status.status,
        action: options.dryRun ? "would_release_failed_output" : "released_failed_output",
        reason
      };
    }

    if (!options.dryRun) await captureCompleted(job, status);
    return {
      job_id: job.id,
      runpod_job_id: job.runpod_job_id,
      runpod_status: status.status,
      action: options.dryRun ? "would_capture_completed" : "captured_completed"
    };
  }

  if (normalized === "failed") {
    const reason = status.error || status.output?.error || `RunPod status ${status.status}`;
    if (!options.dryRun) await failAndRelease(job, reason, status);
    return {
      job_id: job.id,
      runpod_job_id: job.runpod_job_id,
      runpod_status: status.status,
      action: options.dryRun ? "would_release_failed" : "released_failed",
      reason
    };
  }

  if (ageMinutes >= options.timeoutMinutes) {
    const reason = `Timed out after ${ageMinutes} minutes while RunPod status is ${status.status ?? "unknown"}.`;
    if (!options.dryRun) await failAndRelease(job, reason, status);
    return {
      job_id: job.id,
      runpod_job_id: job.runpod_job_id,
      runpod_status: status.status,
      action: options.dryRun ? "would_release_timeout" : "released_timeout",
      reason
    };
  }

  return {
    job_id: job.id,
    runpod_job_id: job.runpod_job_id,
    runpod_status: status.status,
    action: "left_processing"
  };
}

async function captureCompleted(job: DeepcleanJob, status: RunpodStatus) {
  const client = adminClient();
  const now = new Date().toISOString();

  const { data: updated, error: updateError } = await client
    .from("deepclean_jobs")
    .update({
      status: "completed",
      credits_charged: job.credits_reserved,
      runtime_ms: status.output?.runtime_ms ?? null,
      engine_version: "reconciled-runpod-status",
      report: {
        ...(job.report ?? {}),
        reconciled: true,
        runpod_status: redactRunpodStatus(status)
      },
      updated_at: now,
      completed_at: now
    })
    .eq("id", job.id)
    .eq("status", "processing")
    .select("id")
    .maybeSingle();

  if (updateError) throw updateError;
  if (!updated) return;

  await client.from("credit_ledger").insert({
    user_id: job.user_id,
    job_id: job.id,
    kind: "deepclean_capture",
    amount: 0,
    metadata: { reconciled: true, runpod_job_id: job.runpod_job_id }
  });

  await client.storage.from("deepclean-inputs").remove([job.input_path]);
}

async function failAndRelease(
  job: DeepcleanJob,
  reason: string,
  status: RunpodStatus | null
) {
  const client = adminClient();
  const now = new Date().toISOString();

  const { data: updatedJob, error: jobError } = await client
    .from("deepclean_jobs")
    .update({
      status: "failed",
      credits_charged: 0,
      failure_reason: reason,
      report: {
        ...(job.report ?? {}),
        reconciled: true,
        runpod_status: status ? redactRunpodStatus(status) : null
      },
      updated_at: now,
      completed_at: now
    })
    .eq("id", job.id)
    .eq("status", "processing")
    .select("id")
    .maybeSingle();
  if (jobError) throw jobError;
  if (!updatedJob) return;

  const { data: profile, error: profileError } = await client
    .from("creator_profiles")
    .select("deepclean_credits")
    .eq("user_id", job.user_id)
    .single();
  if (profileError) throw profileError;

  const nextCredits = (profile?.deepclean_credits ?? 0) + job.credits_reserved;

  const { error: creditError } = await client
    .from("creator_profiles")
    .update({ deepclean_credits: nextCredits, updated_at: now })
    .eq("user_id", job.user_id);
  if (creditError) throw creditError;

  await client.from("credit_ledger").insert({
    user_id: job.user_id,
    job_id: job.id,
    kind: "deepclean_release",
    amount: job.credits_reserved,
    balance_after: nextCredits,
    metadata: { reconciled: true, reason, runpod_job_id: job.runpod_job_id }
  });

  await client.storage.from("deepclean-inputs").remove([job.input_path]);
}

async function getRunpodStatus(runpodJobId: string): Promise<RunpodStatus> {
  const endpointId = Deno.env.get("RUNPOD_ENDPOINT_ID");
  const apiKey = Deno.env.get("RUNPOD_API_KEY");
  if (!endpointId || !apiKey) throw new Error("RunPod status configuration is missing.");

  const response = await fetch(`https://api.runpod.ai/v2/${endpointId}/status/${runpodJobId}`, {
    method: "GET",
    headers: { authorization: `Bearer ${apiKey}` }
  });
  const payload = (await response.json().catch(() => ({}))) as RunpodStatus;
  if (!response.ok) {
    throw new Error(payload.error || `RunPod status failed with ${response.status}`);
  }
  return payload;
}

function normalizeRunpodStatus(status: string | undefined) {
  const value = (status ?? "").toUpperCase();
  if (["COMPLETED", "COMPLETED_WITH_ERRORS"].includes(value)) return "completed";
  if (["FAILED", "CANCELLED", "CANCELED", "TIMED_OUT", "TIMEOUT"].includes(value)) return "failed";
  return "processing";
}

function redactRunpodStatus(status: RunpodStatus) {
  return {
    id: status.id,
    status: status.status,
    output: status.output
      ? {
          ok: status.output.ok,
          job_id: status.output.job_id,
          runtime_ms: status.output.runtime_ms,
          error: status.output.error
        }
      : undefined,
    error: status.error
  };
}

function clampInt(value: number, min: number, max: number): number {
  if (!Number.isFinite(value)) return min;
  return Math.max(min, Math.min(max, Math.round(value)));
}

class ReconcileError extends Error {
  constructor(message: string, public status: number) {
    super(message);
  }
}
