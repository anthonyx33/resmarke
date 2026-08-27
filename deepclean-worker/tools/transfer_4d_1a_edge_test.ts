const edgeUrl = new URL(
  "../../supabase/functions/create-deepclean-job/index.ts",
  import.meta.url,
);

Deno.test("4D-1a edge boundary validates before durable mutation", async () => {
  const source = await Deno.readTextFile(edgeUrl);
  const dispatchCall = source.indexOf(
    "? dsRemintV8_9ExpertRefinement(body.ds_remint_v8_9)",
  );
  const normalizeCall = source.indexOf("const transfer4d1a = validate4d1aFlag");
  const tupleCall = source.indexOf(
    "validate4d1aTuple(transfer4d1a, raw.seed, opticsPsfScale)",
  );
  const creditWrite = source.indexOf(
    "deepclean_credits: profile.deepclean_credits - 1",
  );
  const ledgerWrite = source.indexOf('.from("credit_ledger").insert');
  const jobWrite = source.indexOf('.from("deepclean_jobs").insert');
  assert(
    normalizeCall >= 0 && tupleCall > normalizeCall,
    "strict flag/tuple validation is missing",
  );
  assert(dispatchCall >= 0, "V8.9 normalizer dispatch is missing");
  for (
    const [name, position] of Object.entries({
      creditWrite,
      ledgerWrite,
      jobWrite,
    })
  ) {
    assert(position > dispatchCall, `${name} occurs before 4D-1a rejection`);
  }
});

Deno.test("4D-1a edge boundary rejects unknown V8.9 keys", async () => {
  const source = await Deno.readTextFile(edgeUrl);
  assert(
    source.includes(
      'assertOnlyKnownKeys(raw, DS_REMINT_V8_9_KEYS, "DS ReMint V8.9")',
    ),
  );
  assert(source.includes('"4d1a",'));
  assert(source.includes("const unknown = Object.keys(value).filter"));
  assert(source.includes("contains unknown setting(s)"));
});

Deno.test("4D-1a flag is serialized into standalone and HD worker payloads", async () => {
  const source = await Deno.readTextFile(
    new URL("../../src/lib/deepcleanClient.ts", import.meta.url),
  );
  const occurrences = source.match(/"4d1a": params\./g) ?? [];
  assert(
    occurrences.length === 2,
    `expected two serialized paths, got ${occurrences.length}`,
  );
  assert(source.includes('"4d1a": params.dsRemintV89.transfer4d1a'));
  assert(source.includes('"4d1a": params.dsRemintV89Hd.remint.transfer4d1a'));
});

function assert(
  condition: unknown,
  message = "Assertion failed",
): asserts condition {
  if (!condition) throw new Error(message);
}
