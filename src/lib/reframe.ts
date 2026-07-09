// Browser-side "reframe" pre-transform: a subtle zoom-in + tilt + sub-pixel
// shift applied on a <canvas> before the image is processed or uploaded. Zero
// GPU, runs entirely client-side.
//
// Why it helps: watermarks (SynthID) and diffusion fingerprints assume the
// original pixel grid and framing. A slight non-integer zoom (crop), a small
// rotation and a sub-pixel translation desynchronise that grid and shift the
// composition, which disrupts the watermark's spatial alignment and the
// fingerprint's grid-locked artifacts. Competitors do exactly this. It is
// deliberately gentle (a few percent zoom, ~1.5deg) so it stays imperceptible
// on real content while still breaking spatial assumptions.

export type ReframeOptions = {
  zoom?: number; // scale factor, e.g. 1.06 = crop ~6% off the edges
  maxRotationDeg?: number; // random tilt magnitude, e.g. 1.5
  maxShiftPx?: number; // random sub-pixel/pixel translation magnitude
};

const DEFAULTS: Required<ReframeOptions> = {
  zoom: 1.06,
  maxRotationDeg: 1.5,
  maxShiftPx: 6
};

export async function reframeImageFile(file: File, options: ReframeOptions = {}): Promise<File> {
  const opts = { ...DEFAULTS, ...options };
  const img = await loadImage(file);
  const width = img.naturalWidth || img.width;
  const height = img.naturalHeight || img.height;

  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext("2d");
  if (!ctx) throw new Error("Reframe: 2D canvas context unavailable.");
  ctx.imageSmoothingEnabled = true;
  ctx.imageSmoothingQuality = "high";

  const rotation = ((Math.random() * 2 - 1) * opts.maxRotationDeg * Math.PI) / 180;
  const shiftX = (Math.random() * 2 - 1) * opts.maxShiftPx;
  const shiftY = (Math.random() * 2 - 1) * opts.maxShiftPx;

  // Draw about the centre: translate -> rotate -> scale, so the zoom crops the
  // edges evenly and the rotation covers the frame without empty corners (the
  // zoom is chosen large enough to hide the rotated gaps).
  ctx.translate(width / 2 + shiftX, height / 2 + shiftY);
  ctx.rotate(rotation);
  ctx.scale(opts.zoom, opts.zoom);
  ctx.drawImage(img, -width / 2, -height / 2, width, height);

  URL.revokeObjectURL(img.src);

  const type = file.type === "image/png" ? "image/png" : "image/jpeg";
  const quality = type === "image/jpeg" ? 0.95 : undefined;
  const blob = await canvasToBlob(canvas, type, quality);
  return new File([blob], file.name, { type, lastModified: Date.now() });
}

function loadImage(file: File): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(file);
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = () => {
      URL.revokeObjectURL(url);
      reject(new Error("Reframe: could not decode image."));
    };
    img.src = url;
  });
}

function canvasToBlob(canvas: HTMLCanvasElement, type: string, quality?: number): Promise<Blob> {
  return new Promise((resolve, reject) => {
    canvas.toBlob(
      (blob) => (blob ? resolve(blob) : reject(new Error("Reframe: canvas export failed."))),
      type,
      quality
    );
  });
}
