import { corsHeaders, jsonResponse } from "../_shared/cors.ts";
import {
  assertSha256,
  assertUuid,
  canonicalJson,
  corpusBucket,
  corpusMaxOutputsPerImage,
  corpusStorageByteLimit,
  CorpusHttpError,
  downloadStorageBytes,
  errorResponse,
  requireCorpusAdmin,
  sha256Hex,
} from "../_shared/corpus.ts";
import { cachedGradePair } from "../_shared/corpus_grades.ts";
import { canonicalOutputPath, inspectImage } from "../_shared/corpus_image.ts";

const MAX_BYTES = 25 * 1024 * 1024;

Deno.serve(async (request) => {
  if (request.method === "OPTIONS") return new Response("ok", { headers: corsHeaders });
  if (request.method !== "POST") return jsonResponse({ error: "Method not allowed" }, 405);
  let cleanupCopiedOutput: (() => Promise<void>) | null = null;
  try {
    const { client, user } = await requireCorpusAdmin(request);
    const body = await request.json() as Record<string, unknown>;
    const intentId = assertUuid(body.intent_id, "intent_id");
    const workerJobId = assertUuid(body.worker_job_id, "worker_job_id");

    const { data: existing, error: existingError } = await client.from("corpus_runs")
      .select("id,intent_id,grade_status,output_copy_status").eq("worker_job_id", workerJobId).maybeSingle();
    if (existingError) throw existingError;
    if (existing) {
      if (existing.intent_id !== intentId) throw new CorpusHttpError("Worker job is already linked to a different run intent.", 409);
      return jsonResponse({ corpus_run_id: existing.id, grade_status: existing.grade_status, output_copy_status: existing.output_copy_status, duplicate: true });
    }

    const { data: intent, error: intentError } = await client.from("corpus_run_intents")
      .select("*").eq("id", intentId).maybeSingle();
    if (intentError) throw intentError;
    if (!intent) throw new CorpusHttpError("Run intent was not found.", 404);
    if (intent.registered_at) throw new CorpusHttpError("Run intent is already registered.", 409);
    if (intent.created_by !== user.id) throw new CorpusHttpError("Run intent belongs to another user.", 403);

    const [{ data: experiment, error: experimentError }, { data: image, error: imageError }, { data: job, error: jobError }] = await Promise.all([
      client.from("corpus_experiments").select("*").eq("id", intent.experiment_id).maybeSingle(),
      client.from("corpus_images").select("*").eq("id", intent.corpus_image_id).maybeSingle(),
      client.from("deepclean_jobs").select("*").eq("id", workerJobId).maybeSingle(),
    ]);
    if (experimentError) throw experimentError;
    if (imageError) throw imageError;
    if (jobError) throw jobError;
    if (!experiment || !image || !job) throw new CorpusHttpError("Intent, image, experiment, or job is unavailable.", 404);
    if (job.user_id !== user.id) throw new CorpusHttpError("Worker job belongs to another user.", 403);
    if (job.status !== "completed") throw new CorpusHttpError("Worker job must be completed before registration.", 409);
    if (job.input_sha256 !== image.sha256) throw new CorpusHttpError("Worker input hash does not match the corpus image.", 409);
    if (!job.engine_version || job.engine_version !== experiment.engine_release) {
      throw new CorpusHttpError("Worker engine version does not match the experiment release.", 409);
    }
    const outputSha256 = assertSha256(job.output_sha256, "deepclean_jobs.output_sha256");
    const { data: membership, error: membershipError } = await client.from("corpus_set_members")
      .select("corpus_image_id").eq("corpus_set_id", experiment.corpus_set_id)
      .eq("corpus_image_id", image.id).maybeSingle();
    if (membershipError) throw membershipError;
    if (!membership) throw new CorpusHttpError("Image is no longer a member of the experiment corpus set.", 409);

    const { bytes: sourceBytes, error: sourceError } =
      await downloadStorageBytes(client, "deepclean-outputs", job.output_path);
    if (sourceError || !sourceBytes) {
      throw new CorpusHttpError(
        `Delivered output could not be read from storage (${job.output_path}): ${sourceError ?? "empty object"}`,
        409,
      );
    }
    if (sourceBytes.length < 1 || sourceBytes.length > MAX_BYTES) {
      throw new CorpusHttpError("Delivered output size is invalid.", 422);
    }
    const outputHeader = inspectImage(sourceBytes);
    if (await sha256Hex(sourceBytes) !== outputSha256) {
      throw new CorpusHttpError("Delivered output hash does not match the completed job report.", 409);
    }
    const outputPath = canonicalOutputPath(image.sha256, outputSha256, outputHeader.extension);
    const bucket = corpusBucket();
    const { bytes: existingBytes } =
      await downloadStorageBytes(client, bucket, outputPath);
    if (existingBytes) {
      if (await sha256Hex(existingBytes) !== outputSha256) {
        throw new CorpusHttpError("Existing content-addressed output failed integrity verification.", 409);
      }
    } else {
      const { error: uploadError } = await client.storage.from(bucket).upload(outputPath, sourceBytes, {
        contentType: outputHeader.contentType,
        cacheControl: "31536000",
        upsert: false,
      });
      if (uploadError && !/already exists|duplicate/i.test(uploadError.message)) {
        throw new CorpusHttpError(
          `Corpus output upload failed (${outputPath}): ${uploadError.message}`,
          500,
        );
      }
      if (!uploadError) {
        cleanupCopiedOutput = async () => {
          const { data: reference } = await client.from("corpus_runs").select("id")
            .eq("output_storage_path", outputPath).limit(1).maybeSingle();
          if (!reference) await client.storage.from(bucket).remove([outputPath]);
        };
      }
    }

    const report = job.report && typeof job.report === "object" ? job.report as Record<string, unknown> : {};
    const engine = report.engine && typeof report.engine === "object" ? report.engine as Record<string, unknown> : {};
    const executedSettings = engine.settings && typeof engine.settings === "object" ? engine.settings : {};
    const [executedSha, reportSha, grades] = await Promise.all([
      sha256Hex(canonicalJson(executedSettings)),
      sha256Hex(canonicalJson(report)),
      cachedGradePair(client, {
        ogSha256: image.sha256,
        outputSha256,
        vendor: experiment.detector_vendor,
        mode: experiment.detector_mode,
      }),
    ]);
    const payload = {
      intent_id: intent.id,
      experiment_id: intent.experiment_id,
      corpus_image_id: intent.corpus_image_id,
      config_label: intent.config_label,
      config_key: intent.config_key,
      requested_settings_code: intent.requested_settings_code,
      requested_settings_canonical: intent.requested_settings_canonical,
      requested_settings_sha256: intent.requested_settings_sha256,
      executed_settings_snapshot: executedSettings,
      executed_settings_sha256: executedSha,
      worker_report_snapshot: report,
      worker_report_sha256: reportSha,
      worker_job_id: job.id,
      actual_engine_version: job.engine_version,
      runtime_ms: job.runtime_ms,
      output_sha256: outputSha256,
      output_storage_path: outputPath,
      output_byte_size: sourceBytes.length,
      output_copy_status: "COPIED",
      grade_status: grades.gradeStatus,
      og_grade: grades.ogGrade,
      remint_grade: grades.remintGrade,
      delta: grades.delta,
      swap_index: grades.swapIndex,
      retention_index: grades.retentionIndex,
      qa_flag: grades.qaFlag,
      created_by: user.id,
    };
    const { data: run, error: runError } = await client.rpc("register_corpus_run", {
      p_payload: payload,
      p_max_outputs: corpusMaxOutputsPerImage(),
      p_storage_byte_limit: corpusStorageByteLimit(),
    });
    if (runError) throw runError;
    const registeredRun = Array.isArray(run) ? run[0] : run;
    if (!registeredRun?.id) throw new Error("Corpus run registration returned no row.");
    if (registeredRun.intent_id !== intentId) {
      throw new CorpusHttpError("Worker job was concurrently linked to a different run intent.", 409);
    }
    cleanupCopiedOutput = null;
    return jsonResponse({
      corpus_run_id: registeredRun.id,
      grade_status: registeredRun.grade_status,
      output_copy_status: registeredRun.output_copy_status,
      duplicate: false,
    });
  } catch (error) {
    if (cleanupCopiedOutput) await cleanupCopiedOutput().catch(() => undefined);
    const response = errorResponse(error);
    return jsonResponse({ error: response.message }, response.status);
  }
});
