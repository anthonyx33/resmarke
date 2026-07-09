// Browser-side "reframe" pre-transform: subtle geometric desync applied on a
// <canvas> before upload. Zero GPU, entirely client-side.
//
// Why it is the strongest fingerprint lever (confirmed in live tests: reframe
// OFF -> Hive ~84%, reframe ON -> Hive ~1%): the diffusion fingerprint is a
// periodic, axis-aligned grid. A small ROTATION knocks that grid off-axis so
// the later downscale scatters it instead of aliasing it through. Zoom only
// crops (costs quality), so v4 leans on tilt + shear and keeps zoom to the
// minimum needed to cover the rotated corners.

export type ReframePreset = "subtle" | "balanced" | "strong";

export type ReframeOptions = {
  zoom: number; // scale factor; just enough to hide the rotated/sheared gaps
  rotationDeg: number; // tilt magnitude (the potent part)
  shear: number; // skew factor -> perspective-like structural change
  aspectJitter: number; // tiny non-uniform stretch (grid desync)
  driftPx: number; // off-centre crop drift
};

// Presets. Note zoom scales with rotation because a bigger tilt exposes bigger
// corner gaps that the zoom must cover; these pairs are chosen to keep the crop
// as small as the tilt allows.
export const REFRAME_PRESETS: Record<ReframePreset, ReframeOptions> = {
  subtle: { zoom: 1.022, rotationDeg: 1.6, shear: 0.006, aspectJitter: 0.004, driftPx: 4 },
  balanced: { zoom: 1.035, rotationDeg: 2.6, shear: 0.012, aspectJitter: 0.008, driftPx: 7 },
  strong: { zoom: 1.05, rotationDeg: 3.6, shear: 0.02, aspectJitter: 0.013, driftPx: 11 }
};

export function reframeOptionsFor(
  preset: ReframePreset,
  overrides?: Partial<Pick<ReframeOptions, "zoom" | "rotationDeg">>
): ReframeOptions {
  return { ...REFRAME_PRESETS[preset], ...overrides };
}

// Minimum zoom needed so a WxH frame rotated by |deg| (plus a shear margin)
// leaves no empty corners. Guards against a user dialling zoom too low for
// their chosen tilt (which would show background edges).
export function minimumCoverZoom(
  width: number,
  height: number,
  rotationDeg: number,
  shear: number
): number {
  const a = (Math.abs(rotationDeg) * Math.PI) / 180;
  const cos = Math.cos(a);
  const sin = Math.sin(a);
  const coverW = (width * cos + height * (sin + Math.abs(shear))) / width;
  const coverH = (height * cos + width * (sin + Math.abs(shear))) / height;
  return Math.max(coverW, coverH) + 0.002;
}

export async function reframeImageFile(file: File, options: ReframeOptions): Promise<File> {
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

  const sign = () => (Math.random() < 0.5 ? -1 : 1);
  const rotation = (options.rotationDeg * sign() * Math.PI) / 180;
  const shearX = options.shear * sign();
  const shearY = options.shear * sign() * 0.6;
  const aspectX = 1 + options.aspectJitter * sign();
  const aspectY = 1 + options.aspectJitter * sign();
  const driftX = (Math.random() * 2 - 1) * options.driftPx;
  const driftY = (Math.random() * 2 - 1) * options.driftPx;

  // Never let the zoom drop below what is needed to cover the tilt/shear.
  const zoom = Math.max(options.zoom, minimumCoverZoom(width, height, options.rotationDeg, options.shear));

  ctx.translate(width / 2 + driftX, height / 2 + driftY);
  ctx.rotate(rotation);
  ctx.transform(1, shearY, shearX, 1, 0, 0); // skew -> perspective-like tilt
  ctx.scale(zoom * aspectX, zoom * aspectY);
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
