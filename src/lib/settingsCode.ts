import { fnv1a32 } from "./hash";

/**
 * Settings-code filename system.
 *
 * The exported filename ENCODES the exact settings that produced the image:
 * a short human-readable field block plus a 4-char hash of the canonical
 * options JSON. Share the filename back and the exact configuration can be
 * reconstructed / matched for a full settings -> performance feedback loop.
 */

export type SettingsCodeMode = "sequence" | "remint" | "finish";

export interface SettingsCodeInput {
  mode: SettingsCodeMode;
  remint: {
    washModel?: string;
    strength?: string;
    engineMode?: string;
  };
  finish: {
    preset?: string;
    scale?: number | null;
    overrides?: { dither?: number; smoothness?: number; sharpen?: number };
    materialClean?: boolean;
  };
}

/** Stable JSON stringify (sorted keys, no whitespace) so identical settings
 * always hash identically regardless of object construction order. */
export function canonicalJson(value: unknown): string {
  const walk = (v: unknown): unknown => {
    if (v === null || typeof v !== "object") return v;
    if (Array.isArray(v)) return v.map(walk);
    const out: Record<string, unknown> = {};
    for (const key of Object.keys(v as Record<string, unknown>).sort()) {
      out[key] = walk((v as Record<string, unknown>)[key]);
    }
    return out;
  };
  return JSON.stringify(walk(value));
}

const B32 = "abcdefghijklmnopqrstuvwxyz234567";

/** Short deterministic hash of the canonical settings JSON. */
export function settingsShortHash(text: string, chars = 4): string {
  let x = fnv1a32(text);
  let out = "";
  for (let i = 0; i < chars; i += 1) {
    out += B32[x % 32];
    x = (x >>> 5) + 0x9e3779b9;
  }
  return out;
}

const pct = (v: unknown): string => {
  const n = typeof v === "number" && Number.isFinite(v) ? v : 1;
  return `${String(Math.round(n * 100)).padStart(3, "0")}`;
};

export function buildSettingsCode(input: SettingsCodeInput): string {
  const m = { sequence: "SEQ", remint: "REM", finish: "QF" }[input.mode] ?? "SEQ";
  const w =
    { qwen: "Q", zimage: "Z", "qwen+zimage": "QZ" }[input.remint.washModel ?? "qwen"] ?? "Q";
  const s = { light: "L", balanced: "B", deep: "D" }[input.remint.strength ?? "balanced"] ?? "B";
  const e = input.remint.engineMode === "template" ? "T" : "A";
  const p =
    { conservative: "CON", standard: "STD", strong: "STR", fidelity: "FID" }[
      input.finish.preset ?? "standard"
    ] ?? "STD";
  const scale = input.finish.scale == null ? "N" : String(input.finish.scale);
  const ov = input.finish.overrides ?? {};
  const readable = `${m}-${w}-${s}-${e}-${p}-${scale}-D${pct(ov.dither ?? 1)}-S${pct(
    ov.smoothness ?? 1
  )}-X${pct(ov.sharpen ?? 1)}-M${input.finish.materialClean === false ? "0" : "1"}`;
  return `${readable}-${settingsShortHash(canonicalJson(input))}`;
}
