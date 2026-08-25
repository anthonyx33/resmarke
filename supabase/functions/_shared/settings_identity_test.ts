import {
  PRESET_DEFINITIONS,
  buildSettingsCode,
  configIdentity,
  isConfig1A,
  isConfig2B,
  isConfig3C,
  isConfigA,
  presetFromRequested,
  settingsForPreset,
  type PresetId,
  type SettingsCodeInput,
} from "./settingsIdentity.ts";

const IDS: PresetId[] = ["config-a", "config-1a", "config-2b", "config-3c"];
const PREDICATES = [isConfigA, isConfig1A, isConfig2B, isConfig3C];
const GOLDENS = [
  "SEQ-CFA-dtbnbygm5iao",
  "SEQ-1A-3lzgvffda5xf",
  "SEQ-2B-zzz2dudlbywp",
  "SEQ-3C-brgbola74zqg",
];

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
  ];
  negatives.forEach((input, index) => {
    assert(PREDICATES.every((predicate) => !predicate(input)), `negative ${index} matched`);
    assert(configIdentity(input).label === "CUSTOM", `negative ${index} was not custom`);
  });
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

function mutate(input: SettingsCodeInput, remint: Partial<SettingsCodeInput["remint"]>): SettingsCodeInput {
  return { ...input, remint: { ...input.remint, ...remint } };
}

function assert(condition: unknown, message = "Assertion failed"): asserts condition {
  if (!condition) throw new Error(message);
}
