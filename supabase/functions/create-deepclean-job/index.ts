import { corsHeaders, jsonResponse } from "../_shared/cors.ts";
import { userFromRequest } from "../_shared/supabase.ts";

type CreateJobBody = {
  file_name: string;
  file_size: number;
  content_type: string;
  creator_id?: string;
  profile:
    | "standard"
    | "standard-plus"
    | "strong"
    | "max"
    | "max-mint"
    | "max-remint"
    | "max-optical-pro"
    | "max-neural-texture-lab"
    | "max-content-repair-lab";
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
    if (
      ![
        "standard",
        "standard-plus",
        "strong",
        "max",
        "max-mint",
        "max-remint",
        "max-optical-pro",
        "max-neural-texture-lab",
        "max-content-repair-lab"
      ].includes(body.profile)
    ) {
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
    const storedProfile =
      requestedProfile === "standard-plus"
        ? "standard"
        : requestedProfile === "max-mint"
        ? "max"
        : requestedProfile === "max-remint"
        ? "max"
        : requestedProfile === "max-optical-pro"
        ? "max"
        : requestedProfile === "max-neural-texture-lab"
        ? "max"
        : requestedProfile === "max-content-repair-lab"
        ? "max"
        : requestedProfile;
    const requestedOutputMode =
      requestedProfile === "max-mint" ||
      requestedProfile === "max-remint" ||
      requestedProfile === "max-optical-pro" ||
      requestedProfile === "max-neural-texture-lab" ||
      requestedProfile === "max-content-repair-lab"
        ? "stripped"
        : body.output_mode;
    const expertRefinement =
      requestedProfile === "max-mint"
        ? maxMintExpertRefinement()
        : requestedProfile === "max-remint"
        ? maxReMintExpertRefinement()
        : requestedProfile === "max-optical-pro"
        ? opticalProExpertRefinement()
        : requestedProfile === "max-neural-texture-lab"
        ? neuralTextureLabExpertRefinement()
        : requestedProfile === "max-content-repair-lab"
        ? contentRepairLabExpertRefinement()
        : normalizeExpertRefinement(body.expert_refinement);

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
      output_mode: requestedOutputMode ?? "sealed",
      input_path: inputPath,
      output_path: outputPath,
      credits_reserved: 1,
      report: {
        requested_options: {
          profile_variant: requestedProfile === "standard-plus" ? "standard-plus" : null,
          profile_layout:
            requestedProfile === "max-mint"
              ? "max-mint"
              : requestedProfile === "max-remint"
              ? "max-remint"
              : requestedProfile === "max-optical-pro"
              ? "max-optical-pro"
              : requestedProfile === "max-neural-texture-lab"
              ? "max-neural-texture-lab"
              : requestedProfile === "max-content-repair-lab"
              ? "max-content-repair-lab"
              : null,
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
  const modes = [
    "off",
    "light",
    "balanced",
    "optical",
    "optical-pro",
    "max-remint",
    "neural-texture-lab",
    "content-repair-lab"
  ];
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

function maxMintExpertRefinement() {
  return {
    mode: "optical",
    intensity: 97,
    preserve_straight_lines: true,
    techniques: {
      pixel_alignment_break: { enabled: true, value: 0.71 },
      sensor_noise_luma: { enabled: true, value: 0.61 },
      lens_vignette: { enabled: true, value: 0.29 },
      compression_texture: { enabled: true, value: 0.47 },
      bayer_cfa_lite: { enabled: true, value: 0.07 },
      lens_character: { enabled: true, value: 0.2 },
      double_quantization: { enabled: true, value: 0.23 }
    }
  };
}

function opticalProExpertRefinement() {
  return {
    mode: "optical-pro",
    intensity: 100,
    preserve_straight_lines: true,
    techniques: {}
  };
}

function maxReMintExpertRefinement() {
  return {
    mode: "max-remint",
    intensity: 100,
    preserve_straight_lines: true,
    techniques: {},
    max_remint: {
      preset: "balanced",
      optical_enabled: true,
      fft_strength: 0.35,
      fft_alpha: 2.0,
      fft_noise_floor: 0.012,
      repair_enabled: true,
      repair_preset: "balanced",
      repair_engine: "qwen",
      text_denoise: 0.72,
      geometry_denoise: 0.28,
      unify_amount: 0.16,
      min_psnr_db: 28.0,
      psnr_retry_steps: 3
    }
  };
}

function neuralTextureLabExpertRefinement() {
  return {
    mode: "neural-texture-lab",
    intensity: 100,
    preserve_straight_lines: true,
    techniques: {},
    neural_texture: {
      alpha: 0.6,
      model_name: "RealESRGAN_x4plus.pth"
    }
  };
}

function contentRepairLabExpertRefinement() {
  return {
    mode: "content-repair-lab",
    intensity: 100,
    preserve_straight_lines: true,
    techniques: {},
    content_repair: {
      preset: "balanced",
      patch_size: 256,
      stride: 128,
      candidate_threshold: 0.8,
      min_region_area_ratio: 0.004,
      max_regions: 3,
      mask_dilation_px: 10,
      mask_feather_px: 20
    }
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
