import { handleDeepcleanWebhook } from "./index.ts";

type Outcome = "applied" | "duplicate" | "conflict" | "not_found";

const JOB_ID = "00000000-0000-4000-8000-000000000001";
const OUTPUT_SHA = "a".repeat(64);
const INPUT_SHA = "b".repeat(64);

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

function completedBody(
  overrides: Record<string, unknown> = {},
): Record<string, unknown> {
  return {
    job_id: JOB_ID,
    status: "completed",
    output_sha256: OUTPUT_SHA,
    input_sha256: INPUT_SHA,
    engine_version: "engine-v1",
    runtime_ms: 12,
    gpu_type: "test-gpu",
    report: { public: true },
    signature: "expected-secret",
    ...overrides,
  };
}

function failedBody(
  overrides: Record<string, unknown> = {},
): Record<string, unknown> {
  return {
    job_id: JOB_ID,
    status: "failed",
    engine_version: "engine-v1",
    runtime_ms: 7,
    gpu_type: "test-gpu",
    failure_reason: "processing failed",
    report: { public: true },
    signature: "expected-secret",
    ...overrides,
  };
}

function dependencies(
  result: {
    outcome: Outcome;
    duplicate?: boolean;
    conflict?: boolean;
    conflict_kind?: "status" | "payload";
    existing_status?: "completed" | "failed";
    attempted_status?: "completed" | "failed";
  },
  calls: Record<string, unknown>[],
) {
  return {
    expectedSecret: () => "expected-secret",
    finalize: async (body: Record<string, unknown>) => {
      calls.push(body);
      return result;
    },
  };
}

Deno.test("signature validation precedes body validation and the terminal RPC", async () => {
  const calls: Record<string, unknown>[] = [];
  const response = await handleDeepcleanWebhook(
    request({
      job_id: "not-a-uuid",
      status: "completed",
      signature: "wrong-secret",
    }),
    dependencies({ outcome: "applied" }, calls),
  );

  assert(response.status === 401, `expected 401, got ${response.status}`);
  assert(calls.length === 0, "unauthenticated callback reached validation/RPC");
});

Deno.test("applied and exact-duplicate outcomes are factual HTTP 200 responses", async () => {
  for (const outcome of ["applied", "duplicate"] as const) {
    const calls: Record<string, unknown>[] = [];
    const response = await handleDeepcleanWebhook(
      request(completedBody()),
      dependencies({ outcome, duplicate: outcome === "duplicate" }, calls),
    );
    const payload = await response.json();

    assert(
      response.status === 200,
      `${outcome}: expected 200, got ${response.status}`,
    );
    assert(payload.ok === true, `${outcome}: response was not ok`);
    assert(
      payload.duplicate === (outcome === "duplicate"),
      `${outcome}: duplicate flag drifted`,
    );
    assert(calls.length === 1, `${outcome}: expected exactly one RPC call`);
    assert(
      calls[0].output_sha256 === OUTPUT_SHA,
      `${outcome}: output identity drifted`,
    );
    assert(
      calls[0].input_sha256 === INPUT_SHA,
      `${outcome}: input identity drifted`,
    );
    assert(
      !("signature" in calls[0]),
      `${outcome}: signature was passed to the RPC dependency`,
    );
  }
});

Deno.test("same-status payload conflict returns factual HTTP 409", async () => {
  const calls: Record<string, unknown>[] = [];
  const response = await handleDeepcleanWebhook(
    request(completedBody()),
    dependencies({
      outcome: "conflict",
      conflict: true,
      conflict_kind: "payload",
      existing_status: "completed",
      attempted_status: "completed",
    }, calls),
  );
  const payload = await response.json();

  assert(response.status === 409, `expected 409, got ${response.status}`);
  assert(
    payload.ok === false && payload.conflict === true,
    "conflict response was not factual",
  );
  assert(payload.conflict_kind === "payload", "payload conflict kind missing");
  assert(payload.existing_status === "completed", "existing status missing");
  assert(payload.attempted_status === "completed", "attempted status missing");
  assert(calls.length === 1, "conflict did not use exactly one RPC call");
});

Deno.test("opposite-status conflict returns factual HTTP 409", async () => {
  const calls: Record<string, unknown>[] = [];
  const response = await handleDeepcleanWebhook(
    request(completedBody()),
    dependencies({
      outcome: "conflict",
      conflict: true,
      conflict_kind: "status",
      existing_status: "failed",
      attempted_status: "completed",
    }, calls),
  );
  const payload = await response.json();

  assert(response.status === 409, `expected 409, got ${response.status}`);
  assert(payload.conflict_kind === "status", "status conflict kind missing");
  assert(
    calls.length === 1,
    "status conflict did not use exactly one RPC call",
  );
});

Deno.test("completed and failed bodies are validated before the RPC", async () => {
  const invalidBodies = [
    completedBody({ job_id: "not-a-uuid" }),
    completedBody({ status: "processing" }),
    completedBody({ output_sha256: undefined }),
    completedBody({ output_sha256: "A".repeat(64) }),
    completedBody({ input_sha256: "short" }),
    completedBody({ runtime_ms: -1 }),
    completedBody({ runtime_ms: 1.5 }),
    completedBody({ runtime_ms: null }),
    completedBody({ report: [] }),
    completedBody({ engine_version: 9 }),
    failedBody({ failure_reason: undefined }),
    failedBody({ failure_reason: "   " }),
    failedBody({ failure_reason: "x".repeat(2001) }),
  ];

  for (const [index, body] of invalidBodies.entries()) {
    const calls: Record<string, unknown>[] = [];
    const response = await handleDeepcleanWebhook(
      request(body),
      dependencies({ outcome: "applied" }, calls),
    );
    assert(
      response.status === 400,
      `case ${index}: expected 400, got ${response.status}`,
    );
    assert(calls.length === 0, `case ${index}: malformed body reached the RPC`);
  }
});

Deno.test("failed reason is normalized and signature is excluded before RPC", async () => {
  const calls: Record<string, unknown>[] = [];
  const response = await handleDeepcleanWebhook(
    request(failedBody({ failure_reason: "  processing failed  " })),
    dependencies({ outcome: "applied" }, calls),
  );

  assert(response.status === 200, `expected 200, got ${response.status}`);
  assert(
    calls.length === 1,
    "valid failed body did not reach RPC exactly once",
  );
  assert(
    calls[0].failure_reason === "processing failed",
    "failure reason was not normalized",
  );
  assert(
    !("signature" in calls[0]),
    "signature was passed to the RPC dependency",
  );
});

Deno.test("not-found and malformed JSON are rejected", async () => {
  const missingCalls: Record<string, unknown>[] = [];
  const missing = await handleDeepcleanWebhook(
    request(failedBody()),
    dependencies({ outcome: "not_found" }, missingCalls),
  );
  assert(missing.status === 404, `expected 404, got ${missing.status}`);
  assert(missingCalls.length === 1, "valid missing job did not reach RPC once");

  const malformedCalls: Record<string, unknown>[] = [];
  const malformed = await handleDeepcleanWebhook(
    new Request(
      "https://example.invalid/deepclean-webhook",
      { method: "POST", body: "{" },
    ),
    dependencies({ outcome: "applied" }, malformedCalls),
  );
  assert(
    malformed.status === 400,
    `expected malformed JSON 400, got ${malformed.status}`,
  );
  assert(malformedCalls.length === 0, "malformed JSON reached the RPC");
});
