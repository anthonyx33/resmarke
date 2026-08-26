import { corsHeaders, jsonResponse } from "../_shared/cors.ts";
import {
  assertUuid,
  corpusBucket,
  corpusDownloadTtl,
  CorpusHttpError,
  errorResponse,
  requireCorpusAdmin,
} from "../_shared/corpus.ts";

const CONFIG_LABELS = ["A", "1A", "2B", "3C", "CUSTOM"];
const DEFAULT_LIMIT = 20;
const MAX_LIMIT = 100;
const MAX_OFFSET = 100_000;

// `raw` is the untouched vendor payload cached per grade. It is durable evidence
// in `grade_cache`/`corpus_runs` but is never needed by the visual browser, so
// it is stripped here to keep 20-row pages small.
const RUN_COLUMNS = [
  "id",
  "experiment_id",
  "corpus_image_id",
  "config_label",
  "config_key",
  "requested_settings_code",
  "requested_settings_canonical",
  "requested_settings_sha256",
  "executed_settings_sha256",
  "worker_report_sha256",
  "worker_job_id",
  "actual_engine_version",
  "runtime_ms",
  "output_sha256",
  "output_storage_path",
  "output_byte_size",
  "output_copy_status",
  "grade_status",
  "og_grade",
  "remint_grade",
  "delta",
  "swap_index",
  "retention_index",
  "qa_flag",
  "created_at",
].join(",");

Deno.serve(async (request) => {
  if (request.method === "OPTIONS") return new Response("ok", { headers: corsHeaders });
  if (request.method !== "POST") return jsonResponse({ error: "Method not allowed" }, 405);
  try {
    const { client } = await requireCorpusAdmin(request);
    const body = await request.json().catch(() => ({})) as Record<string, unknown>;
    const imageId = body.corpus_image_id ? assertUuid(body.corpus_image_id, "corpus_image_id") : null;
    const experimentId = body.experiment_id ? assertUuid(body.experiment_id, "experiment_id") : null;
    const configLabel = assertConfigLabel(body.config_label);
    const limit = boundedInteger(body.limit, "limit", DEFAULT_LIMIT, 1, MAX_LIMIT);
    const offset = boundedInteger(body.offset, "offset", 0, 0, MAX_OFFSET);

    let query = client.from("corpus_runs").select(RUN_COLUMNS, { count: "exact" })
      .order("created_at", { ascending: false })
      .order("id", { ascending: false })
      .range(offset, offset + limit - 1);
    if (imageId) query = query.eq("corpus_image_id", imageId);
    if (experimentId) query = query.eq("experiment_id", experimentId);
    if (configLabel) query = query.eq("config_label", configLabel);
    const { data: runs, error, count } = await query;
    if (error) throw error;
    const rows = (runs ?? []) as unknown as CorpusRunRow[];

    const imageIds = Array.from(new Set(rows.map((run) => run.corpus_image_id)));
    const experimentIds = Array.from(new Set(rows.map((run) => run.experiment_id)));
    const [imagesResult, experimentsResult] = await Promise.all([
      imageIds.length
        ? client.from("corpus_images").select("id,sha256,file_name,storage_path,width,height,byte_size").in("id", imageIds)
        : Promise.resolve({ data: [], error: null }),
      experimentIds.length
        ? client.from("corpus_experiments").select("id,engine_release,detector_vendor,detector_mode,detector_model,detector_version").in("id", experimentIds)
        : Promise.resolve({ data: [], error: null }),
    ]);
    if (imagesResult.error) throw imagesResult.error;
    if (experimentsResult.error) throw experimentsResult.error;
    const imagesById = new Map(
      ((imagesResult.data ?? []) as CorpusImageRow[]).map((image) => [image.id, image]),
    );
    const experimentsById = new Map(
      ((experimentsResult.data ?? []) as CorpusExperimentRow[]).map((experiment) => [experiment.id, experiment]),
    );

    const ttl = corpusDownloadTtl();
    const paths = Array.from(new Set([
      ...Array.from(imagesById.values()).map((image) => image.storage_path),
      ...rows.map((run) => run.output_storage_path),
    ].filter((path): path is string => Boolean(path))));
    const { data: signed, error: signedError } = paths.length
      ? await client.storage.from(corpusBucket()).createSignedUrls(paths, ttl)
      : { data: [], error: null };
    if (signedError) throw signedError;
    const signedByPath = new Map((signed ?? []).map((entry) => [entry.path, entry.signedUrl ?? null]));

    const history = rows.map((run) => {
      const image = imagesById.get(run.corpus_image_id) ?? null;
      const experiment = experimentsById.get(run.experiment_id) ?? null;
      const ogGrade = sanitizeGrade(run.og_grade);
      const remintGrade = sanitizeGrade(run.remint_grade);
      return {
        run_id: run.id,
        created_at: run.created_at,
        experiment_id: run.experiment_id,
        corpus_image_id: run.corpus_image_id,
        file_name: image?.file_name ?? null,
        config_label: run.config_label,
        config_key: run.config_key,
        settings_code: run.requested_settings_code,
        requested_settings_canonical: run.requested_settings_canonical,
        requested_settings_sha256: run.requested_settings_sha256,
        executed_settings_sha256: run.executed_settings_sha256,
        worker_report_sha256: run.worker_report_sha256,
        og_sha256: image?.sha256 ?? null,
        output_sha256: run.output_sha256,
        output_byte_size: run.output_byte_size,
        output_copy_status: run.output_copy_status,
        og_grade: ogGrade,
        remint_grade: remintGrade,
        delta: run.delta,
        swap_index: run.swap_index,
        retention_index: run.retention_index,
        grade_status: run.grade_status,
        verdict: typeof remintGrade?.verdict === "string" ? remintGrade.verdict : run.grade_status,
        qa_flag: run.qa_flag,
        mock: gradeMock(remintGrade) || gradeMock(ogGrade),
        engine_version: run.actual_engine_version,
        engine_release: experiment?.engine_release ?? null,
        detector_vendor: experiment?.detector_vendor ?? null,
        detector_mode: experiment?.detector_mode ?? null,
        detector_model: experiment?.detector_model ?? null,
        detector_version: experiment?.detector_version ?? null,
        runtime_ms: run.runtime_ms,
        job_id: run.worker_job_id,
        og_width: image?.width ?? null,
        og_height: image?.height ?? null,
        og_url: image ? signedByPath.get(image.storage_path) ?? null : null,
        output_url: signedByPath.get(run.output_storage_path) ?? null,
      };
    });

    const total = typeof count === "number" ? count : history.length;
    return jsonResponse({
      runs: history,
      total,
      limit,
      offset,
      has_more: offset + history.length < total,
      signed_url_ttl_seconds: ttl,
      signed_at: new Date().toISOString(),
    });
  } catch (error) {
    const response = errorResponse(error);
    return jsonResponse({ error: response.message }, response.status);
  }
});

type CorpusRunRow = {
  id: string;
  experiment_id: string;
  corpus_image_id: string;
  config_label: string;
  config_key: string;
  requested_settings_code: string;
  requested_settings_canonical: Record<string, unknown>;
  requested_settings_sha256: string;
  executed_settings_sha256: string | null;
  worker_report_sha256: string | null;
  worker_job_id: string | null;
  actual_engine_version: string;
  runtime_ms: number | null;
  output_sha256: string;
  output_storage_path: string;
  output_byte_size: number;
  output_copy_status: string;
  grade_status: string;
  og_grade: Record<string, unknown> | null;
  remint_grade: Record<string, unknown> | null;
  delta: number | null;
  swap_index: number | null;
  retention_index: number | null;
  qa_flag: boolean;
  created_at: string;
};

type CorpusImageRow = {
  id: string;
  sha256: string;
  file_name: string;
  storage_path: string;
  width: number;
  height: number;
  byte_size: number;
};

type CorpusExperimentRow = {
  id: string;
  engine_release: string;
  detector_vendor: string;
  detector_mode: string;
  detector_model: string | null;
  detector_version: string | null;
};

function assertConfigLabel(value: unknown): string | null {
  if (value === undefined || value === null || value === "") return null;
  if (typeof value !== "string" || !CONFIG_LABELS.includes(value)) {
    throw new CorpusHttpError(`config_label must be one of ${CONFIG_LABELS.join(", ")}.`, 400);
  }
  return value;
}

function boundedInteger(value: unknown, field: string, fallback: number, min: number, max: number): number {
  if (value === undefined || value === null || value === "") return fallback;
  const parsed = typeof value === "number" ? value : Number(value);
  if (!Number.isInteger(parsed) || parsed < min || parsed > max) {
    throw new CorpusHttpError(`${field} must be an integer between ${min} and ${max}.`, 400);
  }
  return parsed;
}

function sanitizeGrade(value: Record<string, unknown> | null): Record<string, unknown> | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) return null;
  const { raw: _raw, ...rest } = value;
  return rest;
}

function gradeMock(grade: Record<string, unknown> | null): boolean {
  return Boolean(grade && grade.mock === true);
}
