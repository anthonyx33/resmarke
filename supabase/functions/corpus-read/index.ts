import { corsHeaders, jsonResponse } from "../_shared/cors.ts";
import {
  assertUuid,
  corpusBucket,
  corpusDownloadTtl,
  CorpusHttpError,
  errorResponse,
  requireCorpusAdmin,
} from "../_shared/corpus.ts";

Deno.serve(async (request) => {
  if (request.method === "OPTIONS") return new Response("ok", { headers: corsHeaders });
  if (request.method !== "POST") return jsonResponse({ error: "Method not allowed" }, 405);
  try {
    const { client } = await requireCorpusAdmin(request);
    const body = await request.json().catch(() => ({})) as Record<string, unknown>;
    const imageId = body.corpus_image_id ? assertUuid(body.corpus_image_id, "corpus_image_id") : null;
    const experimentId = body.experiment_id ? assertUuid(body.experiment_id, "experiment_id") : null;
    if (!imageId && !experimentId) throw new CorpusHttpError("corpus_image_id or experiment_id is required.", 400);

    let query = client.from("corpus_runs").select("*").order("created_at", { ascending: false }).limit(2_000);
    if (imageId) query = query.eq("corpus_image_id", imageId);
    if (experimentId) query = query.eq("experiment_id", experimentId);
    const { data: runs, error } = await query;
    if (error) throw error;

    const imageIds = Array.from(new Set((runs ?? []).map((run) => run.corpus_image_id).concat(imageId ? [imageId] : [])));
    const { data: images, error: imagesError } = imageIds.length
      ? await client.from("corpus_images").select("*").in("id", imageIds)
      : { data: [], error: null };
    if (imagesError) throw imagesError;
    const ttl = corpusDownloadTtl();
    const originalPaths = (images ?? []).map((image) => image.storage_path);
    const outputPaths = (runs ?? []).map((run) => run.output_storage_path).filter(Boolean);
    const paths = Array.from(new Set([...originalPaths, ...outputPaths]));
    const { data: signed, error: signedError } = paths.length
      ? await client.storage.from(corpusBucket()).createSignedUrls(paths, ttl)
      : { data: [], error: null };
    if (signedError) throw signedError;
    const signedByPath = new Map((signed ?? []).map((entry) => [entry.path, entry.signedUrl]));
    const safeImages = (images ?? []).map(({ storage_path, ...image }) => ({ ...image, signed_url: signedByPath.get(storage_path) ?? null }));
    const safeRuns = (runs ?? []).map(({ output_storage_path, ...run }) => ({ ...run, output_url: signedByPath.get(output_storage_path) ?? null }));
    return jsonResponse({ images: safeImages, runs: safeRuns, signed_url_ttl_seconds: ttl });
  } catch (error) {
    const response = errorResponse(error);
    return jsonResponse({ error: response.message }, response.status);
  }
});
