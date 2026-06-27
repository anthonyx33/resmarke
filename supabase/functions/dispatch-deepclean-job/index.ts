import { corsHeaders, jsonResponse } from "../_shared/cors.ts";
import { userFromRequest } from "../_shared/supabase.ts";

Deno.serve(async (request) => {
  if (request.method === "OPTIONS") return new Response("ok", { headers: corsHeaders });
  if (request.method !== "POST") return jsonResponse({ error: "Method not allowed" }, 405);

  try {
    const { client, user } = await userFromRequest(request);
    const { job_id } = (await request.json()) as { job_id: string };
    if (!job_id) return jsonResponse({ error: "job_id is required." }, 400);

    const { data: job, error: jobError } = await client
      .from("deepclean_jobs")
      .select("*")
      .eq("id", job_id)
      .eq("user_id", user.id)
      .single();

    if (jobError) throw jobError;
    if (!job) return jsonResponse({ error: "Job not found." }, 404);

    const { data: inputSigned, error: inputError } = await client.storage
      .from("deepclean-inputs")
      .createSignedUrl(job.input_path, 60 * 20);
    if (inputError) throw inputError;

    const supabaseUrl = Deno.env.get("SUPABASE_URL");
    const runpodApiKey = Deno.env.get("RUNPOD_API_KEY");
    const runpodEndpointId = Deno.env.get("RUNPOD_ENDPOINT_ID");
    const webhookSecret = Deno.env.get("DEEPCLEAN_WEBHOOK_SECRET");

    if (!supabaseUrl || !runpodApiKey || !runpodEndpointId || !webhookSecret) {
      throw new Error("Missing RunPod or webhook configuration.");
    }

    const report = (job.report ?? {}) as Record<string, unknown>;
    const requestedOptions = (report.requested_options ?? {}) as Record<string, unknown>;
    const workerProfile =
      requestedOptions.profile_variant === "standard-plus"
        ? "standard-plus"
        : job.profile === "max" && requestedOptions.micro_texture_jitter === true
        ? "max-jitter"
        : job.profile;

    const webhookUrl = `${supabaseUrl}/functions/v1/deepclean-webhook`;
    const payload = {
      input: {
        job_id: job.id,
        creator_id: job.creator_id || user.email || user.id,
        profile: workerProfile,
        output_mode: job.output_mode,
        input_url: inputSigned.signedUrl,
        input_path: job.input_path,
        output_path: job.output_path,
        webhook_url: webhookUrl,
        webhook_secret: webhookSecret
      }
    };

    const runpodResponse = await fetch(
      `https://api.runpod.ai/v2/${runpodEndpointId}/run`,
      {
        method: "POST",
        headers: {
          "content-type": "application/json",
          authorization: `Bearer ${runpodApiKey}`
        },
        body: JSON.stringify(payload)
      }
    );

    if (!runpodResponse.ok) {
      throw new Error(`RunPod dispatch failed with ${runpodResponse.status}`);
    }
    const runpodBody = await runpodResponse.json().catch(() => ({}));

    await client
      .from("deepclean_jobs")
      .update({
        status: "processing",
        runpod_job_id: runpodBody.id ?? runpodBody.job_id ?? null,
        updated_at: new Date().toISOString()
      })
      .eq("id", job.id);

    return jsonResponse({ ok: true, job_id: job.id });
  } catch (error) {
    return jsonResponse(
      { error: error instanceof Error ? error.message : "Could not dispatch job." },
      500
    );
  }
});
