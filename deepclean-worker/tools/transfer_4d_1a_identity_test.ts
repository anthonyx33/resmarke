import {
  buildSettingsCode,
  CAM1_PRESET_DEFINITION,
  configIdentity,
  type FrozenPresetId,
  is4d1a,
  is4dCam1,
  isConfig1A,
  isConfig2B,
  isConfig3C,
  isConfigA,
  PRESET_DEFINITIONS,
  presetFromRequested,
  settingsForPreset,
  TRANSFER_4D_1A_PRESET_DEFINITION,
  validate4d1aFlag,
  validate4d1aTuple,
} from "../../supabase/functions/_shared/settingsIdentity.ts";

const FROZEN_IDS: FrozenPresetId[] = [
  "config-a",
  "config-1a",
  "config-2b",
  "config-3c",
];
const FROZEN_GOLDENS = [
  "SEQ-CFA-dtbnbygm5iao",
  "SEQ-1A-3lzgvffda5xf",
  "SEQ-2B-zzz2dudlbywp",
  "SEQ-3C-brgbola74zqg",
];
const CAM1_GOLDENS: Record<string, string> = {
  "lab-ctla1": "SEQ-CAM1-7ltwtryshnga",
  "lab-ctla2": "SEQ-CAM1-w4kwip3no7g4",
};
const TRANSFER_GOLDENS: Record<string, string> = {
  "lab-ctla1": "SEQ-4D1A-kqbl35dztkl4",
  "lab-ctla2": "SEQ-4D1A-p3m5qpiorc7b",
};
const FROZEN_PREDICATES = [isConfigA, isConfig1A, isConfig2B, isConfig3C];

Deno.test("4D-1a round-trips both sealed seed-dependent identities", () => {
  for (const seed of ["lab-ctla1", "lab-ctla2"]) {
    const input = settingsForPreset(TRANSFER_4D_1A_PRESET_DEFINITION);
    input.remint.seed = seed;
    assert(is4d1a(input), `${seed}: transfer predicate failed`);
    assert(!is4dCam1(input), `${seed}: transfer tuple matched CAM-1`);
    assert(
      FROZEN_PREDICATES.every((predicate) => !predicate(input)),
      `${seed}: matched frozen preset`,
    );
    const code = buildSettingsCode(input);
    assert(code === TRANSFER_GOLDENS[seed], `${seed}: ${code}`);
    assert(code.startsWith("SEQ-4D1A-"), `${seed}: marker drift`);
    const identity = configIdentity(input);
    assert(
      identity.label === "CUSTOM" && identity.key === code,
      `${seed}: CUSTOM identity drift`,
    );
    const reconstructed = presetFromRequested(input);
    assert(reconstructed?.id === "4d-1a", `${seed}: reconstruction failed`);
    assert(reconstructed.remint.transfer4d1a === true, `${seed}: flag lost`);
    assert(reconstructed.remint.seed === seed, `${seed}: seed lost`);
    assert(
      buildSettingsCode(settingsForPreset(reconstructed)) === code,
      `${seed}: round-trip code drift`,
    );
  }
});

Deno.test("four frozen and both CAM-1 identity goldens remain byte-identical", () => {
  FROZEN_IDS.forEach((id, index) => {
    assert(
      buildSettingsCode(settingsForPreset(PRESET_DEFINITIONS[id])) ===
        FROZEN_GOLDENS[index],
      id,
    );
  });
  for (const seed of ["lab-ctla1", "lab-ctla2"]) {
    const input = settingsForPreset(CAM1_PRESET_DEFINITION);
    input.remint.seed = seed;
    assert(buildSettingsCode(input) === CAM1_GOLDENS[seed], seed);
  }
});

Deno.test("4D-1a marker requires the exact candidate tuple", () => {
  const exact = settingsForPreset(TRANSFER_4D_1A_PRESET_DEFINITION);
  exact.remint.seed = "lab-ctla1";
  const mutations = [
    { ...exact, remint: { ...exact.remint, transfer4d1a: false } },
    { ...exact, remint: { ...exact.remint, transfer4d1a: undefined } },
    { ...exact, remint: { ...exact.remint, seed: undefined } },
    { ...exact, remint: { ...exact.remint, seed: "lab-other" } },
    { ...exact, remint: { ...exact.remint, opticsPsfScale: 0.5 } },
    { ...exact, remint: { ...exact.remint, washModel: "qwen+zimage" } },
    {
      ...exact,
      remint: { ...exact.remint, jpegQuality: 97, jpegSubsampling: "4:4:4" },
    },
  ];
  for (const input of mutations) {
    assert(!is4d1a(input), "mutated tuple matched transfer predicate");
    assert(
      !buildSettingsCode(input).startsWith("SEQ-4D1A-"),
      "mutated tuple emitted marker",
    );
  }
});

Deno.test("4D-1a request flag and locked tuple fail closed", () => {
  assert(validate4d1aFlag(undefined, false) === false);
  assert(validate4d1aFlag(false, true) === false);
  assert(validate4d1aFlag(true, true) === true);
  for (const invalid of [0, 1, "true", null, undefined, {}, []]) {
    expectThrow(() => validate4d1aFlag(invalid, true));
  }
  validate4d1aTuple(true, "lab-ctla1", 1);
  validate4d1aTuple(true, "lab-ctla2", 1);
  validate4d1aTuple(false, undefined, 0.5);
  expectThrow(() => validate4d1aTuple(true, undefined, 1));
  expectThrow(() => validate4d1aTuple(true, "lab-other", 1));
  expectThrow(() => validate4d1aTuple(true, "lab-ctla1", 0.5));
});

function expectThrow(operation: () => unknown): void {
  try {
    operation();
  } catch {
    return;
  }
  throw new Error("expected strict boundary rejection");
}

function assert(
  condition: unknown,
  message = "Assertion failed",
): asserts condition {
  if (!condition) throw new Error(message);
}
