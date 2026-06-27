import { supabase } from "./supabase";
import { throwSupabaseFunctionError } from "./supabaseFunctionError";

export type DeepCleanProfile = "standard" | "strong" | "max";
export type DeepCleanOutputMode = "stripped" | "sealed" | "sealed-stamped";

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
  profile: DeepCleanProfile;
  outputMode: DeepCleanOutputMode;
  microTextureJitter?: boolean;
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
      micro_texture_jitter: Boolean(params.microTextureJitter)
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
