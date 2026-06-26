import { corsHeaders, jsonResponse } from "../_shared/cors.ts";
import { adminClient } from "../_shared/supabase.ts";

type WebhookBody = {
  job_id: string;
  status: "completed" | "failed";
  output_sha256?: string;
  input_sha256?: string;
  engine_version?: string;
  runtime_ms?: number;
  gpu_type?: string;
  failure_reason?: string;
  report?: Record<string, unknown>;
  signature?: string;
};

Deno.serve(async (request) => {
  if (request.method === "OPTIONS") return new Response("ok", { headers: corsHeaders });
  if (request.method !== "POST") return jsonResponse({ error: "Method not allowed" }, 405);

  try {
    const body = (await request.json()) as WebhookBody;
    const expectedSecret = Deno.env.get("DEEPCLEAN_WEBHOOK_SECRET");
    if (!expectedSecret || body.signature !== expectedSecret) {
      return jsonResponse({ error: "Invalid webhook signature." }, 401);
    }

    const client = adminClient();
    const { data: job, error: jobError } = await client
      .from("deepclean_jobs")
      .select("*")
      .eq("id", body.job_id)
      .single();
    if (jobError) throw jobError;
    if (!job) return jsonResponse({ error: "Job not found." }, 404);
    if (job.status === "completed" || job.status === "failed") {
      return jsonResponse({ ok: true, duplicate: true });
    }

    const now = new Date().toISOString();
    if (body.status === "completed") {
      const { error: updateError } = await client
        .from("deepclean_jobs")
        .update({
          status: "completed",
          credits_charged: job.credits_reserved,
          output_sha256: body.output_sha256,
          input_sha256: body.input_sha256,
          engine_version: body.engine_version,
          runtime_ms: body.runtime_ms,
          gpu_type: body.gpu_type,
          report: body.report ?? {},
          updated_at: now,
          completed_at: now
        })
        .eq("id", job.id);
      if (updateError) throw updateError;

      await client.from("credit_ledger").insert({
        user_id: job.user_id,
        job_id: job.id,
        kind: "deepclean_capture",
        amount: 0,
        metadata: { output_sha256: body.output_sha256 }
      });
    } else {
      const { data: profile, error: profileError } = await client
        .from("creator_profiles")
        .select("deepclean_credits")
        .eq("user_id", job.user_id)
        .single();
      if (profileError) throw profileError;

      const nextCredits = (profile?.deepclean_credits ?? 0) + job.credits_reserved;
      await client
        .from("creator_profiles")
        .update({ deepclean_credits: nextCredits, updated_at: now })
        .eq("user_id", job.user_id);

      await client
        .from("deepclean_jobs")
        .update({
          status: "failed",
          credits_charged: 0,
          failure_reason: body.failure_reason ?? "Worker failed.",
          engine_version: body.engine_version,
          runtime_ms: body.runtime_ms,
          gpu_type: body.gpu_type,
          report: body.report ?? {},
          updated_at: now,
          completed_at: now
        })
        .eq("id", job.id);

      await client.from("credit_ledger").insert({
        user_id: job.user_id,
        job_id: job.id,
        kind: "deepclean_release",
        amount: job.credits_reserved,
        balance_after: nextCredits,
        metadata: { failure_reason: body.failure_reason ?? "Worker failed." }
      });
    }

    return jsonResponse({ ok: true });
  } catch (error) {
    return jsonResponse(
      { error: error instanceof Error ? error.message : "Webhook failed." },
      500
    );
  }
});
