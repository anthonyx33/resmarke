import { supabase } from "./supabase";
import { throwSupabaseFunctionError } from "./supabaseFunctionError";

export type DeepCleanProfile =
  | "standard"
  | "standard-plus"
  | "strong"
  | "max"
  | "max-mint";
export type DeepCleanOutputMode = "stripped" | "sealed" | "sealed-stamped";

export type CxRemintQualityFloor = "studio" | "high" | "balanced" | "strong" | "floor";
export type CxRemintEngineMode = "template" | "adaptive";
export type CxRemintAcquisition = "conservative" | "balanced" | "aggressive";
export type CxRemintResolutionMode = "off" | "standard" | "custom";
export type CxRemintDevice =
  | "auto"
  | "iphone-16-pro-max"
  | "iphone-16-pro"
  | "iphone-16"
  | "iphone-15-pro-max"
  | "iphone-15-pro"
  | "iphone-15"
  | "iphone-14-pro";

export type CxRemintOptions = {
  engineMode: CxRemintEngineMode;
  qualityFloor: CxRemintQualityFloor;
  acquisition: CxRemintAcquisition;
  iphoneExif: boolean;
  device: CxRemintDevice;
  resolutionMode: CxRemintResolutionMode;
  resolutionX: number;
  resolutionY: number;
};

export type DsRemintV6Options = {
  engineMode: CxRemintEngineMode;
  qualityFloor: CxRemintQualityFloor;
  acquisition: CxRemintAcquisition;
  iphoneExif: boolean;
  device: CxRemintDevice;
  outputTarget: number | null;
  sharpenPercent?: number;
  textureAmount?: number;
  spectralStrength?: number;
};

export type DsRemintV7Options = {
  engineMode: CxRemintEngineMode;
  iphoneExif: boolean;
  aiThreshold?: number;
  sourceThreshold?: number;
};

export type DsRemintV8QualityFloor = "studio" | "high" | "balanced" | "strong";

export type DsRemintV8Options = {
  engineMode: CxRemintEngineMode;
  qualityFloor: DsRemintV8QualityFloor;
  iphoneExif: boolean;
  metadataMode?: "device" | "minimal";
  device: CxRemintDevice;
  resolutionMode: CxRemintResolutionMode;
  resolutionX: number;
  resolutionY: number;
};

export type DsRemintV8_2Options = {
  engineMode: CxRemintEngineMode;
  qualityFloor: "studio" | "balanced" | "strong";
  iphoneExif: boolean;
  metadataMode?: "device" | "minimal";
  restoreEngine?: "neural" | "classical";
};

export type DsRemintV8_3Options = {
  engineMode: CxRemintEngineMode;
  qualityFloor: "studio" | "balanced" | "strong";
  washModel: "qwen" | "zimage" | "qwen+zimage";
  restoreEngine: "neural" | "classical";
  iphoneExif: boolean;
  metadataMode?: "device" | "minimal";
};

export type DsRemintV8_8Options = {
  engineMode: CxRemintEngineMode;
  washModel: "qwen" | "zimage" | "qwen+zimage";
  strength: "light" | "balanced" | "deep";
  iphoneExif: boolean;
  metadataMode?: "device" | "minimal";
};
export type ExpertRefinementMode = "off" | "light" | "balanced" | "optical";
export type ExpertRefinementTechnique =
  | "pixel_alignment_break"
  | "sensor_noise_luma"
  | "lens_vignette"
  | "compression_texture"
  | "bayer_cfa_lite"
  | "lens_character"
  | "double_quantization";

export type ExpertRefinementSettings = {
  mode: ExpertRefinementMode;
  intensity: number;
  preserve_straight_lines: boolean;
  techniques: Record<
    ExpertRefinementTechnique,
    {
      enabled: boolean;
      value: number;
    }
  >;
};

export type DeepCleanJob = {
  id: string;
  status: "queued" | "uploading" | "processing" | "completed" | "failed";
  uploadUrl?: string;
  uploadToken?: string;
  inputPath?: string;
  outputPath?: string;
  outputName?: string;
  outputUrl?: string;
  runtimeMs?: number;
  gpuType?: string;
  report?: Record<string, unknown>;
  failureReason?: string;
};

export async function createDeepCleanJob(params: {
  file: File;
  creatorId: string;
  profile:
    | DeepCleanProfile
    | "max-remint"
    | "max-optimised-remint"
    | "max-optical-pro"
    | "max-neural-texture-lab"
    | "max-content-repair-lab"
    | "max-cx-remint"
    | "max-cx-remint-v2"
    | "max-cx-remint-v3"
    | "max-cx-remint-v4"
    | "max-cx-remint-v5"
    | "ds-remint-v6"
    | "ds-remint-v7"
    | "ds-remint-v8"
    | "ds-remint-v8.1"
    | "ds-remint-v8.2"
    | "ds-remint-v8.3"
    | "ds-remint-v8.8";
  outputMode: DeepCleanOutputMode;
  microTextureJitter?: boolean;
  expertRefinement?: ExpertRefinementSettings;
  cxRemint?: CxRemintOptions;
  dsRemintV6?: DsRemintV6Options;
  dsRemintV7?: DsRemintV7Options;
  dsRemintV8?: DsRemintV8Options;
  dsRemintV82?: DsRemintV8_2Options;
  dsRemintV83?: DsRemintV8_3Options;
  dsRemintV88?: DsRemintV8_8Options;
  outputNameStyle?: "photo-style" | "original" | "custom";
  outputNameCustom?: string;
}): Promise<DeepCleanJob> {
  if (!supabase) {
    throw new Error("Supabase is not configured for Remarkee Max jobs.");
  }

  const { data, error } = await supabase.functions.invoke("create-deepclean-job", {
    body: {
      file_name: params.file.name,
      file_size: params.file.size,
      content_type: params.file.type || "application/octet-stream",
      creator_id: params.creatorId,
      profile: params.profile,
      output_mode: params.outputMode,
      micro_texture_jitter: Boolean(params.microTextureJitter),
      expert_refinement: params.expertRefinement,
      cx_remint: params.cxRemint
        ? {
            engine_mode: params.cxRemint.engineMode,
            quality_floor: params.cxRemint.qualityFloor,
            acquisition: params.cxRemint.acquisition,
            iphone_exif: params.cxRemint.iphoneExif,
            device: params.cxRemint.device,
            resolution_mode: params.cxRemint.resolutionMode,
            x_resolution: params.cxRemint.resolutionX,
            y_resolution: params.cxRemint.resolutionY
          }
        : undefined,
      ds_remint_v6: params.dsRemintV6
        ? {
            engine_mode: params.dsRemintV6.engineMode,
            quality_floor: params.dsRemintV6.qualityFloor,
            acquisition: params.dsRemintV6.acquisition,
            iphone_exif: params.dsRemintV6.iphoneExif,
            device: params.dsRemintV6.device,
            output_target: params.dsRemintV6.outputTarget,
            sharpen_percent: params.dsRemintV6.sharpenPercent,
            texture_amount: params.dsRemintV6.textureAmount,
            spectral_strength: params.dsRemintV6.spectralStrength
          }
        : undefined,
      ds_remint_v7: params.dsRemintV7
        ? {
            engine_mode: params.dsRemintV7.engineMode,
            iphone_exif: params.dsRemintV7.iphoneExif,
            ai_threshold: params.dsRemintV7.aiThreshold,
            source_threshold: params.dsRemintV7.sourceThreshold
          }
        : undefined,
      ds_remint_v8: params.dsRemintV8
        ? {
            engine_mode: params.dsRemintV8.engineMode,
            quality_floor: params.dsRemintV8.qualityFloor,
            iphone_exif: params.dsRemintV8.iphoneExif,
            metadata_mode: params.dsRemintV8.metadataMode,
            device: params.dsRemintV8.device,
            resolution_mode: params.dsRemintV8.resolutionMode,
            x_resolution: params.dsRemintV8.resolutionX,
            y_resolution: params.dsRemintV8.resolutionY
          }
        : undefined,
      ds_remint_v8_2: params.dsRemintV82
        ? {
            engine_mode: params.dsRemintV82.engineMode,
            quality_floor: params.dsRemintV82.qualityFloor,
            iphone_exif: params.dsRemintV82.iphoneExif,
            metadata_mode: params.dsRemintV82.metadataMode,
            restore_engine: params.dsRemintV82.restoreEngine
          }
        : undefined,
      ds_remint_v8_3: params.dsRemintV83
        ? {
            engine_mode: params.dsRemintV83.engineMode,
            quality_floor: params.dsRemintV83.qualityFloor,
            wash_model: params.dsRemintV83.washModel,
            restore_engine: params.dsRemintV83.restoreEngine,
            iphone_exif: params.dsRemintV83.iphoneExif,
            metadata_mode: params.dsRemintV83.metadataMode
          }
        : undefined,
      ds_remint_v8_8: params.dsRemintV88
        ? {
            engine_mode: params.dsRemintV88.engineMode,
            wash_model: params.dsRemintV88.washModel,
            strength: params.dsRemintV88.strength,
            iphone_exif: params.dsRemintV88.iphoneExif,
            metadata_mode: params.dsRemintV88.metadataMode
          }
        : undefined,
      output_name_style: params.outputNameStyle,
      output_name_custom: params.outputNameCustom
    }
  });

  if (error) await throwSupabaseFunctionError(error);
  return data as DeepCleanJob;
}

export async function uploadDeepCleanInput(job: DeepCleanJob, file: File): Promise<void> {
  if (!supabase) {
    throw new Error("Supabase is not configured for Remarkee Max jobs.");
  }
  if (!job.inputPath || !job.uploadToken) {
    throw new Error("Remarkee Max job is missing signed upload details.");
  }

  const { error } = await supabase.storage
    .from("deepclean-inputs")
    .uploadToSignedUrl(job.inputPath, job.uploadToken, file, {
      contentType: file.type || "application/octet-stream"
    });

  if (error) await throwSupabaseFunctionError(error);
}

export async function dispatchDeepCleanJob(jobId: string): Promise<void> {
  if (!supabase) {
    throw new Error("Supabase is not configured for Remarkee Max jobs.");
  }

  const { error } = await supabase.functions.invoke("dispatch-deepclean-job", {
    body: { job_id: jobId }
  });

  if (error) throw error;
}

export async function getDeepCleanJob(jobId: string): Promise<DeepCleanJob> {
  if (!supabase) {
    throw new Error("Supabase is not configured for Remarkee Max jobs.");
  }

  const { data, error } = await supabase.functions.invoke("get-deepclean-job", {
    body: { job_id: jobId }
  });

  if (error) await throwSupabaseFunctionError(error);
  return data as DeepCleanJob;
}

export async function cancelDeepCleanJob(jobId: string): Promise<void> {
  if (!supabase) {
    throw new Error("Supabase is not configured for Remarkee Max jobs.");
  }

  const { error } = await supabase.functions.invoke("cancel-deepclean-job", {
    body: { job_id: jobId }
  });

  if (error) await throwSupabaseFunctionError(error);
}
