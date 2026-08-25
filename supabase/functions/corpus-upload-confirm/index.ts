import { corsHeaders, jsonResponse } from "../_shared/cors.ts";
import {
  assertSha256,
  corpusBucket,
  corpusMaxImages,
  corpusStorageByteLimit,
  CorpusHttpError,
  downloadStorageBytes,
  errorResponse,
  requireCorpusAdmin,
  safeFileName,
  sha256Hex,
} from "../_shared/corpus.ts";
import { canonicalOriginalPath, inspectImage } from "../_shared/corpus_image.ts";

const MAX_BYTES = 25 * 1024 * 1024;

Deno.serve(async (request) => {
  if (request.method === "OPTIONS") return new Response("ok", { headers: corsHeaders });
  if (request.method !== "POST") return jsonResponse({ error: "Method not allowed" }, 405);
  let cleanup: (() => Promise<void>) | null = null;
  try {
    const { client, user } = await requireCorpusAdmin(request);
    const body = await request.json() as Record<string, unknown>;
    const claimedSha256 = assertSha256(body.claimed_sha256, "claimed_sha256");
    const fileName = safeFileName(body.claimed_file_name);
    const storagePath = typeof body.storage_path === "string" ? body.storage_path : "";
    if (!storagePath || !storagePath.startsWith(`${claimedSha256}/original.`)) {
      throw new CorpusHttpError("Stored object path is not canonical for the claimed hash.", 422);
    }
    const bucket = corpusBucket();
    cleanup = async () => {
      const { data } = await client.from("corpus_images").select("id")
        .eq("storage_path", storagePath).maybeSingle();
      if (!data) await client.storage.from(bucket).remove([storagePath]);
    };
    const { bytes, error: downloadError } = await downloadStorageBytes(client, bucket, storagePath);
    if (downloadError || !bytes) {
      throw new CorpusHttpError(
        `Stored object could not be re-read for verification: ${downloadError ?? "empty object"}`,
        422,
      );
    }
    if (bytes.length < 1 || bytes.length > MAX_BYTES) {
      throw new CorpusHttpError("Stored object exceeds the 25 MB corpus limit.", 422);
    }
    const header = inspectImage(bytes);
    const actualSha256 = await sha256Hex(bytes);
    if (actualSha256 !== claimedSha256) throw new CorpusHttpError("Stored object SHA-256 does not match the claim.", 422);
    const expectedPath = canonicalOriginalPath(actualSha256, header.extension);
    if (storagePath !== expectedPath) throw new CorpusHttpError("Stored object extension or path does not match its MIME magic.", 422);

    const { data, error } = await client.rpc("register_corpus_image", {
      p_sha256: actualSha256,
      p_storage_path: storagePath,
      p_file_name: fileName,
      p_byte_size: bytes.length,
      p_content_type: header.contentType,
      p_width: header.width,
      p_height: header.height,
      p_created_by: user.id,
      p_max_images: corpusMaxImages(),
      p_storage_byte_limit: corpusStorageByteLimit(),
    });
    if (error) throw error;
    const row = Array.isArray(data) ? data[0] : data;
    if (!row?.id) throw new Error("Corpus image registration returned no row.");
    if (row.storage_path !== storagePath) await cleanup();
    cleanup = null;
    return jsonResponse({ corpus_image: row, corpus_image_id: row.id, sha256: actualSha256, stored: row.storage_path === storagePath });
  } catch (error) {
    if (cleanup) await cleanup().catch(() => undefined);
    const response = errorResponse(error);
    return jsonResponse({ error: response.message }, response.status === 400 ? 422 : response.status);
  }
});
