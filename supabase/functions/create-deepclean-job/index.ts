import { corsHeaders, jsonResponse } from "../_shared/cors.ts";
import { userFromRequest } from "../_shared/supabase.ts";

type CreateJobBody = {
  file_name: string;
  file_size: number;
  content_type: string;
  creator_id?: string;
  profile: "standard" | "standard-plus" | "strong" | "max";
  micro_texture_jitter?: boolean;
  expert_refinement?: unknown;
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
    if (!["standard", "standard-plus", "strong", "max"].includes(body.profile)) {
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
    const requestedProfile = body.profile ?? "standard";
    const storedProfile = requestedProfile === "standard-plus" ? "standard" : requestedProfile;
    const expertRefinement = normalizeExpertRefinement(body.expert_refinement);

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
      profile: storedProfile,
      output_mode: body.output_mode ?? "sealed",
      input_path: inputPath,
      output_path: outputPath,
      credits_reserved: 1,
      report: {
        requested_options: {
          profile_variant: requestedProfile === "standard-plus" ? "standard-plus" : null,
          micro_texture_jitter: requestedProfile === "max" && body.micro_texture_jitter === true,
          expert_refinement: expertRefinement
        }
      }
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

function normalizeExpertRefinement(input: unknown) {
  const modes = ["off", "light", "balanced", "optical"];
  const techniqueKeys = [
    "pixel_alignment_break",
    "sensor_noise_luma",
    "lens_vignette",
    "compression_texture",
    "bayer_cfa_lite",
    "lens_character",
    "double_quantization"
  ];
  const raw = isRecord(input) ? input : {};
  const mode = typeof raw.mode === "string" && modes.includes(raw.mode) ? raw.mode : "off";
  const intensity = clampNumber(raw.intensity, 0, 100, 45);
  const preserveStraightLines =
    typeof raw.preserve_straight_lines === "boolean" ? raw.preserve_straight_lines : true;
  const rawTechniques = isRecord(raw.techniques) ? raw.techniques : {};
  const techniques: Record<string, { enabled: boolean; value: number }> = {};

  for (const key of techniqueKeys) {
    if (isRecord(rawTechniques[key])) {
      const row = rawTechniques[key];
      techniques[key] = {
        enabled: typeof row.enabled === "boolean" ? row.enabled : false,
        value: clampNumber(row.value, 0, 1, 0)
      };
    }
  }

  return {
    mode,
    intensity,
    preserve_straight_lines: preserveStraightLines,
    techniques
  };
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function clampNumber(value: unknown, min: number, max: number, fallback: number): number {
  const parsed = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(parsed)) return fallback;
  return Math.min(max, Math.max(min, parsed));
}
