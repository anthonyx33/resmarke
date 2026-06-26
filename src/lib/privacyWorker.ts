export type OutputFormat = "jpeg" | "png" | "webp";
export type OutputSizeMode = "original" | "square" | "custom";

export type PrivacyMaxOptions = {
  file: File;
  creatorId: string;
  cleanVisibleMarks: boolean;
  markStrength: number;
  quality: number;
  format: OutputFormat;
  sizeMode: OutputSizeMode;
  squareSize: number;
  customWidth: number;
  customHeight: number;
  fit: "contain" | "cover";
};

export type PrivacyMaxResult = {
  blob: Blob;
  width: number;
  height: number;
  report: {
    metadataStripped: true;
    visibleCleanupApplied: boolean;
    visibleCleanupPixels: number;
    fibonacciBits: 88;
    format: OutputFormat;
    quality: number;
  };
};

type WorkerResponse =
  | ({ id: string; ok: true } & PrivacyMaxResult)
  | { id: string; ok: false; error: string };

export function runPrivacyMax(options: PrivacyMaxOptions): Promise<PrivacyMaxResult> {
  const worker = new Worker(new URL("../workers/privacyMax.worker.ts", import.meta.url), {
    type: "module"
  });
  const id = crypto.randomUUID();

  return new Promise((resolve, reject) => {
    worker.onmessage = (event: MessageEvent<WorkerResponse>) => {
      if (event.data.id !== id) return;
      worker.terminate();

      if (event.data.ok) {
        resolve({
          blob: event.data.blob,
          width: event.data.width,
          height: event.data.height,
          report: event.data.report
        });
      } else {
        reject(new Error(event.data.error));
      }
    };

    worker.onerror = (event) => {
      worker.terminate();
      reject(new Error(event.message));
    };

    worker.postMessage({ id, ...options });
  });
}
