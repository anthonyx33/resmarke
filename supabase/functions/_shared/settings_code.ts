import { canonicalJson } from "./corpus.ts";

export type SettingsCodeInput = {
  mode: "sequence" | "remint" | "finish";
  remint: {
    washModel?: string;
    strength?: string;
    engineMode?: string;
    jpegQuality?: number;
    jpegSubsampling?: string;
    iphoneExif?: boolean;
    metadataMode?: string;
  };
  finish: {
    preset?: string;
    scale?: number | null;
    finishMode?: string;
    overrides?: { dither?: number; smoothness?: number; sharpen?: number };
    materialClean?: boolean;
  };
};

const B32 = "abcdefghijklmnopqrstuvwxyz234567";

export function buildSettingsCode(input: SettingsCodeInput): string {
  const marker = { sequence: "SEQ", remint: "REM", finish: "QF" }[input.mode];
  const hash = settingsShortHash(canonicalJson(input), 12);
  if (isConfigA(input)) return `${marker}-CFA-${hash}`;
  if (isConfig1A(input)) return `${marker}-1A-${hash}`;
  if (isConfig2B(input)) return `${marker}-2B-${hash}`;
  const preset = ({ conservative: "CON", standard: "STD", strong: "STR", fidelity: "FID" } as Record<string, string>)[input.finish.preset ?? "standard"] ?? "STD";
  const scale = input.finish.scale == null ? "N" : String(input.finish.scale);
  const wall = input.finish.materialClean === false ? "M0" : "M1";
  return `${marker}-${preset}-${scale}-${wall}-${hash}`;
}

export function configIdentity(input: SettingsCodeInput): { label: "A" | "1A" | "2B" | "CUSTOM"; key: string } {
  if (isConfigA(input)) return { label: "A", key: "A" };
  if (isConfig1A(input)) return { label: "1A", key: "1A" };
  if (isConfig2B(input)) return { label: "2B", key: "2B" };
  return { label: "CUSTOM", key: buildSettingsCode(input) };
}

function settingsShortHash(text: string, chars: number): string {
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

function isConfigA(input: SettingsCodeInput): boolean {
  const remint = input.remint;
  const finish = input.finish;
  const overrides = finish.overrides ?? {};
  return input.mode === "sequence" && remint.washModel === "qwen" &&
    remint.strength === "deep" && remint.engineMode === "adaptive" &&
    (remint.jpegQuality === undefined || remint.jpegQuality === 92) &&
    (remint.jpegSubsampling === undefined || remint.jpegSubsampling === "4:2:0") &&
    finish.preset === "strong" && finish.scale == null && finish.finishMode === "adaptive" &&
    finish.materialClean !== false && near(overrides.dither, 1) &&
    near(overrides.smoothness, 1.25) && near(overrides.sharpen, 1);
}

function isConfig1A(input: SettingsCodeInput): boolean {
  const remint = input.remint;
  const finish = input.finish;
  const overrides = finish.overrides ?? {};
  return input.mode === "sequence" && remint.washModel === "qwen+zimage" &&
    remint.strength === "deep" && remint.engineMode === "adaptive" &&
    finish.preset === "strong" && finish.scale == null && finish.finishMode === "adaptive" &&
    finish.materialClean !== false && near(overrides.dither, 1) &&
    near(overrides.smoothness, 1.25) && near(overrides.sharpen, 1);
}

function isConfig2B(input: SettingsCodeInput): boolean {
  const remint = input.remint;
  const finish = input.finish;
  const overrides = finish.overrides ?? {};
  return input.mode === "sequence" && remint.washModel === "qwen" &&
    remint.strength === "deep" && remint.engineMode === "adaptive" &&
    remint.jpegQuality === 97 && remint.jpegSubsampling === "4:4:4" &&
    finish.preset === "strong" && finish.scale == null && finish.finishMode === "adaptive" &&
    finish.materialClean !== false && near(overrides.dither, 1) &&
    near(overrides.smoothness, 1.25) && near(overrides.sharpen, 1);
}

function near(value: number | undefined, target: number): boolean {
  return typeof value === "number" && Math.abs(value - target) < 1e-6;
}
