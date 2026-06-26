import { supabase } from "./supabase";
import { throwSupabaseFunctionError } from "./supabaseFunctionError";

export type AdminRunpodEndpoint = {
  id: string;
  name: string;
  gpuIds: string;
  idleTimeout: number;
  scalerType?: string;
  scalerValue?: number;
  templateId: string;
  workersMax: number;
  workersMin: number;
};

export type AdminRunpodPreset = "sleep" | "warm-window" | "keep-warm" | "manual";

export async function getAdminRunpodEndpoint(): Promise<AdminRunpodEndpoint> {
  if (!supabase) throw new Error("Supabase is not configured.");

  const { data, error } = await supabase.functions.invoke("admin-runpod-endpoint", {
    body: { action: "status" }
  });

  if (error) await throwSupabaseFunctionError(error);
  return data.endpoint as AdminRunpodEndpoint;
}

export async function updateAdminRunpodEndpoint(params: {
  preset: AdminRunpodPreset;
  idleTimeout?: number;
  workersMin?: number;
  workersMax?: number;
}): Promise<AdminRunpodEndpoint> {
  if (!supabase) throw new Error("Supabase is not configured.");

  const { data, error } = await supabase.functions.invoke("admin-runpod-endpoint", {
    body: {
      action: "update",
      ...params
    }
  });

  if (error) await throwSupabaseFunctionError(error);
  return data.endpoint as AdminRunpodEndpoint;
}
