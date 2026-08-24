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

/** Exact Config A detector: the proven all-clear tuple (deep + STRONG +
 * smoothing 1.25x, wall ON, native, adaptive routing, defaults elsewhere).
 * Mirrors the WAVL-v1 predicate in the consoles. iphoneExif / metadataMode
 * are deliberately excluded — the Config A button does not set them. */
export function isConfigA(input: SettingsCodeInput): boolean {
  const r = input.remint;
  const f = input.finish;
  const o = f.overrides ?? {};
  const near = (x: number | undefined, target: number) =>
    typeof x === "number" && Math.abs(x - target) < 1e-6;
  return (
    input.mode === "sequence" &&
    r.washModel === "qwen" &&
    r.strength === "deep" &&
    r.engineMode === "adaptive" &&
    f.preset === "strong" &&
    f.scale == null &&
    f.finishMode === "adaptive" &&
    f.materialClean !== false &&
    near(o.dither, 1) &&
    near(o.smoothness, 1.25) &&
    near(o.sharpen, 1)
  );
}

/** Exact Config 1A detector: the V8 cross-wash test tuple — every Config A
 * lever unchanged except the wash model is the Qwen+Z-Image blend, the
 * runtime lever that targets the fingerprint-swap failure on night content.
 * Emits the SEQ-1A marker so test exports are self-describing. */
export function isConfig1A(input: SettingsCodeInput): boolean {
  const r = input.remint;
  const f = input.finish;
  const o = f.overrides ?? {};
  const near = (x: number | undefined, target: number) =>
    typeof x === "number" && Math.abs(x - target) < 1e-6;
  return (
    input.mode === "sequence" &&
    r.washModel === "qwen+zimage" &&
    r.strength === "deep" &&
    r.engineMode === "adaptive" &&
    f.preset === "strong" &&
    f.scale == null &&
    f.finishMode === "adaptive" &&
    f.materialClean !== false &&
    near(o.dither, 1) &&
    near(o.smoothness, 1.25) &&
    near(o.sharpen, 1)
  );
}

export function buildSettingsCode(input: SettingsCodeInput): string {
  const m = { sequence: "SEQ", remint: "REM", finish: "QF" }[input.mode] ?? "SEQ";
  // Exact Config A gets the unmistakable CFA marker — no other setting emits
  // it, so a CFA filename is a guarantee the proven all-clear tuple ran.
  if (isConfigA(input)) {
    return `${m}-CFA-${settingsShortHash(canonicalJson(input), 12)}`;
  }
  // Config 1A gets its own marker — the V8 cross-wash test tuple — so A/B
  // exports against Config A are self-describing.
  if (isConfig1A(input)) {
    return `${m}-1A-${settingsShortHash(canonicalJson(input), 12)}`;
  }
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
