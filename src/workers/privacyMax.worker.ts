/// <reference lib="webworker" />

import { applyFibonacci88Mark } from "../lib/fibonacci88";

type PrivacyRequest = {
  id: string;
  file: File;
  creatorId: string;
  cleanVisibleMarks: boolean;
  markStrength: number;
  jpegQuality: number;
  targetSize: number;
  fit: "contain" | "cover";
};

type PrivacySuccess = {
  id: string;
  ok: true;
  blob: Blob;
  width: number;
  height: number;
  report: {
    metadataStripped: true;
    visibleCleanupApplied: boolean;
    visibleCleanupPixels: number;
    fibonacciBits: 88;
    jpegQuality: number;
  };
};

type PrivacyFailure = {
  id: string;
  ok: false;
  error: string;
};

type WorkerResponse = PrivacySuccess | PrivacyFailure;

self.onmessage = async (event: MessageEvent<PrivacyRequest>) => {
  const request = event.data;
  try {
    const bitmap = await createImageBitmap(request.file);
    const canvas = new OffscreenCanvas(request.targetSize, request.targetSize);
    const context = canvas.getContext("2d", {
      alpha: false,
      willReadFrequently: true
    });

    if (!context) {
      throw new Error("Canvas is not available in this browser.");
    }

    context.fillStyle = "#f7f8f4";
    context.fillRect(0, 0, request.targetSize, request.targetSize);
    drawFittedImage(context, bitmap, request.targetSize, request.fit);

    let imageData = context.getImageData(0, 0, request.targetSize, request.targetSize);
    const visibleCleanup = request.cleanVisibleMarks
      ? cleanVisibleCornerMarks(imageData)
      : { applied: false, changedPixels: 0, imageData };

    imageData = applyFibonacci88Mark(visibleCleanup.imageData, {
      creatorId: request.creatorId,
      strength: request.markStrength
    });

    context.putImageData(imageData, 0, 0);
    const blob = await canvas.convertToBlob({
      type: "image/jpeg",
      quality: request.jpegQuality
    });

    const response: WorkerResponse = {
      id: request.id,
      ok: true,
      blob,
      width: request.targetSize,
      height: request.targetSize,
      report: {
        metadataStripped: true,
        visibleCleanupApplied: visibleCleanup.applied,
        visibleCleanupPixels: visibleCleanup.changedPixels,
        fibonacciBits: 88,
        jpegQuality: request.jpegQuality
      }
    };
    self.postMessage(response);
  } catch (error) {
    const response: WorkerResponse = {
      id: request.id,
      ok: false,
      error: error instanceof Error ? error.message : "Processing failed."
    };
    self.postMessage(response);
  }
};

function drawFittedImage(
  context: OffscreenCanvasRenderingContext2D,
  bitmap: ImageBitmap,
  targetSize: number,
  fit: "contain" | "cover"
) {
  const imageRatio = bitmap.width / bitmap.height;
  const targetRatio = 1;
  let drawWidth = targetSize;
  let drawHeight = targetSize;

  if (fit === "contain") {
    if (imageRatio > targetRatio) {
      drawWidth = targetSize;
      drawHeight = targetSize / imageRatio;
    } else {
      drawHeight = targetSize;
      drawWidth = targetSize * imageRatio;
    }
  } else if (imageRatio > targetRatio) {
    drawHeight = targetSize;
    drawWidth = targetSize * imageRatio;
  } else {
    drawWidth = targetSize;
    drawHeight = targetSize / imageRatio;
  }

  const x = (targetSize - drawWidth) / 2;
  const y = (targetSize - drawHeight) / 2;

  context.imageSmoothingEnabled = true;
  context.imageSmoothingQuality = "high";
  context.drawImage(bitmap, x, y, drawWidth, drawHeight);
}

function cleanVisibleCornerMarks(imageData: ImageData): {
  applied: boolean;
  changedPixels: number;
  imageData: ImageData;
} {
  const { width, height, data } = imageData;
  const masks = [
    buildCornerMask(imageData, "bottom-right"),
    buildCornerMask(imageData, "bottom-left")
  ];

  let changedPixels = 0;
  for (const mask of masks) {
    if (!mask.shouldApply) continue;
    dilateMask(mask.mask, width, height, 2);
    changedPixels += inpaintMask(data, width, height, mask.mask);
  }

  return {
    applied: changedPixels > 0,
    changedPixels,
    imageData
  };
}

function buildCornerMask(
  imageData: ImageData,
  corner: "bottom-right" | "bottom-left"
): { shouldApply: boolean; mask: Uint8Array } {
  const { width, height, data } = imageData;
  const mask = new Uint8Array(width * height);
  const regionWidth = Math.floor(width * 0.28);
  const regionHeight = Math.floor(height * 0.22);
  const startX = corner === "bottom-right" ? width - regionWidth : 0;
  const startY = height - regionHeight;
  let selected = 0;
  let regionPixels = 0;

  for (let y = startY; y < height; y += 1) {
    for (let x = startX; x < startX + regionWidth; x += 1) {
      const offset = (y * width + x) * 4;
      const r = data[offset];
      const g = data[offset + 1];
      const b = data[offset + 2];
      const luminance = 0.299 * r + 0.587 * g + 0.114 * b;
      const chromaSpread = Math.max(r, g, b) - Math.min(r, g, b);
      const isLikelyLightOverlay = luminance > 202 && chromaSpread < 34;

      regionPixels += 1;
      if (isLikelyLightOverlay) {
        mask[y * width + x] = 1;
        selected += 1;
      }
    }
  }

  const density = selected / Math.max(1, regionPixels);
  return {
    shouldApply: density > 0.002 && density < 0.12,
    mask
  };
}

function dilateMask(mask: Uint8Array, width: number, height: number, iterations: number) {
  for (let iteration = 0; iteration < iterations; iteration += 1) {
    const copy = mask.slice();
    for (let y = 1; y < height - 1; y += 1) {
      for (let x = 1; x < width - 1; x += 1) {
        const index = y * width + x;
        if (copy[index] === 1) continue;
        if (
          copy[index - 1] ||
          copy[index + 1] ||
          copy[index - width] ||
          copy[index + width]
        ) {
          mask[index] = 1;
        }
      }
    }
  }
}

function inpaintMask(
  data: Uint8ClampedArray,
  width: number,
  height: number,
  mask: Uint8Array
): number {
  let changed = 0;
  const original = new Uint8ClampedArray(data);
  const radius = 9;

  for (let y = 0; y < height; y += 1) {
    for (let x = 0; x < width; x += 1) {
      const index = y * width + x;
      if (!mask[index]) continue;

      let r = 0;
      let g = 0;
      let b = 0;
      let samples = 0;

      for (let yy = Math.max(0, y - radius); yy <= Math.min(height - 1, y + radius); yy += 1) {
        for (let xx = Math.max(0, x - radius); xx <= Math.min(width - 1, x + radius); xx += 1) {
          const neighbor = yy * width + xx;
          if (mask[neighbor]) continue;
          const offset = neighbor * 4;
          r += original[offset];
          g += original[offset + 1];
          b += original[offset + 2];
          samples += 1;
        }
      }

      if (samples > 0) {
        const offset = index * 4;
        data[offset] = r / samples;
        data[offset + 1] = g / samples;
        data[offset + 2] = b / samples;
        changed += 1;
      }
    }
  }

  return changed;
}
