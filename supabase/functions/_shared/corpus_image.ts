import { CorpusHttpError } from "./corpus.ts";

export type ImageHeader = {
  contentType: "image/jpeg" | "image/png" | "image/webp";
  extension: "jpg" | "png" | "webp";
  width: number;
  height: number;
};

const MAX_DIMENSION = 50_000;
const MAX_PIXELS = 250_000_000;

export function inspectImage(bytes: Uint8Array): ImageHeader {
  let header: ImageHeader | null = null;
  if (isJpeg(bytes)) header = jpegHeader(bytes);
  else if (isPng(bytes)) header = pngHeader(bytes);
  else if (isWebp(bytes)) header = webpHeader(bytes);
  if (!header) throw new CorpusHttpError("Only valid JPEG, PNG, and WebP images are accepted.", 422);
  if (
    header.width < 1 || header.height < 1 ||
    header.width > MAX_DIMENSION || header.height > MAX_DIMENSION ||
    header.width * header.height > MAX_PIXELS
  ) {
    throw new CorpusHttpError("Image dimensions are invalid or exceed the safety limit.", 422);
  }
  return header;
}

export function canonicalOriginalPath(sha256: string, extension: ImageHeader["extension"]): string {
  return `${sha256}/original.${extension}`;
}

export function canonicalOutputPath(
  imageSha256: string,
  outputSha256: string,
  extension: ImageHeader["extension"],
): string {
  return `${imageSha256}/outputs/${outputSha256}.${extension}`;
}

function isJpeg(bytes: Uint8Array): boolean {
  return bytes.length >= 4 && bytes[0] === 0xff && bytes[1] === 0xd8 && bytes[2] === 0xff;
}

function jpegHeader(bytes: Uint8Array): ImageHeader | null {
  const sofMarkers = new Set([0xc0, 0xc1, 0xc2, 0xc3, 0xc5, 0xc6, 0xc7, 0xc9, 0xca, 0xcb, 0xcd, 0xce, 0xcf]);
  let offset = 2;
  while (offset + 8 < bytes.length) {
    if (bytes[offset] !== 0xff) {
      offset += 1;
      continue;
    }
    while (offset < bytes.length && bytes[offset] === 0xff) offset += 1;
    const marker = bytes[offset++];
    if (marker === 0xd8 || marker === 0xd9 || (marker >= 0xd0 && marker <= 0xd7)) continue;
    if (offset + 1 >= bytes.length) break;
    const length = (bytes[offset] << 8) | bytes[offset + 1];
    if (length < 2 || offset + length > bytes.length) break;
    if (sofMarkers.has(marker) && length >= 7) {
      const height = (bytes[offset + 3] << 8) | bytes[offset + 4];
      const width = (bytes[offset + 5] << 8) | bytes[offset + 6];
      return { contentType: "image/jpeg", extension: "jpg", width, height };
    }
    offset += length;
  }
  return null;
}

function isPng(bytes: Uint8Array): boolean {
  const signature = [0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a];
  return bytes.length >= 24 && signature.every((value, index) => bytes[index] === value);
}

function pngHeader(bytes: Uint8Array): ImageHeader | null {
  if (ascii(bytes, 12, 16) !== "IHDR") return null;
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  return {
    contentType: "image/png",
    extension: "png",
    width: view.getUint32(16, false),
    height: view.getUint32(20, false),
  };
}

function isWebp(bytes: Uint8Array): boolean {
  return bytes.length >= 30 && ascii(bytes, 0, 4) === "RIFF" && ascii(bytes, 8, 12) === "WEBP";
}

function webpHeader(bytes: Uint8Array): ImageHeader | null {
  const kind = ascii(bytes, 12, 16);
  if (kind === "VP8X" && bytes.length >= 30) {
    return {
      contentType: "image/webp",
      extension: "webp",
      width: 1 + uint24le(bytes, 24),
      height: 1 + uint24le(bytes, 27),
    };
  }
  if (kind === "VP8L" && bytes.length >= 25 && bytes[20] === 0x2f) {
    const packed = (bytes[21] | (bytes[22] << 8) | (bytes[23] << 16) | (bytes[24] << 24)) >>> 0;
    return {
      contentType: "image/webp",
      extension: "webp",
      width: (packed & 0x3fff) + 1,
      height: ((packed >>> 14) & 0x3fff) + 1,
    };
  }
  if (
    kind === "VP8 " && bytes.length >= 30 &&
    bytes[23] === 0x9d && bytes[24] === 0x01 && bytes[25] === 0x2a
  ) {
    return {
      contentType: "image/webp",
      extension: "webp",
      width: ((bytes[27] << 8) | bytes[26]) & 0x3fff,
      height: ((bytes[29] << 8) | bytes[28]) & 0x3fff,
    };
  }
  return null;
}

function ascii(bytes: Uint8Array, start: number, end: number): string {
  return String.fromCharCode(...bytes.subarray(start, end));
}

function uint24le(bytes: Uint8Array, offset: number): number {
  return bytes[offset] | (bytes[offset + 1] << 8) | (bytes[offset + 2] << 16);
}
