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
    | "max-cx-remint-v2";
  outputMode: DeepCleanOutputMode;
  microTextureJitter?: boolean;
  expertRefinement?: ExpertRefinementSettings;
  cxRemint?: CxRemintOptions;
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
            device: params.cxRemint.device
          }
        : undefined
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
