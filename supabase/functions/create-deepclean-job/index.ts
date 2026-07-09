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
    | "max-optimised-remint"
    | "max-optical-pro"
    | "max-neural-texture-lab"
    | "max-content-repair-lab"
    | "max-cx-remint"
    | "max-cx-remint-v2"
    | "max-cx-remint-v3"
    | "max-cx-remint-v4";
  micro_texture_jitter?: boolean;
  expert_refinement?: unknown;
  // CX Remint is the only Max profile with user-facing options (quality-floor
  // slider, iPhone EXIF toggle, template/adaptive). They are validated and
  // clamped server-side in cxRemintExpertRefinement().
  cx_remint?: unknown;
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
        "max-optimised-remint",
        "max-optical-pro",
        "max-neural-texture-lab",
        "max-content-repair-lab",
        "max-cx-remint",
        "max-cx-remint-v2",
        "max-cx-remint-v3",
        "max-cx-remint-v4"
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
        : requestedProfile === "max-optimised-remint"
        ? "max"
        : requestedProfile === "max-optical-pro"
        ? "max"
        : requestedProfile === "max-neural-texture-lab"
        ? "max"
        : requestedProfile === "max-content-repair-lab"
        ? "max"
        : requestedProfile === "max-cx-remint"
        ? "max"
        : requestedProfile === "max-cx-remint-v2"
        ? "max"
        : requestedProfile === "max-cx-remint-v3"
        ? "max"
        : requestedProfile === "max-cx-remint-v4"
        ? "max"
        : requestedProfile;
    const requestedOutputMode =
      requestedProfile === "max-mint" ||
      requestedProfile === "max-remint" ||
      requestedProfile === "max-optimised-remint" ||
      requestedProfile === "max-optical-pro" ||
      requestedProfile === "max-neural-texture-lab" ||
      requestedProfile === "max-content-repair-lab" ||
      requestedProfile === "max-cx-remint" ||
      requestedProfile === "max-cx-remint-v2" ||
      requestedProfile === "max-cx-remint-v3" ||
      requestedProfile === "max-cx-remint-v4"
        ? "stripped"
        : body.output_mode;
    const expertRefinement =
      requestedProfile === "max-mint"
        ? maxMintExpertRefinement()
        : requestedProfile === "max-remint"
        ? maxReMintExpertRefinement()
        : requestedProfile === "max-optimised-remint"
        ? maxOptimisedReMintExpertRefinement()
        : requestedProfile === "max-optical-pro"
        ? opticalProExpertRefinement()
        : requestedProfile === "max-neural-texture-lab"
        ? neuralTextureLabExpertRefinement()
        : requestedProfile === "max-content-repair-lab"
        ? contentRepairLabExpertRefinement()
        : requestedProfile === "max-cx-remint"
        ? cxRemintExpertRefinement(body.cx_remint, "plain")
        : requestedProfile === "max-cx-remint-v2"
        ? cxRemintExpertRefinement(body.cx_remint, "deep")
        : requestedProfile === "max-cx-remint-v3"
        ? cxRemintExpertRefinement(body.cx_remint, "deep-color")
        : requestedProfile === "max-cx-remint-v4"
        ? cxRemintExpertRefinement(body.cx_remint, "deep-hist")
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
              : requestedProfile === "max-optimised-remint"
              ? "max-optimised-remint"
              : requestedProfile === "max-optical-pro"
              ? "max-optical-pro"
              : requestedProfile === "max-neural-texture-lab"
              ? "max-neural-texture-lab"
              : requestedProfile === "max-content-repair-lab"
              ? "max-content-repair-lab"
              : requestedProfile === "max-cx-remint"
              ? "max-cx-remint"
              : requestedProfile === "max-cx-remint-v2"
              ? "max-cx-remint-v2"
              : requestedProfile === "max-cx-remint-v3"
              ? "max-cx-remint-v3"
              : requestedProfile === "max-cx-remint-v4"
              ? "max-cx-remint-v4"
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
    "max-optimised-remint",
    "neural-texture-lab",
    "content-repair-lab",
    "max-cx-remint"
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

function maxOptimisedReMintExpertRefinement() {
  return {
    mode: "max-optimised-remint",
    intensity: 100,
    preserve_straight_lines: true,
    techniques: {},
    max_optimised_remint: {
      preset: "balanced",
      adaptive_level: 4,
      adaptive_level_min: 3,
      adaptive_level_max: 6,
      process_cap: 1800,
      timeout: 280,
      unsharp_radius: 1.2,
      unsharp_percent: 35,
      unsharp_threshold: 2,
      min_psnr_db: 28.0,
      min_ssim: 0.9,
      skip_if_processed: true
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

function cxRemintExpertRefinement(
  input: unknown,
  tier: "plain" | "deep" | "deep-color" | "deep-hist"
) {
  // CX Remint: non-generative de-flag + camera re-acquisition. User options are
  // whitelisted here so the client can never smuggle an out-of-range value or a
  // sub-768 output floor to the worker.
  //
  // tier:
  //   plain       (v1) - non-generative only. Does NOT remove SynthID.
  //   deep        (v2) - regenerate (breaks SynthID) + FFT spectral reshape.
  //   deep-color  (v3) - deep + mean/std colour restoration from the original.
  //   deep-hist   (v4) - deep + FULL histogram tone match (fixes the S-curve
  //                      over-contrast v3 left), lower unsharp, final tone lock
  //                      and a camera-realism boost. The recommended tier.
  const deep = tier === "deep" || tier === "deep-color" || tier === "deep-hist";
  const colorRestore = tier === "deep-color" || tier === "deep-hist";
  const histogram = tier === "deep-hist";
  const raw = isRecord(input) ? input : {};
  const engineModes = ["template", "adaptive"];
  const qualityFloors = ["studio", "high", "balanced", "strong", "floor"];
  const acquisitions = ["conservative", "balanced", "aggressive"];
  const devices = [
    "auto",
    "iphone-16-pro-max",
    "iphone-16-pro",
    "iphone-16",
    "iphone-15-pro-max",
    "iphone-15-pro",
    "iphone-15",
    "iphone-14-pro"
  ];

  const engineMode =
    typeof raw.engine_mode === "string" && engineModes.includes(raw.engine_mode)
      ? raw.engine_mode
      : "template";
  const qualityFloor =
    typeof raw.quality_floor === "string" && qualityFloors.includes(raw.quality_floor)
      ? raw.quality_floor
      : "balanced";
  const acquisition =
    typeof raw.acquisition === "string" && acquisitions.includes(raw.acquisition)
      ? raw.acquisition
      : "balanced";
  const device =
    typeof raw.device === "string" && devices.includes(raw.device) ? raw.device : "auto";
  const iphoneExif = typeof raw.iphone_exif === "boolean" ? raw.iphone_exif : true;

  return {
    mode: "max-cx-remint",
    intensity: 100,
    preserve_straight_lines: true,
    techniques: {},
    max_cx_remint: {
      engine_mode: engineMode,
      quality_floor: qualityFloor,
      acquisition,
      iphone_exif: iphoneExif,
      device,
      jpeg_quality: 92,
      jpeg_subsampling: "4:2:0",
      ai_threshold: 0.5,
      max_rungs: 5,
      // v2/v3 "Deep": regenerate to break SynthID, then spectral-reshape to
      // strip the diffusion fingerprint. regen_level 8 is the level that removed
      // SynthID in the live test.
      pre_regen: deep,
      regen_level: 8,
      spectral_reshape: deep,
      spectral_strength: 0.3,
      // v3/v4: restore the original's palette after regen.
      color_restore: colorRestore,
      color_restore_strength: 0.8,
      // v4 only: full histogram tone match (fixes over-contrast), softer
      // sharpen, and a camera-realism boost aimed at general AI classifiers.
      color_restore_method: histogram ? "histogram" : "mean_std",
      sharpen_percent: histogram ? 24 : 42,
      realism_boost: histogram ? 0.35 : 0.0
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
