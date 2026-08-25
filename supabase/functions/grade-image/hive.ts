export type HiveProviderResult = {
  aiProbability: number;
  deepfakeProbability: number;
  sources: Record<string, number>;
  raw: Record<string, unknown>;
};

const NON_SOURCE_CLASSES = new Set([
  "ai_generated",
  "not_ai_generated",
  "deepfake",
  "none",
  "inconclusive",
  "ai_generated_audio",
  "not_ai_generated_audio",
]);

export function parseHiveResponse(value: unknown): HiveProviderResult {
  if (!isRecord(value)) throw new Error("Hive returned a non-object response.");
  const output = value.output;
  if (!Array.isArray(output) || !isRecord(output[0])) {
    throw new Error("Hive response is missing output[0].");
  }
  const classes = output[0].classes;
  if (!Array.isArray(classes)) {
    throw new Error("Hive response is missing output[0].classes.");
  }

  const scores = new Map<string, number>();
  for (const item of classes) {
    if (!isRecord(item)) throw new Error("Hive returned an invalid class row.");
    const name = item.class;
    const score = item.value;
    if (
      typeof name !== "string" || !name || typeof score !== "number" ||
      !Number.isFinite(score) || score < 0 || score > 1
    ) {
      throw new Error("Hive returned an invalid class name or value.");
    }
    if (scores.has(name)) {
      throw new Error(`Hive returned duplicate class ${name}.`);
    }
    scores.set(name, score);
  }

  const aiProbability = scores.get("ai_generated");
  const deepfakeProbability = scores.get("deepfake");
  if (aiProbability === undefined) {
    throw new Error("Hive response is missing ai_generated.");
  }
  if (deepfakeProbability === undefined) {
    throw new Error("Hive response is missing deepfake.");
  }

  const sources = Object.fromEntries(
    [...scores.entries()].filter(([name]) => !NON_SOURCE_CLASSES.has(name)),
  );
  if (!Object.keys(sources).length) {
    throw new Error("Hive response does not contain source probabilities.");
  }

  return {
    aiProbability,
    deepfakeProbability,
    sources,
    raw: value,
  };
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
