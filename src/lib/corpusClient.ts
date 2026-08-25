import * as tus from "tus-js-client";
import { sha256Hex } from "./hash";
import type { SettingsCodeInput } from "./settingsCode";
import { supabase } from "./supabase";
import { throwSupabaseFunctionError } from "./supabaseFunctionError";

export type CorpusImage = {
  id: string;
  sha256: string;
  file_name: string;
  byte_size: number;
  content_type: "image/jpeg" | "image/png" | "image/webp";
  width: number;
  height: number;
  created_at: string;
  archived_at: string | null;
  signed_url: string | null;
  run_count: number;
};

export type CorpusSet = {
  id: string;
  name: string;
  version: number;
  manifest_sha256: string | null;
  locked_at: string | null;
  archived_at: string | null;
  created_at: string;
};

export type CorpusSetMember = {
  corpus_set_id: string;
  corpus_image_id: string;
  position: number;
};

export type CorpusExperiment = {
  id: string;
  corpus_set_id: string;
  engine_release: string;
  detector_vendor: string;
  detector_mode: "sdxl" | "flux_schnell" | "real";
  detector_model: string | null;
  detector_version: string | null;
  config_set: string[] | Record<string, unknown>;
  notes: string | null;
  archived_at: string | null;
  created_at: string;
};

export type CorpusGrade = {
  grade_id: string;
  image_sha256: string;
  vendor: string;
  mode: string;
  ai_probability: number;
  deepfake_probability: number;
  verdict: "CLEAR" | "NEAR" | "BORDER" | "FAIL";
  top_source: string | null;
  sources: Record<string, number>;
  raw?: Record<string, unknown>;
  mock: boolean;
  swap_index?: number;
  retention_index?: number;
};

export type CorpusRun = {
  id: string;
  intent_id?: string;
  experiment_id: string;
  corpus_image_id: string;
  config_label: "A" | "1A" | "2B" | "3C" | "CUSTOM";
  config_key: string;
  requested_settings_code: string;
  requested_settings_canonical?: Record<string, unknown>;
  requested_settings_sha256?: string;
  executed_settings_snapshot?: Record<string, unknown>;
  executed_settings_sha256?: string | null;
  worker_report_snapshot?: Record<string, unknown>;
  worker_report_sha256?: string | null;
  worker_job_id?: string | null;
  actual_engine_version?: string;
  runtime_ms: number | null;
  output_sha256?: string;
  output_copy_status: "PENDING" | "COPIED" | "FAILED";
  grade_status: "PENDING" | "COMPLETE" | "ERROR";
  og_grade: CorpusGrade | null;
  remint_grade: CorpusGrade | null;
  delta: number | null;
  swap_index: number | null;
  retention_index: number | null;
  qa_flag: boolean;
  output_url?: string | null;
  created_at: string;
};

export type CorpusLeaderboardRow = {
  corpus_run_id: string;
  experiment_id: string;
  corpus_image_id: string;
  file_name: string;
  corpus_set_id: string;
  engine_release: string;
  detector_vendor: string;
  detector_mode: string;
  detector_model: string | null;
  detector_version: string | null;
  config_label: string;
  config_key: string;
  requested_settings_code: string;
  grade_status: CorpusRun["grade_status"];
  qa_flag: boolean;
  mock: boolean;
  og_ai: number | null;
  remint_ai: number | null;
  delta: number | null;
  swap_index: number | null;
  retention_index: number | null;
  og_top_source: string | null;
  remint_top_source: string | null;
  og_verdict: string | null;
  remint_verdict: string | null;
  runtime_ms: number | null;
  created_at: string;
};

export type CorpusSnapshot = {
  is_admin: true;
  user_id: string;
  images: CorpusImage[];
  sets: CorpusSet[];
  members: CorpusSetMember[];
  experiments: CorpusExperiment[];
  runs: CorpusRun[];
  leaderboard: CorpusLeaderboardRow[];
  engine_releases: string[];
  caps: {
    max_images: number;
    max_outputs_per_image: number;
    storage_byte_limit: number | null;
    used_bytes: number;
    download_ttl_seconds: number;
  };
  stats: {
    total_runs: number;
    pending_runs: number;
  };
};

type UploadResult = { corpus_image: CorpusImage; stored?: boolean; duplicate?: boolean };

export async function fetchCorpusSnapshot(): Promise<CorpusSnapshot> {
  return invoke<CorpusSnapshot>("corpus-list", {});
}

export async function readCorpusHistory(input: {
  corpusImageId?: string;
  experimentId?: string;
}): Promise<{ images: CorpusImage[]; runs: CorpusRun[]; signed_url_ttl_seconds: number }> {
  return invoke("corpus-read", {
    corpus_image_id: input.corpusImageId,
    experiment_id: input.experimentId,
  });
}

export async function uploadCorpusFile(
  file: File,
  onProgress?: (progress: number) => void,
): Promise<UploadResult> {
  const sha256 = await sha256Hex(await file.arrayBuffer());
  if (file.size <= 6 * 1024 * 1024) {
    const imageBase64 = await fileToBase64(file);
    onProgress?.(0.5);
    const result = await invoke<UploadResult>("corpus-upload", {
      image_b64: imageBase64,
      file_name: file.name,
    });
    onProgress?.(1);
    return result;
  }

  const presign = await invoke<{
    duplicate: boolean;
    corpus_image?: CorpusImage;
    bucket?: string;
    storage_path?: string;
    upload_token?: string;
    resumable_endpoint?: string;
    chunk_size?: number;
  }>("corpus-upload-presign", {
    file_name: file.name,
    file_size: file.size,
    content_type: file.type,
    sha256,
  });
  if (presign.duplicate && presign.corpus_image) {
    onProgress?.(1);
    return { corpus_image: presign.corpus_image, stored: false, duplicate: true };
  }
  if (!presign.bucket || !presign.storage_path || !presign.upload_token || !presign.resumable_endpoint) {
    throw new Error("Corpus upload presign returned an invalid response.");
  }
  await resumableUpload(file, presign as Required<typeof presign>, onProgress);
  return invoke<UploadResult>("corpus-upload-confirm", {
    storage_path: presign.storage_path,
    claimed_sha256: sha256,
    claimed_file_name: file.name,
  });
}

export async function createCorpusSet(name: string, version: number): Promise<CorpusSet> {
  const result = await manage<{ corpus_set: CorpusSet }>({ action: "create_set", name, version });
  return result.corpus_set;
}

export async function addCorpusSetMember(setId: string, imageId: string, position: number) {
  return manage({ action: "add_member", corpus_set_id: setId, corpus_image_id: imageId, position });
}

export async function removeCorpusSetMember(setId: string, imageId: string) {
  return manage({ action: "remove_member", corpus_set_id: setId, corpus_image_id: imageId });
}

export async function lockCorpusSet(setId: string) {
  return manage<{ corpus_set: CorpusSet & { member_count: number } }>({ action: "lock_set", corpus_set_id: setId });
}

export async function createCorpusExperiment(input: {
  corpusSetId: string;
  engineRelease: string;
  detectorVendor: string;
  detectorMode: CorpusExperiment["detector_mode"];
  detectorModel?: string;
  detectorVersion?: string;
  configSet: string[];
  notes?: string;
}): Promise<CorpusExperiment> {
  const result = await manage<{ experiment: CorpusExperiment }>({
    action: "create_experiment",
    corpus_set_id: input.corpusSetId,
    engine_release: input.engineRelease,
    detector_vendor: input.detectorVendor,
    detector_mode: input.detectorMode,
    detector_model: input.detectorModel,
    detector_version: input.detectorVersion,
    config_set: input.configSet,
    notes: input.notes,
  });
  return result.experiment;
}

export async function archiveCorpusEntity(entity: "image" | "set" | "experiment", id: string) {
  return manage({ action: "archive", entity, id });
}

export async function createCorpusRunIntent(input: {
  corpusImageId: string;
  experimentId: string;
  configLabel: "A" | "1A" | "2B" | "3C" | "CUSTOM";
  requestedSettingsCode: string;
  requestedSettingsCanonical: SettingsCodeInput;
}): Promise<string> {
  const result = await invoke<{ intent_id: string }>("corpus-run-intent", {
    corpus_image_id: input.corpusImageId,
    experiment_id: input.experimentId,
    config_label: input.configLabel,
    requested_settings_code: input.requestedSettingsCode,
    requested_settings_canonical: input.requestedSettingsCanonical,
  });
  return result.intent_id;
}

export async function registerCorpusRun(intentId: string, workerJobId: string) {
  return invoke<{
    corpus_run_id: string;
    grade_status: CorpusRun["grade_status"];
    output_copy_status: CorpusRun["output_copy_status"];
    duplicate: boolean;
  }>("corpus-register-run", { intent_id: intentId, worker_job_id: workerJobId });
}

export async function reconcileCorpusGrades(input: { experimentId?: string; runIds?: string[] }) {
  return invoke<{ completed: number; still_pending: number }>("corpus-reconcile-grades", {
    experiment_id: input.experimentId,
    run_ids: input.runIds,
  });
}

export function exportCorpusJsonl(runs: CorpusRun[]): string {
  return runs.map((run) => JSON.stringify(run)).join("\n") + (runs.length ? "\n" : "");
}

export function compactCorpusReport(runs: CorpusRun[]): string {
  const header = "| OG | OG AI% | top source | remint AI% | remint top | delta | verdict |";
  const divider = "|---|---:|---|---:|---|---:|---|";
  const lines = runs.filter((run) => run.og_grade && run.remint_grade).map((run) =>
    `| ${run.corpus_image_id} | ${percent(run.og_grade!.ai_probability)} | ${run.og_grade!.top_source ?? "—"} | ${percent(run.remint_grade!.ai_probability)} | ${run.remint_grade!.top_source ?? "—"} | ${signedPercent(run.delta ?? 0)} | ${run.remint_grade!.verdict} |`
  );
  return [header, divider, ...lines].join("\n");
}

async function manage<T = Record<string, unknown>>(body: Record<string, unknown>): Promise<T> {
  return invoke<T>("corpus-manage", body);
}

async function invoke<T>(name: string, body: Record<string, unknown>): Promise<T> {
  if (!supabase) throw new Error("Supabase is not configured for the corpus system.");
  const { data, error } = await supabase.functions.invoke(name, { body });
  if (error) await throwSupabaseFunctionError(error);
  return data as T;
}

async function resumableUpload(
  file: File,
  presign: {
    bucket: string;
    storage_path: string;
    upload_token: string;
    resumable_endpoint: string;
    chunk_size: number;
  },
  onProgress?: (progress: number) => void,
): Promise<void> {
  await new Promise<void>((resolve, reject) => {
    const upload = new tus.Upload(file, {
      endpoint: presign.resumable_endpoint,
      retryDelays: [0, 3_000, 5_000, 10_000, 20_000],
      headers: { "x-signature": presign.upload_token },
      uploadDataDuringCreation: true,
      removeFingerprintOnSuccess: true,
      chunkSize: presign.chunk_size,
      metadata: {
        bucketName: presign.bucket,
        objectName: presign.storage_path,
        contentType: file.type,
        cacheControl: "31536000",
      },
      onProgress: (uploaded, total) => onProgress?.(total ? uploaded / total : 0),
      onError: reject,
      onSuccess: () => {
        onProgress?.(1);
        resolve();
      },
    });
    void upload.findPreviousUploads().then((previous) => {
      if (previous.length) upload.resumeFromPreviousUpload(previous[0]);
      upload.start();
    }).catch(reject);
  });
}

function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(new Error(`Could not read ${file.name}.`));
    reader.onload = () => typeof reader.result === "string"
      ? resolve(reader.result)
      : reject(new Error(`Could not encode ${file.name}.`));
    reader.readAsDataURL(file);
  });
}

function percent(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

function signedPercent(value: number): string {
  const formatted = (value * 100).toFixed(1);
  return `${value >= 0 ? "+" : ""}${formatted}%`;
}
