import { corsHeaders, jsonResponse } from "../_shared/cors.ts";
import { userFromRequest } from "../_shared/supabase.ts";

Deno.serve(async (request) => {
  if (request.method === "OPTIONS") return new Response("ok", { headers: corsHeaders });
  if (request.method !== "POST") return jsonResponse({ error: "Method not allowed" }, 405);

  try {
    const { client, user } = await userFromRequest(request);
    const { job_id } = (await request.json()) as { job_id: string };
    if (!job_id) return jsonResponse({ error: "job_id is required." }, 400);

    const { data: job, error } = await client
      .from("deepclean_jobs")
      .select("*")
      .eq("id", job_id)
      .eq("user_id", user.id)
      .single();

    if (error) throw error;
    if (!job) return jsonResponse({ error: "Job not found." }, 404);

    let outputUrl: string | undefined;
    if (job.status === "completed") {
      const { data: signed, error: signedError } = await client.storage
        .from("deepclean-outputs")
        .createSignedUrl(job.output_path, 60 * 15, {
          download: "resmarke-deepclean.jpg"
        });
      if (signedError) throw signedError;
      outputUrl = signed.signedUrl;
    }

    return jsonResponse({
      id: job.id,
      status: job.status,
      outputPath: job.output_path,
      outputUrl,
      runtimeMs: job.runtime_ms,
      gpuType: job.gpu_type,
      report: job.report,
      failureReason: job.failure_reason
    });
  } catch (error) {
    return jsonResponse(
      { error: error instanceof Error ? error.message : "Could not read job." },
      500
    );
  }
});
