import { corsHeaders, jsonResponse } from "../_shared/cors.ts";
import {
  assertSha256,
  corpusBucket,
  corpusMaxImages,
  corpusStorageByteLimit,
  CorpusHttpError,
  errorResponse,
  requireCorpusAdmin,
  safeFileName,
} from "../_shared/corpus.ts";
import { canonicalOriginalPath } from "../_shared/corpus_image.ts";

const MIN_RESUMABLE_BYTES = 6 * 1024 * 1024;
const MAX_BYTES = 25 * 1024 * 1024;
const MIME_EXTENSIONS = new Map([
  ["image/jpeg", "jpg"],
  ["image/png", "png"],
  ["image/webp", "webp"],
] as const);

Deno.serve(async (request) => {
  if (request.method === "OPTIONS") return new Response("ok", { headers: corsHeaders });
  if (request.method !== "POST") return jsonResponse({ error: "Method not allowed" }, 405);
  try {
    const { client } = await requireCorpusAdmin(request);
    const body = await request.json() as Record<string, unknown>;
    safeFileName(body.file_name);
    const sha256 = assertSha256(body.sha256);
    const fileSize = Number(body.file_size);
    const contentType = typeof body.content_type === "string" ? body.content_type : "";
    const extension = MIME_EXTENSIONS.get(contentType as "image/jpeg" | "image/png" | "image/webp");
    if (!Number.isSafeInteger(fileSize) || fileSize <= MIN_RESUMABLE_BYTES || fileSize > MAX_BYTES) {
      throw new CorpusHttpError("Resumable uploads must be larger than 6 MB and no larger than 25 MB.", 400);
    }
    if (!extension) throw new CorpusHttpError("content_type must be JPEG, PNG, or WebP.", 400);
    const storageLimit = corpusStorageByteLimit();

    const { data: duplicate, error: duplicateError } = await client
      .from("corpus_images").select("id,sha256,file_name,width,height,byte_size,content_type,created_at")
      .eq("sha256", sha256).maybeSingle();
    if (duplicateError) throw duplicateError;
    if (duplicate) return jsonResponse({ duplicate: true, corpus_image: duplicate });

    const [{ count, error: countError }, { data: sizes, error: sizeError }] = await Promise.all([
      client.from("corpus_images").select("id", { count: "exact", head: true }),
      client.from("corpus_images").select("byte_size"),
    ]);
    if (countError) throw countError;
    if (sizeError) throw sizeError;
    if ((count ?? 0) >= corpusMaxImages()) throw new CorpusHttpError("Corpus image cap reached.", 409);
    const usedBytes = (sizes ?? []).reduce((sum, row) => sum + Number(row.byte_size), 0);
    if (usedBytes + fileSize > storageLimit) throw new CorpusHttpError("Corpus storage-byte ceiling reached.", 409);

    const bucket = corpusBucket();
    const storagePath = canonicalOriginalPath(sha256, extension);
    const { data: signed, error } = await client.storage.from(bucket)
      .createSignedUploadUrl(storagePath, { upsert: false });
    if (error) throw error;
    return jsonResponse({
      duplicate: false,
      bucket,
      storage_path: storagePath,
      upload_token: signed.token,
      resumable_endpoint: resumableEndpoint(),
      chunk_size: 6 * 1024 * 1024,
      upload_token_ttl_seconds: 2 * 60 * 60,
    });
  } catch (error) {
    const response = errorResponse(error);
    return jsonResponse({ error: response.message }, response.status);
  }
});

function resumableEndpoint(): string {
  const raw = Deno.env.get("SUPABASE_URL");
  if (!raw) throw new CorpusHttpError("Missing Supabase service configuration.", 503);
  const url = new URL(raw);
  if (url.hostname.endsWith(".supabase.co")) {
    url.hostname = url.hostname.replace(/\.supabase\.co$/, ".storage.supabase.co");
  }
  url.pathname = "/storage/v1/upload/resumable";
  url.search = "";
  return url.toString();
}
