import { corsHeaders, jsonResponse } from "../_shared/cors.ts";
import { userFromRequest } from "../_shared/supabase.ts";

type CreateJobBody = {
  file_name: string;
  file_size: number;
  content_type: string;
  creator_id?: string;
  profile: "standard" | "strong" | "max";
  output_mode: "stripped" | "sealed" | "sealed-stamped";
};

Deno.serve(async (request) => {
  if (request.method === "OPTIONS") return new Response("ok", { headers: corsHeaders });
  if (request.method !== "POST") return jsonResponse({ error: "Method not allowed" }, 405);

  try {
    const { client, user } = await userFromRequest(request);
    const body = (await request.json()) as CreateJobBody;
    const maxBytes = 25 * 1024 * 1024;

    if (!body.file_name || !body.content_type?.startsWith("image/")) {
      return jsonResponse({ error: "A supported image file is required." }, 400);
    }
    if (body.file_size > maxBytes) {
      return jsonResponse({ error: "DeepClean beta accepts images up to 25 MB." }, 400);
    }
    if (!["standard", "strong", "max"].includes(body.profile)) {
      return jsonResponse({ error: "Invalid DeepClean profile." }, 400);
    }
    if (!["stripped", "sealed", "sealed-stamped"].includes(body.output_mode)) {
      return jsonResponse({ error: "Invalid output mode." }, 400);
    }

    const { data: profile, error: profileError } = await client
      .from("creator_profiles")
      .select("deepclean_credits")
      .eq("user_id", user.id)
      .single();

    if (profileError) throw profileError;
    if (!profile || profile.deepclean_credits < 1) {
      return jsonResponse({ error: "No DeepClean credits available." }, 402);
    }

    const jobId = crypto.randomUUID();
    const extension = extensionForContentType(body.content_type);
    const inputPath = `${user.id}/${jobId}/input.${extension}`;
    const outputFileName = photoStyleOutputName();
    const outputPath = `${user.id}/${jobId}/${outputFileName}`;

    const { error: updateError } = await client
      .from("creator_profiles")
      .update({
        deepclean_credits: profile.deepclean_credits - 1,
        updated_at: new Date().toISOString()
      })
      .eq("user_id", user.id);

    if (updateError) throw updateError;

    const { error: ledgerError } = await client.from("credit_ledger").insert({
      user_id: user.id,
      job_id: jobId,
      kind: "deepclean_reserve",
      amount: -1,
      balance_after: profile.deepclean_credits - 1
    });
    if (ledgerError) throw ledgerError;

    const { error: jobError } = await client.from("deepclean_jobs").insert({
      id: jobId,
      user_id: user.id,
      status: "uploading",
      creator_id: (body.creator_id ?? user.email ?? user.id).slice(0, 180),
      profile: body.profile ?? "standard",
      output_mode: body.output_mode ?? "sealed",
      input_path: inputPath,
      output_path: outputPath,
      credits_reserved: 1
    });
    if (jobError) throw jobError;

    const { data: signedUpload, error: uploadError } = await client.storage
      .from("deepclean-inputs")
      .createSignedUploadUrl(inputPath);

    if (uploadError) throw uploadError;

    return jsonResponse({
      id: jobId,
      status: "uploading",
      uploadUrl: signedUpload.signedUrl,
      uploadToken: signedUpload.token,
      inputPath,
      outputPath,
      outputName: outputFileName
    });
  } catch (error) {
    return jsonResponse(
      { error: error instanceof Error ? error.message : "Could not create job." },
      500
    );
  }
});

function extensionForContentType(contentType: string): string {
  if (contentType.includes("png")) return "png";
  if (contentType.includes("webp")) return "webp";
  return "jpg";
}

function photoStyleOutputName(): string {
  const values = new Uint16Array(1);
  crypto.getRandomValues(values);
  const number = values[0] % 10000;
  return `IMG_${String(number).padStart(4, "0")}.JPG`;
}
