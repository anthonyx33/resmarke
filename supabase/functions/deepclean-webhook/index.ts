import { corsHeaders, jsonResponse } from "../_shared/cors.ts";
import { adminClient } from "../_shared/supabase.ts";

type WebhookBody = {
  job_id: string;
  status: "completed" | "failed";
  output_sha256?: string;
  input_sha256?: string;
  engine_version?: string;
  runtime_ms?: number;
  gpu_type?: string;
  failure_reason?: string;
  report: Record<string, unknown>;
};

type TerminalRpcResult = {
  outcome: "applied" | "duplicate" | "conflict" | "not_found";
  duplicate?: boolean;
  conflict?: boolean;
  terminal_status?: "completed" | "failed";
  existing_status?: "completed" | "failed";
  attempted_status?: "completed" | "failed";
  conflict_kind?: "status" | "payload";
};

type WebhookDependencies = {
  expectedSecret: () => string | undefined;
  finalize: (body: WebhookBody) => Promise<TerminalRpcResult>;
};

const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const SHA256_PATTERN = /^[0-9a-f]{64}$/;
const MAX_FAILURE_REASON_LENGTH = 2000;
const POSTGRES_INTEGER_MAX = 2_147_483_647;

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function optionalString(
  body: Record<string, unknown>,
  key: "engine_version" | "gpu_type",
): { value?: string; error?: string } {
  const value = body[key];
  if (value === undefined) return {};
  if (typeof value !== "string") return { error: `${key} must be a string.` };
  return { value };
}

function validateTerminalBody(
  raw: unknown,
): { body?: WebhookBody; error?: string } {
  if (!isRecord(raw)) return { error: "Webhook body must be a JSON object." };

  const jobId = raw.job_id;
  if (typeof jobId !== "string" || !UUID_PATTERN.test(jobId)) {
    return { error: "job_id must be a UUID." };
  }
  if (raw.status !== "completed" && raw.status !== "failed") {
    return { error: "Invalid terminal status." };
  }

  const runtimeMs = raw.runtime_ms;
  if (
    runtimeMs !== undefined &&
    (typeof runtimeMs !== "number" || !Number.isFinite(runtimeMs) ||
      !Number.isInteger(runtimeMs) || runtimeMs < 0 ||
      runtimeMs > POSTGRES_INTEGER_MAX)
  ) {
    return { error: "runtime_ms must be a nonnegative PostgreSQL integer." };
  }

  const engineVersion = optionalString(raw, "engine_version");
  if (engineVersion.error) return { error: engineVersion.error };
  const gpuType = optionalString(raw, "gpu_type");
  if (gpuType.error) return { error: gpuType.error };

  const report = raw.report === undefined ? {} : raw.report;
  if (!isRecord(report)) return { error: "report must be a JSON object." };

  const common = {
    job_id: jobId,
    status: raw.status,
    engine_version: engineVersion.value,
    runtime_ms: runtimeMs as number | undefined,
    gpu_type: gpuType.value,
    report,
  };

  if (raw.status === "completed") {
    if (
      typeof raw.output_sha256 !== "string" ||
      !SHA256_PATTERN.test(raw.output_sha256)
    ) {
      return { error: "completed output_sha256 must be lowercase 64-hex." };
    }
    if (
      typeof raw.input_sha256 !== "string" ||
      !SHA256_PATTERN.test(raw.input_sha256)
    ) {
      return { error: "completed input_sha256 must be lowercase 64-hex." };
    }
    return {
      body: {
        ...common,
        status: "completed",
        output_sha256: raw.output_sha256,
        input_sha256: raw.input_sha256,
      },
    };
  }

  if (typeof raw.failure_reason !== "string") {
    return { error: "failed failure_reason must be a nonempty string." };
  }
  const failureReason = raw.failure_reason.trim();
  if (
    failureReason.length === 0 ||
    failureReason.length > MAX_FAILURE_REASON_LENGTH
  ) {
    return {
      error:
        `failed failure_reason must contain 1-${MAX_FAILURE_REASON_LENGTH} characters.`,
    };
  }
  return {
    body: {
      ...common,
      status: "failed",
      failure_reason: failureReason,
    },
  };
}

const productionDependencies: WebhookDependencies = {
  expectedSecret: () => Deno.env.get("DEEPCLEAN_WEBHOOK_SECRET"),
  finalize: async (body) => {
    const { data, error } = await adminClient().rpc(
      "finalize_deepclean_job_terminal",
      {
        p_job_id: body.job_id,
        p_terminal_status: body.status,
        p_output_sha256: body.output_sha256 ?? null,
        p_input_sha256: body.input_sha256 ?? null,
        p_engine_version: body.engine_version ?? null,
        p_runtime_ms: body.runtime_ms ?? null,
        p_gpu_type: body.gpu_type ?? null,
        p_failure_reason: body.failure_reason ?? null,
        p_report: body.report ?? {},
      },
    );
    if (error) throw error;
    return data as TerminalRpcResult;
  },
};

export async function handleDeepcleanWebhook(
  request: Request,
  dependencies: WebhookDependencies = productionDependencies,
): Promise<Response> {
  if (request.method === "OPTIONS") {
    return new Response("ok", { headers: corsHeaders });
  }
  if (request.method !== "POST") {
    return jsonResponse({ error: "Method not allowed" }, 405);
  }

  let rawBody: unknown;
  try {
    rawBody = await request.json();
  } catch {
    return jsonResponse({ error: "Malformed JSON body." }, 400);
  }

  const expectedSecret = dependencies.expectedSecret();
  const suppliedSignature = isRecord(rawBody) ? rawBody.signature : undefined;
  if (!expectedSecret || suppliedSignature !== expectedSecret) {
    return jsonResponse({ error: "Invalid webhook signature." }, 401);
  }

  const validated = validateTerminalBody(rawBody);
  if (!validated.body) {
    return jsonResponse(
      { error: validated.error ?? "Invalid webhook body." },
      400,
    );
  }

  try {
    const body = validated.body;
    const result = await dependencies.finalize(body);
    if (result.outcome === "not_found") {
      return jsonResponse({ error: "Job not found." }, 404);
    }
    if (result.outcome === "conflict") {
      return jsonResponse({
        ok: false,
        conflict: true,
        conflict_kind: result.conflict_kind,
        existing_status: result.existing_status,
        attempted_status: result.attempted_status,
      }, 409);
    }
    if (result.outcome === "duplicate") {
      return jsonResponse({ ok: true, duplicate: true });
    }
    return jsonResponse({ ok: true, duplicate: false });
  } catch (error) {
    return jsonResponse(
      { error: error instanceof Error ? error.message : "Webhook failed." },
      500,
    );
  }
}

if (import.meta.main) Deno.serve((request) => handleDeepcleanWebhook(request));
