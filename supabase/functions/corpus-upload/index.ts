import { corsHeaders, jsonResponse } from "../_shared/cors.ts";
import {
  corpusBucket,
  corpusMaxImages,
  corpusStorageByteLimit,
  decodeImageBase64,
  errorResponse,
  requireCorpusAdmin,
  safeFileName,
  sha256Hex,
} from "../_shared/corpus.ts";
import { canonicalOriginalPath, inspectImage } from "../_shared/corpus_image.ts";

const MAX_DIRECT_BYTES = 6 * 1024 * 1024;

Deno.serve(async (request) => {
  if (request.method === "OPTIONS") return new Response("ok", { headers: corsHeaders });
  if (request.method !== "POST") return jsonResponse({ error: "Method not allowed" }, 405);

  try {
    const { client, user } = await requireCorpusAdmin(request);
    const body = await request.json() as { image_b64?: unknown; file_name?: unknown };
    const fileName = safeFileName(body.file_name);
    const bytes = decodeImageBase64(body.image_b64, MAX_DIRECT_BYTES);
    const header = inspectImage(bytes);
    const sha256 = await sha256Hex(bytes);

    const { data: duplicate, error: duplicateError } = await client
      .from("corpus_images").select("*").eq("sha256", sha256).maybeSingle();
    if (duplicateError) throw duplicateError;
    if (duplicate) {
      return jsonResponse({ corpus_image: duplicate, corpus_image_id: duplicate.id, sha256, stored: false });
    }

    const bucket = corpusBucket();
    const storagePath = canonicalOriginalPath(sha256, header.extension);
    const { error: uploadError } = await client.storage.from(bucket).upload(storagePath, bytes, {
      contentType: header.contentType,
      cacheControl: "31536000",
      upsert: false,
    });
    if (uploadError && !/already exists|duplicate/i.test(uploadError.message)) throw uploadError;

    const { data, error } = await client.rpc("register_corpus_image", {
      p_sha256: sha256,
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
    if (error) {
      if (!uploadError) await client.storage.from(bucket).remove([storagePath]).catch(() => undefined);
      throw error;
    }
    const row = Array.isArray(data) ? data[0] : data;
    if (!row?.id) throw new Error("Corpus image registration returned no row.");
    return jsonResponse({ corpus_image: row, corpus_image_id: row.id, sha256, stored: true });
  } catch (error) {
    const response = errorResponse(error);
    return jsonResponse({ error: response.message }, response.status);
  }
});
