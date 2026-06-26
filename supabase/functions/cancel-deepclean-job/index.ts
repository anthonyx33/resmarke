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

    if (job.status === "completed" || job.status === "failed") {
      return jsonResponse({ ok: true, status: job.status });
    }

    const { data: profile, error: profileError } = await client
      .from("creator_profiles")
      .select("deepclean_credits")
      .eq("user_id", user.id)
      .single();
    if (profileError) throw profileError;

    const nextCredits = (profile?.deepclean_credits ?? 0) + job.credits_reserved;
    const now = new Date().toISOString();

    await client
      .from("creator_profiles")
      .update({ deepclean_credits: nextCredits, updated_at: now })
      .eq("user_id", user.id);

    await client
      .from("deepclean_jobs")
      .update({
        status: "failed",
        credits_charged: 0,
        failure_reason: "Cancelled before GPU processing completed.",
        updated_at: now,
        completed_at: now
      })
      .eq("id", job.id);

    await client.storage.from("deepclean-inputs").remove([job.input_path]);

    await client.from("credit_ledger").insert({
      user_id: user.id,
      job_id: job.id,
      kind: "deepclean_release",
      amount: job.credits_reserved,
      balance_after: nextCredits,
      metadata: { reason: "cancelled" }
    });

    return jsonResponse({ ok: true, status: "failed" });
  } catch (error) {
    return jsonResponse(
      { error: error instanceof Error ? error.message : "Could not cancel job." },
      500
    );
  }
});
