import { assertEquals, assertThrows } from "jsr:@std/assert@1";
import { parseHiveResponse } from "./hive.ts";

Deno.test("parses the verified Hive V3 detector response", () => {
  const raw = {
    task_id: "redacted-fixture-id",
    model: "hive/ai-generated-and-deepfake-content-detection",
    version: "1",
    output: [{
      classes: [
        { class: "not_ai_generated", value: 0.1 },
        { class: "ai_generated", value: 0.9 },
        { class: "stablediffusionxl", value: 0.8 },
        { class: "flux", value: 0.15 },
        { class: "none", value: 0.05 },
        { class: "deepfake", value: 0.02 },
        { class: "not_ai_generated_audio", value: 1 },
        { class: "ai_generated_audio", value: 0 },
      ],
    }],
  };

  const parsed = parseHiveResponse(raw);
  assertEquals(parsed.aiProbability, 0.9);
  assertEquals(parsed.deepfakeProbability, 0.02);
  assertEquals(parsed.sources, {
    stablediffusionxl: 0.8,
    flux: 0.15,
  });
  assertEquals(parsed.raw, raw);
});

Deno.test("rejects responses without the required probability heads", () => {
  assertThrows(
    () => parseHiveResponse({ output: [{ classes: [] }] }),
    Error,
    "missing ai_generated",
  );
});

Deno.test("rejects out-of-range Hive values", () => {
  assertThrows(
    () =>
      parseHiveResponse({
        output: [{
          classes: [
            { class: "ai_generated", value: 1.1 },
            { class: "deepfake", value: 0 },
          ],
        }],
      }),
    Error,
    "invalid class name or value",
  );
});
