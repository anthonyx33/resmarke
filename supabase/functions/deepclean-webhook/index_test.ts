import { handleDeepcleanWebhook } from "./index.ts";

type Outcome = "applied" | "duplicate" | "conflict" | "not_found";

function assert(condition: unknown, message: string): asserts condition {
  if (!condition) throw new Error(message);
}

function request(body: Record<string, unknown>): Request {
  return new Request("https://example.invalid/deepclean-webhook", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
}

function dependencies(outcome: Outcome, calls: Record<string, unknown>[]) {
  return {
    expectedSecret: () => "expected-secret",
    finalize: async (body: Record<string, unknown>) => {
      calls.push(body);
      if (outcome === "conflict") {
        return {
          outcome,
          conflict: true,
          existing_status: "failed" as const,
          attempted_status: "completed" as const,
        };
      }
      return { outcome, duplicate: outcome === "duplicate" };
    },
  };
}

Deno.test("signature validation precedes the terminal RPC", async () => {
  const calls: Record<string, unknown>[] = [];
  const response = await handleDeepcleanWebhook(request({
    job_id: "00000000-0000-4000-8000-000000000001",
    status: "completed",
    signature: "wrong-secret",
  }), dependencies("applied", calls));

  assert(response.status === 401, `expected 401, got ${response.status}`);
  assert(calls.length === 0, "unauthenticated callback reached the terminal RPC");
});

Deno.test("applied and duplicate outcomes are factual HTTP 200 responses", async () => {
  for (const outcome of ["applied", "duplicate"] as const) {
    const calls: Record<string, unknown>[] = [];
    const response = await handleDeepcleanWebhook(request({
      job_id: "00000000-0000-4000-8000-000000000001",
      status: "completed",
      output_sha256: "abc",
      report: { public: true },
      signature: "expected-secret",
    }), dependencies(outcome, calls));
    const payload = await response.json();

    assert(response.status === 200, `${outcome}: expected 200, got ${response.status}`);
    assert(payload.ok === true, `${outcome}: response was not ok`);
    assert(payload.duplicate === (outcome === "duplicate"), `${outcome}: duplicate flag drifted`);
    assert(calls.length === 1, `${outcome}: expected exactly one RPC call`);
  }
});

Deno.test("conflicting terminal callback returns 409 without a second implementation", async () => {
  const calls: Record<string, unknown>[] = [];
  const response = await handleDeepcleanWebhook(request({
    job_id: "00000000-0000-4000-8000-000000000001",
    status: "completed",
    signature: "expected-secret",
  }), dependencies("conflict", calls));
  const payload = await response.json();

  assert(response.status === 409, `expected 409, got ${response.status}`);
  assert(payload.ok === false && payload.conflict === true, "conflict response was not factual");
  assert(payload.existing_status === "failed", "existing status missing");
  assert(payload.attempted_status === "completed", "attempted status missing");
  assert(calls.length === 1, "conflict did not use exactly one RPC call");
});

Deno.test("not-found and invalid terminal status are rejected", async () => {
  const missingCalls: Record<string, unknown>[] = [];
  const missing = await handleDeepcleanWebhook(request({
    job_id: "00000000-0000-4000-8000-000000000001",
    status: "failed",
    signature: "expected-secret",
  }), dependencies("not_found", missingCalls));
  assert(missing.status === 404, `expected 404, got ${missing.status}`);

  const invalidCalls: Record<string, unknown>[] = [];
  const invalid = await handleDeepcleanWebhook(request({
    job_id: "00000000-0000-4000-8000-000000000001",
    status: "processing",
    signature: "expected-secret",
  }), dependencies("applied", invalidCalls));
  assert(invalid.status === 400, `expected 400, got ${invalid.status}`);
  assert(invalidCalls.length === 0, "invalid terminal status reached the RPC");
});
