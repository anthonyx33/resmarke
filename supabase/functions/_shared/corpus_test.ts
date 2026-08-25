import { inspectImage } from "./corpus_image.ts";
import { buildSettingsCode as buildServerCode, type SettingsCodeInput } from "./settings_code.ts";

const PRESETS: SettingsCodeInput[] = [
  {
    mode: "sequence",
    remint: { engineMode: "adaptive", washModel: "qwen", strength: "deep", iphoneExif: true, metadataMode: "device" },
    finish: { preset: "strong", scale: null, finishMode: "adaptive", overrides: { dither: 1, smoothness: 1.25, sharpen: 1 }, materialClean: true },
  },
  {
    mode: "sequence",
    remint: { engineMode: "adaptive", washModel: "qwen+zimage", strength: "deep", iphoneExif: true, metadataMode: "device" },
    finish: { preset: "strong", scale: null, finishMode: "adaptive", overrides: { dither: 1, smoothness: 1.25, sharpen: 1 }, materialClean: true },
  },
  {
    mode: "sequence",
    remint: { engineMode: "adaptive", washModel: "qwen", strength: "deep", jpegQuality: 97, jpegSubsampling: "4:4:4", iphoneExif: true, metadataMode: "device" },
    finish: { preset: "strong", scale: null, finishMode: "adaptive", overrides: { dither: 1, smoothness: 1.25, sharpen: 1 }, materialClean: true },
  },
];

Deno.test("edge settings-code implementation matches the frozen client contract", () => {
  // Golden values produced by src/lib/settingsCode.ts. A change on either side
  // must update this test deliberately; silent provenance drift is forbidden.
  const expected = [
    "SEQ-CFA-dtbnbygm5iao",
    "SEQ-1A-3lzgvffda5xf",
    "SEQ-2B-zzz2dudlbywp",
  ];
  PRESETS.forEach((preset, index) => {
    const server = buildServerCode(preset);
    assert(server === expected[index], `Server/client settings code contract drift: ${server} !== ${expected[index]}`);
  });
});

Deno.test("image header parser extracts PNG dimensions", () => {
  const bytes = new Uint8Array(24);
  bytes.set([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]);
  bytes.set([0x49, 0x48, 0x44, 0x52], 12);
  new DataView(bytes.buffer).setUint32(16, 1920, false);
  new DataView(bytes.buffer).setUint32(20, 1080, false);
  const header = inspectImage(bytes);
  assert(header.contentType === "image/png" && header.width === 1920 && header.height === 1080);
});

Deno.test("image header parser extracts JPEG dimensions", () => {
  const bytes = new Uint8Array([
    0xff, 0xd8,
    0xff, 0xc0, 0x00, 0x11, 0x08, 0x04, 0x38, 0x07, 0x80,
    0x03, 0x01, 0x11, 0x00, 0x02, 0x11, 0x00, 0x03, 0x11, 0x00,
    0xff, 0xd9,
  ]);
  const header = inspectImage(bytes);
  assert(header.contentType === "image/jpeg" && header.width === 1920 && header.height === 1080);
});

Deno.test("image header parser extracts extended WebP dimensions", () => {
  const bytes = new Uint8Array(30);
  bytes.set(new TextEncoder().encode("RIFF"), 0);
  bytes.set(new TextEncoder().encode("WEBP"), 8);
  bytes.set(new TextEncoder().encode("VP8X"), 12);
  const widthMinusOne = 1919;
  const heightMinusOne = 1079;
  bytes.set([widthMinusOne & 255, (widthMinusOne >>> 8) & 255, (widthMinusOne >>> 16) & 255], 24);
  bytes.set([heightMinusOne & 255, (heightMinusOne >>> 8) & 255, (heightMinusOne >>> 16) & 255], 27);
  const header = inspectImage(bytes);
  assert(header.contentType === "image/webp" && header.width === 1920 && header.height === 1080);
});

function assert(condition: unknown, message = "Assertion failed"): asserts condition {
  if (!condition) throw new Error(message);
}
