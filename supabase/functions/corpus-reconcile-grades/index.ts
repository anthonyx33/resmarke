import { corsHeaders, jsonResponse } from "../_shared/cors.ts";
import {
  assertUuid,
  CorpusHttpError,
  errorResponse,
  requireCorpusAdmin,
} from "../_shared/corpus.ts";
import { gradePairFromRows, type GradeCacheRow } from "../_shared/corpus_grades.ts";

Deno.serve(async (request) => {
  if (request.method === "OPTIONS") return new Response("ok", { headers: corsHeaders });
  if (request.method !== "POST") return jsonResponse({ error: "Method not allowed" }, 405);
  try {
    const { client } = await requireCorpusAdmin(request);
    const body = await request.json() as Record<string, unknown>;
    const experimentId = body.experiment_id ? assertUuid(body.experiment_id, "experiment_id") : null;
    const runIds = Array.isArray(body.run_ids)
      ? body.run_ids.map((value) => assertUuid(value, "run_ids[]"))
      : [];
    if (!experimentId && !runIds.length) throw new CorpusHttpError("experiment_id or run_ids is required.", 400);
    if (runIds.length > 500) throw new CorpusHttpError("At most 500 run_ids may be reconciled at once.", 400);

    let query = client.from("corpus_runs").select("id,experiment_id,corpus_image_id,output_sha256,grade_status")
      .in("grade_status", ["PENDING", "ERROR"]).limit(500);
    if (experimentId) query = query.eq("experiment_id", experimentId);
    if (runIds.length) query = query.in("id", runIds);
    const { data: runs, error: runsError } = await query;
    if (runsError) throw runsError;
    if (!runs?.length) return jsonResponse({ completed: 0, still_pending: 0 });

    const experimentIds = Array.from(new Set(runs.map((run) => run.experiment_id)));
    const imageIds = Array.from(new Set(runs.map((run) => run.corpus_image_id)));
    const [{ data: experiments, error: experimentsError }, { data: images, error: imagesError }] = await Promise.all([
      client.from("corpus_experiments").select("id,detector_vendor,detector_mode").in("id", experimentIds),
      client.from("corpus_images").select("id,sha256").in("id", imageIds),
    ]);
    if (experimentsError) throw experimentsError;
    if (imagesError) throw imagesError;
    const experimentMap = new Map((experiments ?? []).map((item) => [item.id, item]));
    const imageMap = new Map((images ?? []).map((item) => [item.id, item.sha256]));
    const cache = new Map<string, GradeCacheRow>();
    const groups = new Map<string, { vendor: string; mode: string; hashes: Set<string> }>();
    for (const run of runs) {
      const experiment = experimentMap.get(run.experiment_id);
      const ogSha = imageMap.get(run.corpus_image_id);
      if (!experiment || !ogSha) continue;
      const key = `${experiment.detector_vendor}:${experiment.detector_mode}`;
      const group = groups.get(key) ?? { vendor: experiment.detector_vendor, mode: experiment.detector_mode, hashes: new Set<string>() };
      group.hashes.add(ogSha);
      group.hashes.add(run.output_sha256);
      groups.set(key, group);
    }
    for (const group of groups.values()) {
      const hashes = [...group.hashes];
      for (let offset = 0; offset < hashes.length; offset += 100) {
        const { data, error } = await client.from("grade_cache")
          .select("grade_id,image_sha256,vendor,mode,ai_probability,deepfake_probability,verdict,top_source,sources,raw,mock,created_at")
          .eq("vendor", group.vendor).eq("mode", group.mode).in("image_sha256", hashes.slice(offset, offset + 100));
        if (error) throw error;
        for (const row of (data ?? []) as GradeCacheRow[]) cache.set(cacheKey(row.image_sha256, row.vendor, row.mode), row);
      }
    }

    let completed = 0;
    let stillPending = 0;
    for (const run of runs) {
      const experiment = experimentMap.get(run.experiment_id);
      const ogSha = imageMap.get(run.corpus_image_id);
      if (!experiment || !ogSha) {
        stillPending += 1;
        continue;
      }
      const pair = gradePairFromRows(
        cache.get(cacheKey(ogSha, experiment.detector_vendor, experiment.detector_mode)) ?? null,
        cache.get(cacheKey(run.output_sha256, experiment.detector_vendor, experiment.detector_mode)) ?? null,
      );
      if (pair.gradeStatus !== "COMPLETE") {
        stillPending += 1;
        continue;
      }
      const { error } = await client.from("corpus_runs").update({
        grade_status: "COMPLETE",
        og_grade: pair.ogGrade,
        remint_grade: pair.remintGrade,
        delta: pair.delta,
        swap_index: pair.swapIndex,
        retention_index: pair.retentionIndex,
        qa_flag: pair.qaFlag,
      }).eq("id", run.id).in("grade_status", ["PENDING", "ERROR"]);
      if (error) throw error;
      completed += 1;
    }
    return jsonResponse({ completed, still_pending: stillPending });
  } catch (error) {
    const response = errorResponse(error);
    return jsonResponse({ error: response.message }, response.status);
  }
});

function cacheKey(sha256: string, vendor: string, mode: string): string {
  return `${sha256}:${vendor}:${mode}`;
}
