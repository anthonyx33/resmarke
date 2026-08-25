import { userFromRequest } from "./supabase.ts";
import type { SupabaseClient } from "https://esm.sh/@supabase/supabase-js@2.88.0";

export class CorpusHttpError extends Error {
  constructor(message: string, readonly status: number) {
    super(message);
  }
}

export async function requireCorpusAdmin(request: Request) {
  const authenticated = await userFromRequest(request);
  const uuidAllowlist = envList("CORPUS_ADMIN_UUIDS");
  const emailAllowlist = envList("CORPUS_ADMIN_EMAILS").map((value) => value.toLowerCase());
  const userEmail = authenticated.user.email?.trim().toLowerCase() ?? "";
  const uuidAllowed = uuidAllowlist.includes(authenticated.user.id);
  const emailAllowed = Boolean(
    userEmail && authenticated.user.email_confirmed_at && emailAllowlist.includes(userEmail),
  );

  if (!uuidAllowlist.length && !emailAllowlist.length) {
    throw new CorpusHttpError("Corpus admin allowlist is not configured.", 503);
  }
  if (!uuidAllowed && !emailAllowed) {
    throw new CorpusHttpError("Corpus admin access is required.", 403);
  }
  return authenticated;
}

export function corpusBucket(): string {
  const value = Deno.env.get("CORPUS_BUCKET")?.trim() || "corpus";
  if (!/^[a-z0-9][a-z0-9._-]{0,62}$/i.test(value)) {
    throw new CorpusHttpError("CORPUS_BUCKET is invalid.", 503);
  }
  return value;
}

export function corpusMaxImages(): number {
  return boundedEnvInteger("CORPUS_MAX_IMAGES", 200, 1, 10_000);
}

export function corpusMaxOutputsPerImage(): number {
  return boundedEnvInteger("CORPUS_MAX_OUTPUTS_PER_IMAGE", 20, 1, 10_000);
}

export function corpusDownloadTtl(): number {
  return boundedEnvInteger("CORPUS_DOWNLOAD_TTL_SECONDS", 120, 30, 3_600);
}

export function corpusStorageByteLimit(): number {
  const raw = Deno.env.get("CORPUS_STORAGE_BYTE_LIMIT_BYTES")?.trim();
  const parsed = raw ? Number(raw) : Number.NaN;
  if (!Number.isSafeInteger(parsed) || parsed < 25 * 1024 * 1024) {
    throw new CorpusHttpError(
      "CORPUS_STORAGE_BYTE_LIMIT_BYTES must be configured before corpus uploads.",
      503,
    );
  }
  return parsed;
}

export function assertUuid(value: unknown, field: string): string {
  if (typeof value !== "string" ||
      !/^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(value)) {
    throw new CorpusHttpError(`${field} must be a UUID.`, 400);
  }
  return value;
}

export function assertSha256(value: unknown, field = "sha256"): string {
  if (typeof value !== "string" || !/^[0-9a-f]{64}$/.test(value)) {
    throw new CorpusHttpError(`${field} must be a lowercase SHA-256 hex digest.`, 400);
  }
  return value;
}

export function canonicalJson(value: unknown): string {
  const walk = (current: unknown): unknown => {
    if (current === null || typeof current !== "object") return current;
    if (Array.isArray(current)) return current.map(walk);
    const record = current as Record<string, unknown>;
    return Object.fromEntries(Object.keys(record).sort().map((key) => [key, walk(record[key])]));
  };
  return JSON.stringify(walk(value));
}

export async function sha256Hex(bytes: Uint8Array | string): Promise<string> {
  const source = typeof bytes === "string" ? new TextEncoder().encode(bytes) : new Uint8Array(bytes);
  const digest = await crypto.subtle.digest("SHA-256", source.buffer);
  return [...new Uint8Array(digest)]
    .map((value) => value.toString(16).padStart(2, "0"))
    .join("");
}

export function safeFileName(value: unknown): string {
  if (typeof value !== "string" || !value.trim()) {
    throw new CorpusHttpError("file_name is required.", 400);
  }
  const name = value.trim().split(/[\\/]/).pop()!.replace(/[\u0000-\u001f\u007f]/g, "");
  return name.slice(0, 220) || "image";
}

export function decodeImageBase64(value: unknown, maxBytes: number): Uint8Array {
  if (typeof value !== "string" || !value) {
    throw new CorpusHttpError("image_b64 is required.", 400);
  }
  const encoded = value.replace(/^data:[^;,]+;base64,/i, "").replace(/\s/g, "");
  if (!encoded || encoded.length > Math.ceil(maxBytes / 3) * 4 + 8) {
    throw new CorpusHttpError(`Image exceeds the ${Math.floor(maxBytes / 1024 / 1024)} MB limit.`, 413);
  }
  try {
    const binary = atob(encoded);
    if (!binary.length || binary.length > maxBytes) {
      throw new CorpusHttpError(`Image exceeds the ${Math.floor(maxBytes / 1024 / 1024)} MB limit.`, 413);
    }
    return Uint8Array.from(binary, (character) => character.charCodeAt(0));
  } catch (error) {
    if (error instanceof CorpusHttpError) throw error;
    throw new CorpusHttpError("image_b64 is not valid base64.", 400);
  }
}

export function jsonObject(value: unknown, field: string): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new CorpusHttpError(`${field} must be a JSON object.`, 400);
  }
  return value as Record<string, unknown>;
}

export function errorResponse(error: unknown): { status: number; message: string } {
  if (error instanceof CorpusHttpError) return { status: error.status, message: error.message };
  if (error && typeof error === "object") {
    const candidate = error as { code?: unknown; message?: unknown };
    const message = typeof candidate.message === "string" ? candidate.message : "Corpus request failed.";
    if (candidate.code === "23505") return { status: 409, message };
    if (candidate.code === "23503" || candidate.code === "23514" || candidate.code === "P0002") {
      return { status: candidate.code === "P0002" ? 404 : 409, message };
    }
    if (message && message !== "{}" && message !== "Corpus request failed.") {
      return { status: 500, message };
    }
  }
  return {
    status: 500,
    message: describeUnknownError(error),
  };
}

function describeUnknownError(error: unknown): string {
  if (error instanceof Error) {
    const candidate = error as Error & {
      statusCode?: unknown;
      code?: unknown;
      details?: unknown;
      hint?: unknown;
      context?: unknown;
    };
    const extras: Record<string, unknown> = {};
    for (const key of ["statusCode", "code", "details", "hint"] as const) {
      if (candidate[key] !== undefined && candidate[key] !== null) extras[key] = candidate[key];
    }
    const suffix = Object.keys(extras).length ? ` | ${JSON.stringify(extras)}` : "";
    return `${candidate.name}: ${candidate.message}${suffix}`;
  }
  try {
    return `non-error: ${JSON.stringify(error)}`;
  } catch {
    return "Corpus request failed with an unknown non-serializable error.";
  }
}

// storage-js v2 `download()` resolves `{ data: Blob | null, error }` — it does
// NOT reject on missing objects, and its error message for a missing object is
// an opaque `StorageUnknownError: {}`. Callers must therefore treat
// `{ bytes: null }` as "object absent" and only surface errors where relevant.
export async function downloadStorageBytes(
  client: SupabaseClient,
  bucket: string,
  path: string,
): Promise<{ bytes: Uint8Array | null; error: string | null }> {
  const { data, error } = await client.storage.from(bucket).download(path);
  if (error) return { bytes: null, error: storageErrorText(error) };
  if (!data) return { bytes: null, error: null };
  return { bytes: new Uint8Array(await data.arrayBuffer()), error: null };
}

export function storageErrorText(error: unknown): string {
  const candidate = error as {
    name?: unknown;
    message?: unknown;
    status?: unknown;
    statusCode?: unknown;
    originalError?: unknown;
  };
  const parts: string[] = [];
  if (typeof candidate.name === "string") parts.push(candidate.name);
  const httpStatus = candidate.statusCode ?? candidate.status;
  if (typeof httpStatus === "number") parts.push(`HTTP ${httpStatus}`);
  if (typeof candidate.message === "string" && candidate.message && candidate.message !== "{}") {
    parts.push(candidate.message);
  }
  if (candidate.originalError !== undefined) {
    try {
      const text = JSON.stringify(candidate.originalError);
      if (text && text !== "{}") parts.push(text.slice(0, 200));
    } catch {
      parts.push("<original error not serializable>");
    }
  }
  return parts.join(" · ") || "unknown storage error";
}

function envList(name: string): string[] {
  return Array.from(new Set(
    (Deno.env.get(name) ?? "").split(",").map((value) => value.trim()).filter(Boolean),
  ));
}

function boundedEnvInteger(name: string, fallback: number, min: number, max: number): number {
  const raw = Deno.env.get(name)?.trim();
  const parsed = raw ? Number(raw) : fallback;
  if (!Number.isInteger(parsed) || parsed < min || parsed > max) {
    throw new CorpusHttpError(`${name} is invalid.`, 503);
  }
  return parsed;
}
