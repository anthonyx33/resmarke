import {
  CAM1_PRESET_DEFINITION,
  PRESET_DEFINITIONS,
  REMINT_1_01_PRESET_DEFINITION,
  buildSettingsCode,
  canonicalJson,
  configIdentity,
  is4dCam1,
  isConfig1A,
  isConfig2B,
  isConfig3C,
  isConfigA,
  isRemint1_01,
  presetFromRequested,
  settingsForPreset,
  validateOpticsPsfScale,
  type FrozenPresetId,
  type SettingsCodeInput,
} from "./settingsIdentity.ts";

const IDS: FrozenPresetId[] = ["config-a", "config-1a", "config-2b", "config-3c"];
const PREDICATES = [isConfigA, isConfig1A, isConfig2B, isConfig3C];
const GOLDENS = [
  "SEQ-CFA-dtbnbygm5iao",
  "SEQ-1A-3lzgvffda5xf",
  "SEQ-2B-zzz2dudlbywp",
  "SEQ-3C-brgbola74zqg",
];
const CAM1_GOLDENS: Record<string, string> = {
  "lab-ctla1": "SEQ-CAM1-7ltwtryshnga",
  "lab-ctla2": "SEQ-CAM1-w4kwip3no7g4",
};
const REMINT_1_01_GOLDEN = "SEQ-1.01-sywgbtfbjwhg";
const REMINT_1_01_SEEDED_GOLDENS: Record<string, string> = {
  "lab-ctla1": "SEQ-1.01-yg63qja3got4",
  "lab-ctla2": "SEQ-1.01-vzz7jbtvmvly",
};

Deno.test("identity predicates are exclusive over every frozen tuple", () => {
  IDS.forEach((id, expectedIndex) => {
    const input = settingsForPreset(PRESET_DEFINITIONS[id]);
    const matches = PREDICATES.map((predicate) => predicate(input));
    matches.forEach((matched, index) => {
      assert(matched === (index === expectedIndex), `${id}: predicate ${index}=${matched}`);
    });
  });
});

Deno.test("negative codec and wash tuples emit no frozen identity", () => {
  const base = settingsForPreset(PRESET_DEFINITIONS["config-a"]);
  const negatives: SettingsCodeInput[] = [
    mutate(base, { jpegSubsampling: "4:4:4" }),
    mutate(base, { washModel: "zimage" }),
    mutate(settingsForPreset(PRESET_DEFINITIONS["config-2b"]), { jpegQuality: undefined }),
    mutate(settingsForPreset(PRESET_DEFINITIONS["config-2b"]), { jpegSubsampling: undefined }),
    mutate(base, { jpegQuality: 95, jpegSubsampling: "4:2:2" }),
    mutate(base, { outputTarget: 1799 }),
  ];
  negatives.forEach((input, index) => {
    assert(PREDICATES.every((predicate) => !predicate(input)), `negative ${index} matched`);
    assert(configIdentity(input).label === "CUSTOM", `negative ${index} was not custom`);
  });
});

Deno.test("ReMint 1.01 is exact, exclusive, reconstructable, and marked 1.01", () => {
  const input = settingsForPreset(REMINT_1_01_PRESET_DEFINITION);
  assert(isRemint1_01(input), "1.01 predicate rejected its sealed tuple");
  assert(PREDICATES.every((predicate) => !predicate(input)), "1.01 matched a frozen config");
  const code = buildSettingsCode(input);
  assert(code.startsWith("SEQ-1.01-"), `incorrect 1.01 marker: ${code}`);
  assert(code === REMINT_1_01_GOLDEN, `1.01 golden drifted: ${code}`);
  assert(configIdentity(input).label === "CUSTOM", "1.01 must use the existing CUSTOM ledger label");
  assert(configIdentity(input).key === code, "1.01 custom key drifted");
  const reconstructed = presetFromRequested(input);
  assert(reconstructed?.id === "remint-1-01", "1.01 reconstruction failed");
  assert(reconstructed.remint.outputTarget === 1800, "1.01 delivery target was lost");
  assert(buildSettingsCode(settingsForPreset(reconstructed)) === code, "1.01 code drifted");
  for (const [seed, golden] of Object.entries(REMINT_1_01_SEEDED_GOLDENS)) {
    const seeded = settingsForPreset(REMINT_1_01_PRESET_DEFINITION);
    seeded.remint.seed = seed;
    assert(buildSettingsCode(seeded) === golden, `${seed}: 1.01 seeded golden drifted`);
  }
  const configA = settingsForPreset(PRESET_DEFINITIONS["config-a"]);
  const withoutDelivery = { ...input, remint: { ...input.remint } };
  delete withoutDelivery.remint.outputTarget;
  assert(
    canonicalJson(withoutDelivery) === canonicalJson(configA),
    "1.01 moved a setting other than outputTarget",
  );

  for (const outputTarget of [undefined, 1250, 1799, 1800, 1801, 2000]) {
    const candidate = mutate(input, { outputTarget });
    assert(isRemint1_01(candidate) === (outputTarget === 1800), `target ${outputTarget} matched`);
  }
});

Deno.test("full settings-code goldens and markers are byte-for-byte stable", () => {
  IDS.forEach((id, index) => {
    const input = settingsForPreset(PRESET_DEFINITIONS[id]);
    const actual = buildSettingsCode(input);
    assert(actual === GOLDENS[index], `${id}: ${actual} !== ${GOLDENS[index]}`);
    const marker = index === 0 ? "CFA" : ["", "1A", "2B", "3C"][index];
    assert(actual.startsWith(`SEQ-${marker}-`), `${id}: incorrect marker ${actual}`);
  });
});

Deno.test("preset reconstruction round-trips all presets with seed absent and present", () => {
  IDS.forEach((id) => {
    for (const seed of [undefined, "lab-paired1"]) {
      const input = settingsForPreset(PRESET_DEFINITIONS[id]);
      if (seed !== undefined) input.remint.seed = seed;
      const reconstructed = presetFromRequested(input);
      assert(reconstructed?.id === id, `${id}/${seed ?? "absent"}: reconstruction failed`);
      assert(reconstructed?.remint.seed === seed, `${id}/${seed ?? "absent"}: seed drift`);
      assert(buildSettingsCode(settingsForPreset(reconstructed)) === buildSettingsCode(input));

      const ledgerShape = {
        profile: "ds-remint-v8.9-hd",
        remint: input.remint,
        finish: { ...input.finish, finishMode: undefined },
        finish_mode: input.finish.finishMode,
      };
      assert(presetFromRequested(ledgerShape)?.id === id, `${id}: ledger round-trip failed`);
    }
  });
});

Deno.test("4D-CAM-1 is an exact CUSTOM identity and round-trips both locked seeds", () => {
  for (const seed of ["lab-ctla1", "lab-ctla2"]) {
    const input = settingsForPreset(CAM1_PRESET_DEFINITION);
    input.remint.seed = seed;
    assert(is4dCam1(input), `${seed}: CAM-1 predicate failed`);
    assert(PREDICATES.every((predicate) => !predicate(input)), `${seed}: matched a frozen config`);
    const code = buildSettingsCode(input);
    assert(code.startsWith("SEQ-CAM1-"), `${seed}: incorrect marker ${code}`);
    assert(code === CAM1_GOLDENS[seed], `${seed}: ${code} !== ${CAM1_GOLDENS[seed]}`);
    const identity = configIdentity(input);
    assert(identity.label === "CUSTOM", `${seed}: candidate was not CUSTOM`);
    assert(identity.key === code, `${seed}: CUSTOM key drifted`);
    const reconstructed = presetFromRequested(input);
    assert(reconstructed?.id === "4d-cam-1", `${seed}: reconstruction failed`);
    assert(reconstructed.remint.opticsPsfScale === 0.5, `${seed}: scale was lost`);
    assert(reconstructed.remint.seed === seed, `${seed}: seed was lost`);
    assert(buildSettingsCode(settingsForPreset(reconstructed)) === code, `${seed}: code drifted`);
  }
});

Deno.test("absent and explicit 1.00 are baseline-only while the incumbent golden stays absent", () => {
  const absent = settingsForPreset(PRESET_DEFINITIONS["config-a"]);
  const explicit = mutate(absent, { opticsPsfScale: 1 });
  assert(isConfigA(absent) && isConfigA(explicit), "baseline predicate rejected an authorized form");
  assert(!is4dCam1(absent) && !is4dCam1(explicit), "baseline matched CAM-1");
  assert(buildSettingsCode(absent) === GOLDENS[0], "absent baseline golden changed");
  assert(buildSettingsCode(explicit) !== GOLDENS[0], "explicit scale unexpectedly reused incumbent code");
  assert(PRESET_DEFINITIONS["config-a"].remint.opticsPsfScale === undefined, "Config A must omit scale");
});

Deno.test("optics PSF request boundary accepts only absent, 1.00, or 0.50", () => {
  assert(validateOpticsPsfScale(undefined, false) === 1, "absence did not default to 1.00");
  assert(validateOpticsPsfScale(1, true) === 1, "explicit 1.00 rejected");
  assert(validateOpticsPsfScale(0.5, true) === 0.5, "candidate 0.50 rejected");
  for (const invalid of [0.49, 0.6, 0.75, NaN, Infinity, -Infinity, "0.50", null, undefined]) {
    let rejected = false;
    try {
      validateOpticsPsfScale(invalid, true);
    } catch {
      rejected = true;
    }
    assert(rejected, `invalid boundary value was accepted: ${String(invalid)}`);
  }
});

function mutate(input: SettingsCodeInput, remint: Partial<SettingsCodeInput["remint"]>): SettingsCodeInput {
  return { ...input, remint: { ...input.remint, ...remint } };
}

function assert(condition: unknown, message = "Assertion failed"): asserts condition {
  if (!condition) throw new Error(message);
}
