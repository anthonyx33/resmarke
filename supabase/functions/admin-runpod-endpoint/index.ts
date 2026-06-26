import { corsHeaders, jsonResponse } from "../_shared/cors.ts";
import { userFromRequest } from "../_shared/supabase.ts";

type RunpodEndpoint = {
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

type AdminBody = {
  action?: "status" | "update";
  preset?: "sleep" | "warm-window" | "keep-warm" | "manual";
  idleTimeout?: number;
  workersMin?: number;
  workersMax?: number;
};

Deno.serve(async (request) => {
  if (request.method === "OPTIONS") return new Response("ok", { headers: corsHeaders });
  if (request.method !== "POST") return jsonResponse({ error: "Method not allowed" }, 405);

  try {
    const { user } = await userFromRequest(request);
    assertAdmin(user.email ?? "");

    const body = (await request.json().catch(() => ({}))) as AdminBody;
    const action = body.action ?? "status";
    const current = await getRunpodEndpoint();

    if (action === "status") {
      return jsonResponse({ endpoint: current });
    }

    const next = nextEndpointConfig(current, body);
    const endpoint = await saveRunpodEndpoint(next);
    return jsonResponse({ endpoint });
  } catch (error) {
    return jsonResponse(
      { error: error instanceof Error ? error.message : "Could not manage RunPod endpoint." },
      error instanceof AdminError ? error.status : 500
    );
  }
});

function assertAdmin(email: string) {
  const admins = (Deno.env.get("ADMIN_EMAILS") ?? "")
    .split(",")
    .map((item) => item.trim().toLowerCase())
    .filter(Boolean);

  if (!admins.length) {
    throw new AdminError("ADMIN_EMAILS is not configured.", 403);
  }
  if (!admins.includes(email.toLowerCase())) {
    throw new AdminError("Not authorized for admin controls.", 403);
  }
}

function nextEndpointConfig(current: RunpodEndpoint, body: AdminBody): RunpodEndpoint {
  const preset = body.preset ?? "manual";
  const idleTimeout = clampInt(body.idleTimeout ?? current.idleTimeout, 5, 3600);
  const workersMin = clampInt(body.workersMin ?? current.workersMin, 0, 1);
  const workersMax = clampInt(body.workersMax ?? current.workersMax, 1, 3);

  if (preset === "sleep") {
    return { ...current, workersMin: 0, workersMax: 1, idleTimeout: 5 };
  }
  if (preset === "warm-window") {
    return { ...current, workersMin: 0, workersMax: 1, idleTimeout: clampInt(idleTimeout, 60, 900) };
  }
  if (preset === "keep-warm") {
    return { ...current, workersMin: 1, workersMax: 1, idleTimeout: clampInt(idleTimeout, 60, 900) };
  }

  return {
    ...current,
    workersMin,
    workersMax: Math.max(workersMax, workersMin || 1),
    idleTimeout
  };
}

async function getRunpodEndpoint(): Promise<RunpodEndpoint> {
  const endpointId = Deno.env.get("RUNPOD_ENDPOINT_ID");
  if (!endpointId) throw new Error("RUNPOD_ENDPOINT_ID is not configured.");

  const data = await runpodGraphql<{
    myself: { endpoints: RunpodEndpoint[] };
  }>(`
    query {
      myself {
        endpoints {
          id
          name
          gpuIds
          idleTimeout
          scalerType
          scalerValue
          templateId
          workersMax
          workersMin
        }
      }
    }
  `);

  const endpoint = data.myself.endpoints.find((item) => item.id === endpointId);
  if (!endpoint) throw new Error("Configured RunPod endpoint was not found.");
  return endpoint;
}

async function saveRunpodEndpoint(endpoint: RunpodEndpoint): Promise<RunpodEndpoint> {
  const scalerType = endpoint.scalerType ? `scalerType: ${gqlString(endpoint.scalerType)},` : "";
  const scalerValue =
    typeof endpoint.scalerValue === "number" ? `scalerValue: ${endpoint.scalerValue},` : "";

  const data = await runpodGraphql<{
    saveEndpoint: RunpodEndpoint;
  }>(`
    mutation {
      saveEndpoint(input: {
        id: ${gqlString(endpoint.id)},
        gpuIds: ${gqlString(endpoint.gpuIds)},
        name: ${gqlString(endpoint.name)},
        templateId: ${gqlString(endpoint.templateId)},
        workersMin: ${endpoint.workersMin},
        workersMax: ${endpoint.workersMax},
        idleTimeout: ${endpoint.idleTimeout},
        ${scalerType}
        ${scalerValue}
      }) {
        id
        name
        gpuIds
        idleTimeout
        scalerType
        scalerValue
        templateId
        workersMax
        workersMin
      }
    }
  `);

  return data.saveEndpoint;
}

async function runpodGraphql<T>(query: string): Promise<T> {
  const apiKey = Deno.env.get("RUNPOD_API_KEY");
  if (!apiKey) throw new Error("RUNPOD_API_KEY is not configured.");

  const response = await fetch("https://api.runpod.io/graphql", {
    method: "POST",
    headers: {
      "authorization": `Bearer ${apiKey}`,
      "content-type": "application/json"
    },
    body: JSON.stringify({ query })
  });

  const payload = await response.json().catch(() => ({}));
  if (!response.ok || payload.errors?.length) {
    const message = payload.errors?.[0]?.message ?? `RunPod GraphQL failed with ${response.status}`;
    throw new Error(message);
  }
  return payload.data as T;
}

function gqlString(value: string): string {
  return JSON.stringify(value);
}

function clampInt(value: number, min: number, max: number): number {
  if (!Number.isFinite(value)) return min;
  return Math.max(min, Math.min(max, Math.round(value)));
}

class AdminError extends Error {
  constructor(message: string, public status: number) {
    super(message);
  }
}
