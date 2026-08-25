import { corsHeaders, jsonResponse } from "../_shared/cors.ts";
import {
  assertUuid,
  corpusBucket,
  CorpusHttpError,
  errorResponse,
  jsonObject,
  requireCorpusAdmin,
} from "../_shared/corpus.ts";

type ManageBody = { action?: unknown } & Record<string, unknown>;

Deno.serve(async (request) => {
  if (request.method === "OPTIONS") return new Response("ok", { headers: corsHeaders });
  if (request.method !== "POST") return jsonResponse({ error: "Method not allowed" }, 405);
  try {
    const { client, user } = await requireCorpusAdmin(request);
    const body = await request.json() as ManageBody;
    if (body.action === "create_set") {
      const name = requiredText(body.name, "name", 120);
      const version = positiveInteger(body.version, "version");
      const { data, error } = await client.from("corpus_sets").insert({
        name,
        version,
        created_by: user.id,
      }).select("*").single();
      if (error) throw error;
      return jsonResponse({ corpus_set: data });
    }
    if (body.action === "add_member") {
      const setId = assertUuid(body.corpus_set_id, "corpus_set_id");
      const imageId = assertUuid(body.corpus_image_id, "corpus_image_id");
      const position = positiveInteger(body.position, "position");
      const { data: existing, error: existingError } = await client.from("corpus_set_members")
        .select("*").eq("corpus_set_id", setId).eq("corpus_image_id", imageId).maybeSingle();
      if (existingError) throw existingError;
      if (existing) return jsonResponse({ member: existing, duplicate: true });
      const { data, error } = await client.from("corpus_set_members").insert({
        corpus_set_id: setId,
        corpus_image_id: imageId,
        position,
      }).select("*").single();
      if (error) throw error;
      return jsonResponse({ member: data, duplicate: false });
    }
    if (body.action === "remove_member") {
      const setId = assertUuid(body.corpus_set_id, "corpus_set_id");
      const imageId = assertUuid(body.corpus_image_id, "corpus_image_id");
      const { error } = await client.from("corpus_set_members").delete()
        .eq("corpus_set_id", setId).eq("corpus_image_id", imageId);
      if (error) throw error;
      return jsonResponse({ removed: true });
    }
    if (body.action === "lock_set") {
      const setId = assertUuid(body.corpus_set_id, "corpus_set_id");
      const { data, error } = await client.rpc("lock_corpus_set", { p_set_id: setId });
      if (error) throw error;
      return jsonResponse({ corpus_set: Array.isArray(data) ? data[0] : data });
    }
    if (body.action === "create_experiment") {
      const setId = assertUuid(body.corpus_set_id, "corpus_set_id");
      const engineRelease = requiredText(body.engine_release, "engine_release", 300);
      const detectorVendor = optionalText(body.detector_vendor, 80) ?? "g1";
      const detectorMode = body.detector_mode ?? "real";
      if (!["sdxl", "flux_schnell", "real"].includes(String(detectorMode))) {
        throw new CorpusHttpError("detector_mode is invalid.", 400);
      }
      const configSet = body.config_set ?? ["A", "1A", "2B"];
      if (!Array.isArray(configSet) && (!configSet || typeof configSet !== "object")) {
        throw new CorpusHttpError("config_set must be an array or object.", 400);
      }
      const { data, error } = await client.from("corpus_experiments").insert({
        corpus_set_id: setId,
        engine_release: engineRelease,
        detector_vendor: detectorVendor,
        detector_mode: detectorMode,
        detector_model: optionalText(body.detector_model, 160),
        detector_version: optionalText(body.detector_version, 160),
        config_set: configSet,
        notes: optionalText(body.notes, 2_000),
        created_by: user.id,
      }).select("*").single();
      if (error) throw error;
      return jsonResponse({ experiment: data });
    }
    if (body.action === "archive") {
      const entity = String(body.entity ?? "");
      const id = assertUuid(body.id, "id");
      const table = ({ image: "corpus_images", set: "corpus_sets", experiment: "corpus_experiments" } as const)[entity as "image" | "set" | "experiment"];
      if (!table) throw new CorpusHttpError("entity must be image, set, or experiment.", 400);
      if (entity === "image") {
        const { data: memberships, error: membershipError } = await client.from("corpus_set_members")
          .select("corpus_set_id").eq("corpus_image_id", id);
        if (membershipError) throw membershipError;
        const setIds = (memberships ?? []).map((member) => member.corpus_set_id);
        if (setIds.length) {
          const { data: activeSets, error: activeSetsError } = await client.from("corpus_sets")
            .select("id").in("id", setIds).is("archived_at", null).limit(1);
          if (activeSetsError) throw activeSetsError;
          if (activeSets?.length) throw new CorpusHttpError("Remove the image from draft sets or archive its locked set before archiving the image.", 409);
        }
      }
      if (entity === "set") {
        const { data: activeExperiments, error: activeExperimentsError } = await client.from("corpus_experiments")
          .select("id").eq("corpus_set_id", id).is("archived_at", null).limit(1);
        if (activeExperimentsError) throw activeExperimentsError;
        if (activeExperiments?.length) throw new CorpusHttpError("Archive active experiments before archiving their corpus set.", 409);
      }
      const { data, error } = await client.from(table).update({ archived_at: new Date().toISOString() })
        .eq("id", id).is("archived_at", null).select("id,archived_at").maybeSingle();
      if (error) throw error;
      return jsonResponse({ archived: Boolean(data), record: data });
    }
    if (body.action === "hard_delete") {
      const entity = String(body.entity ?? "");
      const id = assertUuid(body.id, "id");
      const fn = ({ image: "hard_delete_corpus_image", set: "hard_delete_corpus_set", experiment: "hard_delete_corpus_experiment" } as const)[entity as "image" | "set" | "experiment"];
      if (!fn) throw new CorpusHttpError("entity must be image, set, or experiment.", 400);
      const { data: imageRecord, error: imageRecordError } = entity === "image"
        ? await client.from("corpus_images").select("storage_path").eq("id", id).maybeSingle()
        : { data: null, error: null };
      if (imageRecordError) throw imageRecordError;
      const { error } = await client.rpc(fn, { p_id: id });
      if (error) throw error;
      if (imageRecord?.storage_path) {
        const { error: storageError } = await client.storage.from(corpusBucket()).remove([imageRecord.storage_path]);
        if (storageError) throw storageError;
      }
      return jsonResponse({ deleted: true });
    }
    if (body.action === "validate_config") {
      return jsonResponse({ config: jsonObject(body.config, "config") });
    }
    throw new CorpusHttpError("Unknown corpus management action.", 400);
  } catch (error) {
    const response = errorResponse(error);
    return jsonResponse({ error: response.message }, response.status);
  }
});

function requiredText(value: unknown, field: string, max: number): string {
  if (typeof value !== "string" || !value.trim()) throw new CorpusHttpError(`${field} is required.`, 400);
  return value.trim().slice(0, max);
}

function optionalText(value: unknown, max: number): string | null {
  return typeof value === "string" && value.trim() ? value.trim().slice(0, max) : null;
}

function positiveInteger(value: unknown, field: string): number {
  const parsed = Number(value);
  if (!Number.isInteger(parsed) || parsed < 1) throw new CorpusHttpError(`${field} must be a positive integer.`, 400);
  return parsed;
}
