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
  report?: Record<string, unknown>;
  signature?: string;
};

type TerminalRpcResult = {
  outcome: "applied" | "duplicate" | "conflict" | "not_found";
  duplicate?: boolean;
  conflict?: boolean;
  terminal_status?: "completed" | "failed";
  existing_status?: "completed" | "failed";
  attempted_status?: "completed" | "failed";
};

type WebhookDependencies = {
  expectedSecret: () => string | undefined;
  finalize: (body: WebhookBody) => Promise<TerminalRpcResult>;
};

const productionDependencies: WebhookDependencies = {
  expectedSecret: () => Deno.env.get("DEEPCLEAN_WEBHOOK_SECRET"),
  finalize: async (body) => {
    const { data, error } = await adminClient().rpc("finalize_deepclean_job_terminal", {
      p_job_id: body.job_id,
      p_terminal_status: body.status,
      p_output_sha256: body.output_sha256 ?? null,
      p_input_sha256: body.input_sha256 ?? null,
      p_engine_version: body.engine_version ?? null,
      p_runtime_ms: body.runtime_ms ?? null,
      p_gpu_type: body.gpu_type ?? null,
      p_failure_reason: body.failure_reason ?? null,
      p_report: body.report ?? {},
    });
    if (error) throw error;
    return data as TerminalRpcResult;
  },
};

export async function handleDeepcleanWebhook(
  request: Request,
  dependencies: WebhookDependencies = productionDependencies,
): Promise<Response> {
  if (request.method === "OPTIONS") return new Response("ok", { headers: corsHeaders });
  if (request.method !== "POST") return jsonResponse({ error: "Method not allowed" }, 405);

  try {
    const body = (await request.json()) as WebhookBody;
    const expectedSecret = dependencies.expectedSecret();
    if (!expectedSecret || body.signature !== expectedSecret) {
      return jsonResponse({ error: "Invalid webhook signature." }, 401);
    }
    if (body.status !== "completed" && body.status !== "failed") {
      return jsonResponse({ error: "Invalid terminal status." }, 400);
    }

    const result = await dependencies.finalize(body);
    if (result.outcome === "not_found") {
      return jsonResponse({ error: "Job not found." }, 404);
    }
    if (result.outcome === "conflict") {
      return jsonResponse({
        ok: false,
        conflict: true,
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
      500
    );
  }
}

if (import.meta.main) Deno.serve((request) => handleDeepcleanWebhook(request));
