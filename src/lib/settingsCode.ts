/**
 * Settings-code filename system.
 *
 * The exported filename ENCODES the exact settings that produced the image:
 * a minimal human prefix (mode, preset, scale, wall toggle) plus a dense
 * 12-char hash of the canonical options JSON carrying EVERY config field.
 * Share the filename back and the exact configuration can be reconstructed /
 * matched for a full settings -> performance feedback loop.
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
    finishMode?: string;
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

/** Dense deterministic hash of the canonical settings JSON: FNV-1a and FNV-1
 * run in parallel (64-bit-ish) and are merged into up to 16 base32 chars.
 * Every config field participates via the canonical JSON, so two exports with
 * different settings cannot share a hash in practice. */
export function settingsShortHash(text: string, chars = 12): string {
  let a = 0x811c9dc5;
  let b = 0x811c9dc5;
  for (let i = 0; i < text.length; i += 1) {
    const c = text.charCodeAt(i);
    a ^= c;
    a = Math.imul(a, 0x01000193);
    b = Math.imul(b, 0x01000193);
    b ^= c;
  }
  a >>>= 0;
  b >>>= 0;
  let out = "";
  for (let i = 0; i < chars; i += 1) {
    if (i % 2 === 0) {
      out += B32[a % 32];
      a = (a >>> 5) + 0x9e3779b9;
    } else {
      out += B32[b % 32];
      b = (b >>> 5) + 0x85ebca6b;
    }
  }
  return out;
}

export function buildSettingsCode(input: SettingsCodeInput): string {
  const m = { sequence: "SEQ", remint: "REM", finish: "QF" }[input.mode] ?? "SEQ";
  const p =
    { conservative: "CON", standard: "STD", strong: "STR", fidelity: "FID" }[
      input.finish.preset ?? "standard"
    ] ?? "STD";
  const scale = input.finish.scale == null ? "N" : String(input.finish.scale);
  const wall = input.finish.materialClean === false ? "M0" : "M1";
  // Minimal human prefix (mode, preset, scale, wall toggle); the dense hash
  // carries EVERY config field via the canonical JSON.
  const readable = `${m}-${p}-${scale}-${wall}`;
  return `${readable}-${settingsShortHash(canonicalJson(input), 12)}`;
}
