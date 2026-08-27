/**
 * Canonical, dependency-free settings identity for client and edge runtimes.
 * Detection predicates intentionally ignore iphoneExif and metadataMode while
 * canonical hashing includes every supplied field, including a lab seed.
 */

export type SettingsCodeMode = "sequence" | "remint" | "finish";
export type ConfigLabel = "A" | "1A" | "2B" | "3C" | "CUSTOM";
export type FrozenPresetId = "config-a" | "config-1a" | "config-2b" | "config-3c";
export type PresetId = FrozenPresetId | "4d-cam-1" | "4d-1a";
export type OpticsPsfScale = 0.5 | 1;

export class SettingsValidationError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "SettingsValidationError";
  }
}

export interface RemintSettings {
  washModel?: string;
  strength?: string;
  engineMode?: string;
  jpegQuality?: number;
  jpegSubsampling?: string;
  iphoneExif?: boolean;
  metadataMode?: string;
  seed?: string;
  opticsPsfScale?: number;
  transfer4d1a?: boolean;
}

export interface FinishSettings {
  preset?: string;
  scale?: number | null;
  finishMode?: string;
  overrides?: { dither?: number; smoothness?: number; sharpen?: number };
  materialClean?: boolean;
}

export interface SettingsCodeInput {
  mode: SettingsCodeMode;
  remint: RemintSettings;
  finish: FinishSettings;
}

export interface PresetDefinition {
  id: PresetId;
  label: string;
  detail: string;
  remint: RemintSettings & {
    engineMode: "adaptive";
    washModel: "qwen" | "qwen+zimage";
    strength: "deep";
    iphoneExif: true;
    metadataMode: "device";
    jpegQuality?: 97;
    jpegSubsampling?: "4:4:4";
  };
  finish: Omit<FinishSettings, "finishMode"> & {
    preset: "strong";
    scale: null;
    materialClean: true;
    overrides: { dither: 1; smoothness: 1.25; sharpen: 1 };
  };
  finishMode: "adaptive";
}

const COMMON_FINISH: PresetDefinition["finish"] = {
  preset: "strong",
  scale: null,
  overrides: { dither: 1, smoothness: 1.25, sharpen: 1 },
  materialClean: true,
};

export const PRESET_DEFINITIONS: Record<FrozenPresetId, PresetDefinition> = {
  "config-a": {
    id: "config-a",
    label: "Config A",
    detail: "Qwen · Deep · Strong · Native · S1.25 · Adaptive",
    remint: {
      engineMode: "adaptive",
      washModel: "qwen",
      strength: "deep",
      iphoneExif: true,
      metadataMode: "device",
    },
    finish: cloneFinish(COMMON_FINISH),
    finishMode: "adaptive",
  },
  "config-1a": {
    id: "config-1a",
    label: "Config 1A",
    detail: "Qwen + Z-Image · rest identical to Config A",
    remint: {
      engineMode: "adaptive",
      washModel: "qwen+zimage",
      strength: "deep",
      iphoneExif: true,
      metadataMode: "device",
    },
    finish: cloneFinish(COMMON_FINISH),
    finishMode: "adaptive",
  },
  "config-2b": {
    id: "config-2b",
    label: "Config 2B",
    detail: "Stage-1 Q97 4:4:4 · rest identical to Config A",
    remint: {
      engineMode: "adaptive",
      washModel: "qwen",
      strength: "deep",
      jpegQuality: 97,
      jpegSubsampling: "4:4:4",
      iphoneExif: true,
      metadataMode: "device",
    },
    finish: cloneFinish(COMMON_FINISH),
    finishMode: "adaptive",
  },
  "config-3c": {
    id: "config-3c",
    label: "Config 3C — LAB · Qwen + Z-Image · Stage-1 Q97 4:4:4",
    detail: "Paired-seed laboratory control only",
    remint: {
      engineMode: "adaptive",
      washModel: "qwen+zimage",
      strength: "deep",
      jpegQuality: 97,
      jpegSubsampling: "4:4:4",
      iphoneExif: true,
      metadataMode: "device",
    },
    finish: cloneFinish(COMMON_FINISH),
    finishMode: "adaptive",
  },
};

/** Kept separate so shared consumers still enumerate exactly four frozen configs. */
export const CAM1_PRESET_DEFINITION: PresetDefinition = {
  id: "4d-cam-1",
  label: "4D-CAM-1 — LAB · Gaussian radii ×0.50",
  detail: "Config A with the sealed camera-radius scalar only",
  remint: {
    engineMode: "adaptive",
    washModel: "qwen",
    strength: "deep",
    iphoneExif: true,
    metadataMode: "device",
    opticsPsfScale: 0.5,
  },
  finish: cloneFinish(COMMON_FINISH),
  finishMode: "adaptive",
};

/** Kept separate so shared consumers still enumerate exactly four frozen configs. */
export const TRANSFER_4D_1A_PRESET_DEFINITION: PresetDefinition = {
  id: "4d-1a",
  label: "4D-1A — LAB · H1/H2 source transfer α=0.10",
  detail: "Config A with sealed remint-led H1/H2 source-energy transfer",
  remint: {
    engineMode: "adaptive",
    washModel: "qwen",
    strength: "deep",
    iphoneExif: true,
    metadataMode: "device",
    transfer4d1a: true,
  },
  finish: cloneFinish(COMMON_FINISH),
  finishMode: "adaptive",
};

/** Fail-closed boundary parser shared by the client/edge identity contract. */
export function validateOpticsPsfScale(value: unknown, supplied: boolean): OpticsPsfScale {
  if (!supplied) return 1;
  if (typeof value !== "number" || !Number.isFinite(value) || (value !== 0.5 && value !== 1)) {
    throw new SettingsValidationError("optics_psf_scale must be exactly 0.50 or 1.00 when supplied.");
  }
  return value;
}

/** Strict fail-closed parser for the lab-only 4D-1a request flag. */
export function validate4d1aFlag(value: unknown, supplied: boolean): boolean {
  if (!supplied) return false;
  if (typeof value !== "boolean") {
    throw new SettingsValidationError("4d1a must be a boolean when supplied.");
  }
  return value;
}

/** The candidate is one sealed seed/optics tuple, never a parameter family. */
export function validate4d1aTuple(
  enabled: boolean,
  seed: unknown,
  opticsPsfScale: OpticsPsfScale,
): void {
  if (!enabled) return;
  if (seed !== "lab-ctla1" && seed !== "lab-ctla2") {
    throw new SettingsValidationError("4d1a requires lab-ctla1 or lab-ctla2.");
  }
  if (opticsPsfScale !== 1) {
    throw new SettingsValidationError("4d1a requires incumbent optics_psf_scale 1.00.");
  }
}

/** Stable JSON stringify: sorted keys and no insignificant whitespace. */
export function canonicalJson(value: unknown): string {
  const walk = (item: unknown): unknown => {
    if (item === null || typeof item !== "object") return item;
    if (Array.isArray(item)) return item.map(walk);
    const output: Record<string, unknown> = {};
    for (const key of Object.keys(item as Record<string, unknown>).sort()) {
      output[key] = walk((item as Record<string, unknown>)[key]);
    }
    return output;
  };
  return JSON.stringify(walk(value));
}

const B32 = "abcdefghijklmnopqrstuvwxyz234567";

export function settingsShortHash(text: string, chars = 12): string {
  let a = 0x811c9dc5;
  let b = 0x811c9dc5;
  for (let index = 0; index < text.length; index += 1) {
    const code = text.charCodeAt(index);
    a ^= code;
    a = Math.imul(a, 0x01000193);
    b = Math.imul(b, 0x01000193);
    b ^= code;
  }
  a >>>= 0;
  b >>>= 0;
  let output = "";
  for (let index = 0; index < chars; index += 1) {
    if (index % 2 === 0) {
      output += B32[a % 32];
      a = (a >>> 5) + 0x9e3779b9;
    } else {
      output += B32[b % 32];
      b = (b >>> 5) + 0x85ebca6b;
    }
  }
  return output;
}

export function isConfigA(input: SettingsCodeInput): boolean {
  return commonTuple(input, "qwen") && defaultCodec(input.remint);
}

export function isConfig1A(input: SettingsCodeInput): boolean {
  return commonTuple(input, "qwen+zimage") && defaultCodec(input.remint);
}

export function isConfig2B(input: SettingsCodeInput): boolean {
  return commonTuple(input, "qwen") && q97Codec(input.remint);
}

export function isConfig3C(input: SettingsCodeInput): boolean {
  return commonTuple(input, "qwen+zimage") && q97Codec(input.remint);
}

export function is4dCam1(input: SettingsCodeInput): boolean {
  return commonBaseTuple(input, "qwen") && input.remint.opticsPsfScale === 0.5 &&
    default4d1a(input.remint) && defaultCodec(input.remint);
}

export function is4d1a(input: SettingsCodeInput): boolean {
  return commonBaseTuple(input, "qwen") && defaultOpticsPsfScale(input.remint) &&
    input.remint.transfer4d1a === true && locked4d1aSeed(input.remint.seed) &&
    defaultCodec(input.remint);
}

export function buildSettingsCode(input: SettingsCodeInput): string {
  const marker = { sequence: "SEQ", remint: "REM", finish: "QF" }[input.mode];
  const hash = settingsShortHash(canonicalJson(input), 12);
  if (isConfigA(input)) return `${marker}-CFA-${hash}`;
  if (isConfig1A(input)) return `${marker}-1A-${hash}`;
  if (isConfig2B(input)) return `${marker}-2B-${hash}`;
  if (isConfig3C(input)) return `${marker}-3C-${hash}`;
  if (is4dCam1(input)) return `${marker}-CAM1-${hash}`;
  if (is4d1a(input)) return `${marker}-4D1A-${hash}`;
  const preset = ({ conservative: "CON", standard: "STD", strong: "STR", fidelity: "FID" } as Record<string, string>)[input.finish.preset ?? "standard"] ?? "STD";
  const scale = input.finish.scale == null ? "N" : String(input.finish.scale);
  const wall = input.finish.materialClean === false ? "M0" : "M1";
  return `${marker}-${preset}-${scale}-${wall}-${hash}`;
}

export function configIdentity(input: SettingsCodeInput): { label: ConfigLabel; key: string } {
  if (isConfigA(input)) return { label: "A", key: "A" };
  if (isConfig1A(input)) return { label: "1A", key: "1A" };
  if (isConfig2B(input)) return { label: "2B", key: "2B" };
  if (isConfig3C(input)) return { label: "3C", key: "3C" };
  if (is4dCam1(input)) {
    const key = buildSettingsCode(input);
    return { label: "CUSTOM", key };
  }
  if (is4d1a(input)) {
    const key = buildSettingsCode(input);
    return { label: "CUSTOM", key };
  }
  return { label: "CUSTOM", key: buildSettingsCode(input) };
}

export function settingsForPreset(preset: PresetDefinition): SettingsCodeInput {
  return {
    mode: "sequence",
    remint: { ...preset.remint },
    finish: { ...cloneFinish(preset.finish), finishMode: preset.finishMode },
  };
}

/** Reconstruct one frozen preset or an exact lab-only candidate tuple. */
export function presetFromRequested(value: unknown): PresetDefinition | null {
  const input = requestedToSettings(value);
  if (!input) return null;
  const id = isConfigA(input) ? "config-a"
    : isConfig1A(input) ? "config-1a"
    : isConfig2B(input) ? "config-2b"
    : isConfig3C(input) ? "config-3c"
    : is4dCam1(input) ? "4d-cam-1"
    : is4d1a(input) ? "4d-1a"
    : null;
  if (!id) return null;
  const definition = id === "4d-cam-1"
    ? CAM1_PRESET_DEFINITION
    : id === "4d-1a"
    ? TRANSFER_4D_1A_PRESET_DEFINITION
    : PRESET_DEFINITIONS[id];
  const result = clonePreset(definition);
  const seed = input.remint.seed;
  if (seed !== undefined) result.remint.seed = seed;
  return result;
}

function requestedToSettings(value: unknown): SettingsCodeInput | null {
  if (!isRecord(value) || !isRecord(value.remint) || !isRecord(value.finish)) return null;
  const finish = { ...value.finish } as FinishSettings;
  if (finish.finishMode === undefined && typeof value.finish_mode === "string") {
    finish.finishMode = value.finish_mode;
  }
  return {
    mode: value.mode === "remint" || value.mode === "finish" ? value.mode : "sequence",
    remint: { ...value.remint } as RemintSettings,
    finish,
  };
}

function commonBaseTuple(input: SettingsCodeInput, washModel: string): boolean {
  const remint = input.remint;
  const finish = input.finish;
  const overrides = finish.overrides ?? {};
  return input.mode === "sequence" && remint.washModel === washModel &&
    remint.strength === "deep" && remint.engineMode === "adaptive" &&
    finish.preset === "strong" && finish.scale == null && finish.finishMode === "adaptive" &&
    finish.materialClean !== false && near(overrides.dither, 1) &&
    near(overrides.smoothness, 1.25) && near(overrides.sharpen, 1);
}

function commonTuple(input: SettingsCodeInput, washModel: string): boolean {
  return commonBaseTuple(input, washModel) && defaultOpticsPsfScale(input.remint) &&
    default4d1a(input.remint);
}

function defaultOpticsPsfScale(remint: RemintSettings): boolean {
  return remint.opticsPsfScale === undefined || remint.opticsPsfScale === 1;
}

function default4d1a(remint: RemintSettings): boolean {
  return remint.transfer4d1a === undefined || remint.transfer4d1a === false;
}

function locked4d1aSeed(seed: string | undefined): boolean {
  return seed === "lab-ctla1" || seed === "lab-ctla2";
}

function defaultCodec(remint: RemintSettings): boolean {
  return (remint.jpegQuality === undefined || remint.jpegQuality === 92) &&
    (remint.jpegSubsampling === undefined || remint.jpegSubsampling === "4:2:0");
}

function q97Codec(remint: RemintSettings): boolean {
  return remint.jpegQuality === 97 && remint.jpegSubsampling === "4:4:4";
}

function near(value: number | undefined, target: number): boolean {
  return typeof value === "number" && Math.abs(value - target) < 1e-6;
}

function clonePreset(preset: PresetDefinition): PresetDefinition {
  return {
    ...preset,
    remint: { ...preset.remint },
    finish: cloneFinish(preset.finish),
  };
}

function cloneFinish<T extends Omit<FinishSettings, "finishMode">>(finish: T): T {
  return {
    ...finish,
    overrides: finish.overrides ? { ...finish.overrides } : undefined,
  } as T;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
