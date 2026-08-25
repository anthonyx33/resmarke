import { corsHeaders, jsonResponse } from "../_shared/cors.ts";
import { adminClient, userFromRequest } from "../_shared/supabase.ts";
import { parseHiveResponse } from "./hive.ts";

type GradeMode = "sdxl" | "flux_schnell" | "real";
type GradeRole = "og" | "remint";
type Verdict = "CLEAR" | "NEAR" | "BORDER" | "FAIL";

type GradeInput = {
  image_b64?: string;
  image_url?: string;
  role: GradeRole;
  mode?: GradeMode;
  settings_code?: string;
  og_grade?: { sources?: Record<string, number> };
  grade_session_id?: string;
};

type CachedGrade = {
  grade_id: string;
  image_sha256: string;
  vendor: string;
  mode: GradeMode;
  ai_probability: number;
  deepfake_probability: number;
  verdict: Verdict;
  top_source: string | null;
  sources: Record<string, number>;
  raw: Record<string, unknown>;
  mock: boolean;
};

type ProviderResult = {
  aiProbability: number;
  deepfakeProbability: number;
  sources: Record<string, number>;
  raw: Record<string, unknown>;
};

type SessionUsage = { vendor_calls: number; cap: number };
type ProviderExecution = {
  grade: CachedGrade;
  providerCalls: number;
  usage: SessionUsage;
  cacheHit: boolean;
  vendorError?: string;
  requestedMode: GradeMode;
};

const MODES = new Set<GradeMode>(["sdxl", "flux_schnell", "real"]);
const MAX_IMAGE_BYTES = 25 * 1024 * 1024;
const HIVE_MAX_IMAGE_BYTES = 20 * 1024 * 1024;
const DEFAULT_SESSION_CAP = 40;
const HIVE_API_MODE: GradeMode = "real";
const HIVE_ENDPOINT =
  "https://api.thehive.ai/api/v3/hive/ai-generated-and-deepfake-content-detection";

Deno.serve(async (request) => {
  if (request.method === "OPTIONS") {
    return new Response("ok", { headers: corsHeaders });
  }
  if (request.method !== "POST") {
    return jsonResponse({ error: "Method not allowed" }, 405);
  }

  try {
    const { user } = await userFromRequest(request);
    const input = (await request.json()) as GradeInput;
    const validated = validateInput(input);
    const provider = providerName();

    const bytes = await readImageBytes(validated);
    const imageSha256 = await sha256Hex(bytes);
    const sessionId = validated.grade_session_id ?? crypto.randomUUID();
    const cap = sessionCap();

    const execution = await gradeWithFallback({
      bytes,
      imageSha256,
      requestedMode: validated.mode,
      gradeMode: provider === "g1" ? HIVE_API_MODE : validated.mode,
      ownerDefaultMode: ownerDefaultMode(),
      provider,
      sessionId,
      userId: user.id,
      cap,
    });

    const paired = pairIndexes(
      execution.grade.sources,
      validated.role === "remint" ? validated.og_grade?.sources : undefined,
    );

    return jsonResponse({
      ...execution.grade,
      swap_index: paired.swapIndex,
      retention_index: paired.retentionIndex,
      cache_hit: execution.cacheHit,
      provider_calls: execution.providerCalls,
      requested_mode: execution.requestedMode,
      ...(execution.vendorError ? { vendor_error: execution.vendorError } : {}),
      session_usage: execution.usage,
    });
  } catch (error) {
    const apiError = toApiError(error);
    return jsonResponse({ error: apiError.message }, apiError.status);
  }
});

function validateInput(
  input: GradeInput,
): GradeInput & { role: GradeRole; mode: GradeMode } {
  if (!input || typeof input !== "object") {
    throw badRequest("A JSON request body is required.");
  }
  if (input.role !== "og" && input.role !== "remint") {
    throw badRequest('role must be "og" or "remint".');
  }
  if (Boolean(input.image_b64) === Boolean(input.image_url)) {
    throw badRequest("Supply exactly one of image_b64 or image_url.");
  }
  const mode = input.mode ?? ownerDefaultMode();
  if (!mode) {
    throw serviceUnavailable(
      "The owner has not configured GRADE_DEFAULT_MODE; pass an explicit mock mode or supply the owner decision.",
    );
  }
  if (!MODES.has(mode)) {
    throw badRequest("mode must be sdxl, flux_schnell, or real.");
  }
  if (
    input.settings_code !== undefined && typeof input.settings_code !== "string"
  ) {
    throw badRequest("settings_code must be a string.");
  }
  if (input.grade_session_id && !isUuid(input.grade_session_id)) {
    throw badRequest("grade_session_id must be a UUID.");
  }
  if (input.role === "remint" && input.og_grade?.sources) {
    validateSources(input.og_grade.sources);
  }
  return { ...input, role: input.role, mode };
}

async function gradeWithFallback(input: {
  bytes: Uint8Array;
  imageSha256: string;
  requestedMode: GradeMode;
  gradeMode: GradeMode;
  ownerDefaultMode: GradeMode | null;
  provider: "mock" | "g1";
  sessionId: string;
  userId: string;
  cap: number;
}): Promise<ProviderExecution> {
  const initial = await cachedGrade(
    input.imageSha256,
    input.provider,
    input.gradeMode,
  );
  if (initial) {
    return {
      grade: initial,
      providerCalls: 0,
      usage: await currentUsage(input.sessionId, input.userId, input.cap),
      cacheHit: true,
      requestedMode: input.requestedMode,
    };
  }

  try {
    const result = await callWithOneRetry(input, input.gradeMode);
    const grade = await normalizeAndCache(
      result.result,
      input.bytes,
      input.imageSha256,
      input.provider,
      input.gradeMode,
    );
    return {
      grade,
      providerCalls: result.calls,
      usage: result.usage,
      cacheHit: false,
      requestedMode: input.requestedMode,
    };
  } catch (error) {
    const defaultMode = input.ownerDefaultMode;
    if (!defaultMode || defaultMode === input.gradeMode) throw error;

    const message = safeError(error);
    const failedCalls = error instanceof VendorAttemptError ? error.calls : 0;
    const fallbackCached = await cachedGrade(
      input.imageSha256,
      input.provider,
      defaultMode,
    );
    if (fallbackCached) {
      return {
        grade: fallbackCached,
        providerCalls: failedCalls,
        usage: await currentUsage(input.sessionId, input.userId, input.cap),
        cacheHit: true,
        vendorError:
          `${input.gradeMode}: ${message}; used cached ${defaultMode}`,
        requestedMode: input.requestedMode,
      };
    }

    const fallback = await callWithOneRetry(input, defaultMode);
    const grade = await normalizeAndCache(
      fallback.result,
      input.bytes,
      input.imageSha256,
      input.provider,
      defaultMode,
    );
    return {
      grade,
      providerCalls: failedCalls + fallback.calls,
      usage: fallback.usage,
      cacheHit: false,
      vendorError: `${input.gradeMode}: ${message}; graded ${defaultMode}`,
      requestedMode: input.requestedMode,
    };
  }
}

async function callWithOneRetry(
  context: {
    bytes: Uint8Array;
    provider: "mock" | "g1";
    sessionId: string;
    userId: string;
    cap: number;
  },
  mode: GradeMode,
): Promise<{ result: ProviderResult; calls: number; usage: SessionUsage }> {
  if (context.provider === "mock") {
    return {
      result: mockProvider(context.bytes, mode),
      calls: 0,
      usage: await currentUsage(context.sessionId, context.userId, context.cap),
    };
  }
  if (context.bytes.length > HIVE_MAX_IMAGE_BYTES) {
    throw badRequest("Hive base64 uploads are limited to 20 MB.");
  }
  if (!Deno.env.get("HIVE_SECRET_KEY")?.trim()) {
    throw serviceUnavailable("Hive server credential is not configured.");
  }

  let lastError: unknown;
  let calls = 0;
  let usage = await currentUsage(
    context.sessionId,
    context.userId,
    context.cap,
  );
  for (let attempt = 0; attempt < 2; attempt += 1) {
    usage = await reserveVendorCall(
      context.sessionId,
      context.userId,
      context.cap,
    );
    calls += 1;
    try {
      const result = await callVerifiedG1(context.bytes);
      return { result, calls, usage };
    } catch (error) {
      lastError = error;
      if (!shouldRetryVendorError(error)) break;
    }
  }
  throw new VendorAttemptError(
    `G1 ${mode} failed after ${calls} attempt${calls === 1 ? "" : "s"}: ${
      safeError(lastError)
    }`,
    calls,
  );
}

async function callVerifiedG1(
  bytes: Uint8Array,
): Promise<ProviderResult> {
  if (bytes.length > HIVE_MAX_IMAGE_BYTES) {
    throw badRequest("Hive base64 uploads are limited to 20 MB.");
  }
  const secret = Deno.env.get("HIVE_SECRET_KEY")?.trim();
  if (!secret) {
    throw serviceUnavailable("Hive server credential is not configured.");
  }

  const response = await fetch(HIVE_ENDPOINT, {
    method: "POST",
    headers: {
      accept: "application/json",
      authorization: `Bearer ${secret}`,
      "content-type": "application/json",
    },
    body: JSON.stringify({
      input: [{ media_base64: encodeBase64(bytes) }],
      processing_mode: "sync_with_fallback",
    }),
    signal: AbortSignal.timeout(60_000),
  });
  const responseText = await response.text();
  let raw: unknown;
  try {
    raw = JSON.parse(responseText);
  } catch {
    if (!response.ok) {
      throw new HiveRequestError(
        `Hive returned non-JSON (HTTP ${response.status}).`,
        response.status,
      );
    }
    throw new Error(`Hive returned non-JSON (HTTP ${response.status}).`);
  }
  if (!response.ok) {
    throw new HiveRequestError(
      `Hive request failed (HTTP ${response.status}): ${vendorMessage(raw)}`,
      response.status,
    );
  }
  return parseHiveResponse(raw);
}

function mockProvider(bytes: Uint8Array, mode: GradeMode): ProviderResult {
  const salt = { sdxl: 0x31, flux_schnell: 0x67, real: 0xa3 }[mode];
  const seed = seededValue(bytes, salt);
  const names = {
    sdxl: ["sdxl", "stable-diffusion", "real"],
    flux_schnell: ["flux-schnell", "flux", "real"],
    real: ["real", "ernie", "flux"],
  }[mode];
  const first = clamp01(0.45 + seed * 0.45);
  const second = clamp01(0.08 + ((seed * 7.13) % 1) * 0.24);
  const third = clamp01(Math.max(0.01, 1 - first - second));
  const sourceTotal = first + second + third;
  const sources = {
    [names[0]]: round6(first / sourceTotal),
    [names[1]]: round6(second / sourceTotal),
    [names[2]]: round6(third / sourceTotal),
  };
  return {
    aiProbability: round6(0.035 + seed * 0.46),
    deepfakeProbability: round6(0.005 + ((seed * 3.71) % 1) * 0.18),
    sources,
    raw: {
      provider: "MOCK",
      schema: "relab-mock-v1",
      mode,
      deterministic_seed: round6(seed),
      notice: "Synthetic grade; no vendor API was called.",
    },
  };
}

async function normalizeAndCache(
  result: ProviderResult,
  bytes: Uint8Array,
  imageSha256: string,
  provider: "mock" | "g1",
  mode: GradeMode,
): Promise<CachedGrade> {
  const aiProbability = unitProbability(result.aiProbability, "ai_probability");
  const deepfakeProbability = unitProbability(
    result.deepfakeProbability,
    "deepfake_probability",
  );
  validateSources(result.sources);
  const timestamp = new Date().toISOString();
  const grade: CachedGrade = {
    grade_id: await gradeId(bytes, provider, mode, timestamp),
    image_sha256: imageSha256,
    vendor: provider,
    mode,
    ai_probability: aiProbability,
    deepfake_probability: deepfakeProbability,
    verdict: verdictFor(aiProbability),
    top_source: topSource(normalizedSources(result.sources)),
    sources: normalizedSources(result.sources),
    raw: redactRaw(result.raw) as Record<string, unknown>,
    mock: provider === "mock",
  };
  await storeCachedGrade(grade);
  return grade;
}

async function cachedGrade(
  imageSha256: string,
  vendor: "mock" | "g1",
  mode: GradeMode,
): Promise<CachedGrade | null> {
  const { data, error } = await adminClient()
    .from("grade_cache")
    .select(
      "grade_id,image_sha256,vendor,mode,ai_probability,deepfake_probability,verdict,top_source,sources,raw,mock",
    )
    .eq("image_sha256", imageSha256)
    .eq("vendor", vendor)
    .eq("mode", mode)
    .maybeSingle();
  if (error) {
    if (vendor === "mock" && isMissingRelation(error)) return null;
    throw new Error(`Grade cache unavailable: ${error.message}`);
  }
  if (!data) return null;
  return data as CachedGrade;
}

async function storeCachedGrade(grade: CachedGrade): Promise<void> {
  const { error } = await adminClient().from("grade_cache").upsert(
    {
      ...grade,
      sources: grade.sources,
      raw: grade.raw,
      last_accessed_at: new Date().toISOString(),
    },
    { onConflict: "image_sha256,vendor,mode", ignoreDuplicates: true },
  );
  if (error && !(grade.mock && isMissingRelation(error))) {
    throw new Error(`Grade cache write failed: ${error.message}`);
  }
}

async function reserveVendorCall(
  sessionId: string,
  userId: string,
  cap: number,
): Promise<SessionUsage> {
  const { data, error } = await adminClient().rpc("reserve_grade_call", {
    p_session_id: sessionId,
    p_user_id: userId,
    p_cap: cap,
  });
  if (error) {
    throw new Error(`Grade budget counter unavailable: ${error.message}`);
  }
  const row = Array.isArray(data) ? data[0] : data;
  if (!row || row.allowed !== true) {
    throw paymentRequired(`Session grade cap reached (${cap}).`);
  }
  return {
    vendor_calls: Number(row.vendor_calls),
    cap: Number(row.session_cap),
  };
}

async function currentUsage(
  sessionId: string,
  userId: string,
  cap: number,
): Promise<SessionUsage> {
  const { data, error } = await adminClient()
    .from("grade_sessions")
    .select("vendor_calls,session_cap")
    .eq("id", sessionId)
    .eq("user_id", userId)
    .maybeSingle();
  if (error) {
    if (isMissingRelation(error)) return { vendor_calls: 0, cap };
    throw new Error(`Grade budget counter unavailable: ${error.message}`);
  }
  return data
    ? { vendor_calls: Number(data.vendor_calls), cap: Number(data.session_cap) }
    : { vendor_calls: 0, cap };
}

function pairIndexes(
  remintSources: Record<string, number>,
  ogSources?: Record<string, number>,
): { swapIndex: number; retentionIndex: number } {
  if (!ogSources) return { swapIndex: 0, retentionIndex: 0 };
  const ogTopThree = new Set(
    Object.entries(ogSources)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 3)
      .map(([family]) => family),
  );
  const entries = Object.entries(remintSources).filter(([, value]) =>
    value > 0
  );
  const total = entries.reduce((sum, [, value]) => sum + value, 0);
  if (total <= 0) return { swapIndex: 0, retentionIndex: 0 };
  const retained = entries.reduce(
    (sum, [family, value]) => sum + (ogTopThree.has(family) ? value : 0),
    0,
  );
  return {
    swapIndex: round6(clamp01((total - retained) / total)),
    retentionIndex: round6(clamp01(retained / total)),
  };
}

async function readImageBytes(input: GradeInput): Promise<Uint8Array> {
  if (input.image_b64) return decodeBase64(input.image_b64);
  const response = await fetchRemoteImage(
    safeRemoteUrl(input.image_url as string),
  );
  if (!response.ok) {
    throw badRequest(`Could not fetch image_url (HTTP ${response.status}).`);
  }
  const length = Number(response.headers.get("content-length") ?? 0);
  if (length > MAX_IMAGE_BYTES) {
    throw badRequest("Image exceeds the 25 MB grading limit.");
  }
  const bytes = new Uint8Array(await response.arrayBuffer());
  if (!bytes.length) throw badRequest("Image is empty.");
  if (bytes.length > MAX_IMAGE_BYTES) {
    throw badRequest("Image exceeds the 25 MB grading limit.");
  }
  return bytes;
}

async function fetchRemoteImage(initialUrl: URL): Promise<Response> {
  let url = initialUrl;
  for (let redirect = 0; redirect <= 3; redirect += 1) {
    const response = await fetch(url, {
      redirect: "manual",
      signal: AbortSignal.timeout(30_000),
    });
    if (![301, 302, 303, 307, 308].includes(response.status)) return response;
    const location = response.headers.get("location");
    if (!location) {
      throw badRequest("image_url redirect is missing a location.");
    }
    if (redirect === 3) throw badRequest("image_url has too many redirects.");
    url = safeRemoteUrl(new URL(location, url).toString());
  }
  throw badRequest("image_url could not be fetched.");
}

function decodeBase64(value: string): Uint8Array {
  const encoded = value.includes(",")
    ? value.slice(value.indexOf(",") + 1)
    : value;
  if (!encoded || encoded.length > Math.ceil((MAX_IMAGE_BYTES * 4) / 3) + 8) {
    throw badRequest("image_b64 is empty or exceeds the 25 MB grading limit.");
  }
  try {
    const binary = atob(encoded.replace(/\s/g, ""));
    const bytes = Uint8Array.from(
      binary,
      (character) => character.charCodeAt(0),
    );
    if (!bytes.length) throw new Error("empty");
    return bytes;
  } catch {
    throw badRequest("image_b64 is not valid base64.");
  }
}

function encodeBase64(bytes: Uint8Array): string {
  const chunks: string[] = [];
  const chunkSize = 0x8000;
  for (let offset = 0; offset < bytes.length; offset += chunkSize) {
    chunks.push(
      String.fromCharCode(...bytes.subarray(offset, offset + chunkSize)),
    );
  }
  return btoa(chunks.join(""));
}

function safeRemoteUrl(value: string): URL {
  let url: URL;
  try {
    url = new URL(value);
  } catch {
    throw badRequest("image_url is invalid.");
  }
  if (url.protocol !== "https:") throw badRequest("image_url must use HTTPS.");
  const host = url.hostname.toLowerCase().replace(/^\[|\]$/g, "");
  if (
    host === "localhost" ||
    host.endsWith(".localhost") ||
    host.endsWith(".local") ||
    host === "::1" ||
    host.startsWith("fc") ||
    host.startsWith("fd") ||
    host.startsWith("fe80:") ||
    isPrivateIpv4(host)
  ) {
    throw badRequest("image_url host is not allowed.");
  }
  return url;
}

function isPrivateIpv4(host: string): boolean {
  const match = host.match(/^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$/);
  if (!match) return false;
  const parts = match.slice(1).map(Number);
  if (parts.some((part) => part > 255)) return true;
  const [a, b] = parts;
  return (
    a === 0 ||
    a === 10 ||
    a === 127 ||
    (a === 169 && b === 254) ||
    (a === 172 && b >= 16 && b <= 31) ||
    (a === 192 && b === 168)
  );
}

function providerName(): "mock" | "g1" {
  const value = (Deno.env.get("GRADE_PROVIDER") ?? "mock").trim().toLowerCase();
  if (value === "mock") return "mock";
  if (value === "g1") return "g1";
  throw serviceUnavailable("GRADE_PROVIDER must be mock or g1.");
}

function ownerDefaultMode(): GradeMode | null {
  const value = Deno.env.get("GRADE_DEFAULT_MODE")?.trim().toLowerCase();
  return value && MODES.has(value as GradeMode) ? (value as GradeMode) : null;
}

function sessionCap(): number {
  const value = Number(
    Deno.env.get("GRADE_SESSION_CAP") ?? DEFAULT_SESSION_CAP,
  );
  return Number.isInteger(value) && value > 0 && value <= 10_000
    ? value
    : DEFAULT_SESSION_CAP;
}

function verdictFor(probability: number): Verdict {
  const value = clamp01(probability);
  if (value <= 0.1) return "CLEAR";
  if (value <= 0.15) return "NEAR";
  if (value <= 0.3) return "BORDER";
  return "FAIL";
}

function normalizedSources(
  sources: Record<string, number>,
): Record<string, number> {
  return Object.fromEntries(
    Object.entries(sources)
      .map(([key, value]) =>
        [
          key.trim().toLowerCase(),
          round6(value > 1 ? clamp01(value / 100) : clamp01(value)),
        ] as const
      )
      .filter(([key]) => key.length > 0)
      .sort((a, b) => b[1] - a[1]),
  );
}

function topSource(sources: Record<string, number>): string | null {
  return Object.entries(sources).sort((a, b) => b[1] - a[1])[0]?.[0] ?? null;
}

function validateSources(sources: Record<string, number>) {
  if (!sources || typeof sources !== "object" || Array.isArray(sources)) {
    throw badRequest("sources must be an object.");
  }
  for (const [key, value] of Object.entries(sources)) {
    if (
      !key || typeof value !== "number" || !Number.isFinite(value) ||
      value < 0 || value > 100
    ) {
      throw badRequest("sources values must be finite probabilities.");
    }
  }
}

function unitProbability(value: number, label: string): number {
  if (!Number.isFinite(value) || value < 0 || value > 100) {
    throw new Error(`${label} from the provider is outside 0..1 or 0..100.`);
  }
  return round6(value > 1 ? value / 100 : value);
}

function redactRaw(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(redactRaw);
  if (!value || typeof value !== "object") return value;
  const out: Record<string, unknown> = {};
  for (const [key, next] of Object.entries(value as Record<string, unknown>)) {
    out[key] = /(api.?key|token|authorization|secret|endpoint)/i.test(key)
      ? "[REDACTED]"
      : redactRaw(next);
  }
  return out;
}

function seededValue(bytes: Uint8Array, salt: number): number {
  let value = (0x811c9dc5 ^ salt) >>> 0;
  const step = Math.max(1, Math.floor(bytes.length / 2048));
  for (let index = 0; index < bytes.length; index += step) {
    value ^= bytes[index];
    value = Math.imul(value, 0x01000193) >>> 0;
  }
  return value / 0xffffffff;
}

async function gradeId(
  bytes: Uint8Array,
  vendor: string,
  mode: GradeMode,
  timestamp: string,
): Promise<string> {
  const suffix = new TextEncoder().encode(`${vendor}:${mode}:${timestamp}`);
  const combined = new Uint8Array(bytes.length + suffix.length);
  combined.set(bytes);
  combined.set(suffix, bytes.length);
  return sha256Hex(combined);
}

async function sha256Hex(bytes: Uint8Array): Promise<string> {
  const digest = await crypto.subtle.digest(
    "SHA-256",
    new Uint8Array(bytes).buffer,
  );
  return Array.from(
    new Uint8Array(digest),
    (byte) => byte.toString(16).padStart(2, "0"),
  ).join("");
}

function isMissingRelation(
  error: { code?: string; message?: string },
): boolean {
  return error.code === "42P01" ||
    /relation .* does not exist/i.test(error.message ?? "");
}

function isUuid(value: string): boolean {
  return /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i
    .test(value);
}

function safeError(error: unknown): string {
  return error instanceof Error
    ? error.message.slice(0, 300)
    : "Vendor request failed.";
}

function vendorMessage(value: unknown): string {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return "Vendor rejected the request.";
  }
  const record = value as Record<string, unknown>;
  const message = [record.message, record.error, record.detail].find((item) =>
    typeof item === "string" && item.length > 0
  );
  return typeof message === "string"
    ? message.replace(/[\r\n]+/g, " ").slice(0, 240)
    : "Vendor rejected the request.";
}

function shouldRetryVendorError(error: unknown): boolean {
  if (error instanceof HiveRequestError) {
    return error.status === 408 || error.status === 429 || error.status >= 500;
  }
  return error instanceof TypeError || error instanceof DOMException;
}

function clamp01(value: number): number {
  return Math.max(0, Math.min(1, value));
}

function round6(value: number): number {
  return Math.round(value * 1_000_000) / 1_000_000;
}

type ApiError = Error & { status?: number };

class VendorAttemptError extends Error {
  calls: number;

  constructor(message: string, calls: number) {
    super(message);
    this.name = "VendorAttemptError";
    this.calls = calls;
  }
}

class HiveRequestError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "HiveRequestError";
    this.status = status;
  }
}

function badRequest(message: string): ApiError {
  return Object.assign(new Error(message), { status: 400 });
}

function paymentRequired(message: string): ApiError {
  return Object.assign(new Error(message), { status: 402 });
}

function serviceUnavailable(message: string): ApiError {
  return Object.assign(new Error(message), { status: 503 });
}

function toApiError(error: unknown): { message: string; status: number } {
  if (error instanceof Error) {
    return {
      message: error.message,
      status: (error as ApiError).status ?? 500,
    };
  }
  return { message: "Image grading failed.", status: 500 };
}
