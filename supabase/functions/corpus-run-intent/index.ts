import { corsHeaders, jsonResponse } from "../_shared/cors.ts";
import {
  assertUuid,
  canonicalJson,
  CorpusHttpError,
  errorResponse,
  jsonObject,
  requireCorpusAdmin,
  sha256Hex,
} from "../_shared/corpus.ts";
import {
  buildSettingsCode,
  configIdentity,
  type SettingsCodeInput,
} from "../_shared/settings_code.ts";

Deno.serve(async (request) => {
  if (request.method === "OPTIONS") return new Response("ok", { headers: corsHeaders });
  if (request.method !== "POST") return jsonResponse({ error: "Method not allowed" }, 405);
  try {
    const { client, user } = await requireCorpusAdmin(request);
    const body = await request.json() as Record<string, unknown>;
    const experimentId = assertUuid(body.experiment_id, "experiment_id");
    const imageId = assertUuid(body.corpus_image_id, "corpus_image_id");
    const canonical = jsonObject(
      body.requested_settings_canonical,
      "requested_settings_canonical",
    ) as unknown as SettingsCodeInput;
    if (canonical.mode !== "sequence" || !canonical.remint || !canonical.finish) {
      throw new CorpusHttpError("requested_settings_canonical must be a sequence settings tuple.", 400);
    }
    const suppliedCode = typeof body.requested_settings_code === "string"
      ? body.requested_settings_code.trim()
      : "";
    const derivedCode = buildSettingsCode(canonical);
    if (!suppliedCode || suppliedCode !== derivedCode) {
      throw new CorpusHttpError("requested_settings_code does not match the canonical settings tuple.", 409);
    }
    const identity = configIdentity(canonical);
    if (body.config_label !== identity.label) {
      throw new CorpusHttpError(`config_label must be ${identity.label} for this settings tuple.`, 409);
    }

    const { data: experiment, error: experimentError } = await client
      .from("corpus_experiments")
      .select("id,corpus_set_id,config_set,archived_at,corpus_sets!inner(locked_at,archived_at)")
      .eq("id", experimentId).maybeSingle();
    if (experimentError) throw experimentError;
    if (!experiment || experiment.archived_at) throw new CorpusHttpError("Experiment was not found or is archived.", 404);
    const set = Array.isArray(experiment.corpus_sets) ? experiment.corpus_sets[0] : experiment.corpus_sets;
    if (!set?.locked_at || set.archived_at) throw new CorpusHttpError("Experiment corpus set is not locked and active.", 409);
    if (!configAllowed(experiment.config_set, identity.label, identity.key)) {
      throw new CorpusHttpError("This config is outside the experiment config set.", 409);
    }
    const { data: member, error: memberError } = await client.from("corpus_set_members")
      .select("corpus_image_id").eq("corpus_set_id", experiment.corpus_set_id)
      .eq("corpus_image_id", imageId).maybeSingle();
    if (memberError) throw memberError;
    if (!member) throw new CorpusHttpError("Image is not a member of the experiment corpus set.", 409);

    const requestedSha = await sha256Hex(canonicalJson(canonical));
    const { data, error } = await client.from("corpus_run_intents").insert({
      experiment_id: experimentId,
      corpus_image_id: imageId,
      config_label: identity.label,
      config_key: identity.key,
      requested_settings_code: derivedCode,
      requested_settings_canonical: canonical,
      requested_settings_sha256: requestedSha,
      created_by: user.id,
    }).select("id,experiment_id,corpus_image_id,config_label,config_key,requested_settings_code,requested_settings_sha256,created_at").single();
    if (error) throw error;
    return jsonResponse({ intent: data, intent_id: data.id });
  } catch (error) {
    const response = errorResponse(error);
    return jsonResponse({ error: response.message }, response.status);
  }
});

function configAllowed(value: unknown, label: string, key: string): boolean {
  if (Array.isArray(value)) return value.includes(label) || value.includes(key);
  if (value && typeof value === "object") {
    const record = value as Record<string, unknown>;
    return Boolean(record[label] ?? record[key]);
  }
  return false;
}
