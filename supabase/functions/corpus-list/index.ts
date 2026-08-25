import { corsHeaders, jsonResponse } from "../_shared/cors.ts";
import {
  corpusBucket,
  corpusDownloadTtl,
  corpusMaxImages,
  corpusMaxOutputsPerImage,
  errorResponse,
  requireCorpusAdmin,
} from "../_shared/corpus.ts";

Deno.serve(async (request) => {
  if (request.method === "OPTIONS") return new Response("ok", { headers: corsHeaders });
  if (request.method !== "POST") return jsonResponse({ error: "Method not allowed" }, 405);
  try {
    const { client, user } = await requireCorpusAdmin(request);
    const [imagesResult, setsResult, membersResult, experimentsResult, runsResult, leaderboardResult, jobsResult, usageResult, countsResult] = await Promise.all([
      client.from("corpus_images").select("*").is("archived_at", null).order("created_at", { ascending: false }),
      client.from("corpus_sets").select("*").is("archived_at", null).order("created_at", { ascending: false }),
      client.from("corpus_set_members").select("corpus_set_id,corpus_image_id,position").order("position"),
      client.from("corpus_experiments").select("*").is("archived_at", null).order("created_at", { ascending: false }),
      client.from("corpus_runs").select("id,experiment_id,corpus_image_id,config_label,config_key,requested_settings_code,grade_status,og_grade,remint_grade,delta,swap_index,retention_index,qa_flag,runtime_ms,output_copy_status,created_at").order("created_at", { ascending: false }).limit(2_000),
      client.from("corpus_leaderboard").select("*"),
      client.from("deepclean_jobs").select("engine_version").eq("status", "completed").not("engine_version", "is", null).order("completed_at", { ascending: false }).limit(200),
      client.rpc("corpus_storage_usage"),
      client.rpc("corpus_run_counts"),
    ]);
    for (const result of [imagesResult, setsResult, membersResult, experimentsResult, runsResult, leaderboardResult, jobsResult, usageResult, countsResult]) {
      if (result.error) throw result.error;
    }
    const images = imagesResult.data ?? [];
    const ttl = corpusDownloadTtl();
    const { data: signed, error: signedError } = images.length
      ? await client.storage.from(corpusBucket()).createSignedUrls(images.map((image) => image.storage_path), ttl)
      : { data: [], error: null };
    if (signedError) throw signedError;
    const signedByPath = new Map((signed ?? []).map((entry) => [entry.path, entry.signedUrl]));
    const countRows = (countsResult.data ?? []) as Array<{ corpus_image_id: string; run_count: number; pending_count: number }>;
    const runCounts = new Map<string, number>(
      countRows.map((row) => [row.corpus_image_id, Number(row.run_count)]),
    );
    const publicImages = images.map(({ storage_path, ...image }) => ({
      ...image,
      signed_url: signedByPath.get(storage_path) ?? null,
      run_count: runCounts.get(image.id) ?? 0,
    }));
    const usage = Array.isArray(usageResult.data) ? usageResult.data[0] : usageResult.data;
    const usedBytes = Number(usage?.total_bytes ?? 0);
    const engineReleases = Array.from(new Set((jobsResult.data ?? []).map((job) => job.engine_version).filter(Boolean)));
    return jsonResponse({
      is_admin: true,
      user_id: user.id,
      images: publicImages,
      sets: setsResult.data ?? [],
      members: membersResult.data ?? [],
      experiments: experimentsResult.data ?? [],
      runs: runsResult.data ?? [],
      leaderboard: leaderboardResult.data ?? [],
      engine_releases: engineReleases,
      caps: {
        max_images: corpusMaxImages(),
        max_outputs_per_image: corpusMaxOutputsPerImage(),
        storage_byte_limit: storageLimitOrNull(),
        used_bytes: usedBytes,
        download_ttl_seconds: ttl,
      },
      stats: {
        total_runs: countRows.reduce((sum, row) => sum + Number(row.run_count), 0),
        pending_runs: countRows.reduce((sum, row) => sum + Number(row.pending_count), 0),
      },
    });
  } catch (error) {
    const response = errorResponse(error);
    return jsonResponse({ error: response.message }, response.status);
  }
});

function storageLimitOrNull(): number | null {
  const value = Number(Deno.env.get("CORPUS_STORAGE_BYTE_LIMIT_BYTES"));
  return Number.isSafeInteger(value) && value > 0 ? value : null;
}
