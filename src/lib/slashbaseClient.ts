import {
  GRADE_LEDGER_SCHEMA_VERSION,
  appendDetectionOnlyLedgerRow,
  loadDetectionOnlyLedger,
  type DetectionOnlyLedgerRow,
  type NormalizedGrade,
} from "./gradeLedger";
import { getGradeSessionId } from "./graderClient";
import { supabase } from "./supabase";
import { throwSupabaseFunctionError } from "./supabaseFunctionError";

export type SlashBaseGradeRequest = {
  imageName: string;
  imageUrl: string;
  fileName: string;
  preset: string;
  sequenceCode: string;
};

const FILE_PREFIX = "slashbase:";

export function slashBaseFileId(request: Pick<SlashBaseGradeRequest, "imageName" | "preset">) {
  return `${FILE_PREFIX}${encodeURIComponent(request.preset)}:${request.imageName}:delivered`;
}

export function loadSlashBaseGradeRows(): DetectionOnlyLedgerRow[] {
  return loadDetectionOnlyLedger().filter(
    (row) =>
      row.file_id.startsWith(FILE_PREFIX) &&
      row.vendor === "g1" &&
      row.mock === false &&
      row.grade.vendor === "g1" &&
      row.grade.mock === false &&
      row.grade.mode === "real",
  );
}

/** One explicit click invokes grade-image exactly once, then appends one row. */
export async function gradeSlashBaseImage(
  request: SlashBaseGradeRequest,
): Promise<DetectionOnlyLedgerRow> {
  if (!supabase) throw new Error("Sign in before grading this image.");

  const imageB64 = await imageUrlToDataUrl(request.imageUrl);
  const { data, error } = await supabase.functions.invoke("grade-image", {
    body: {
      image_b64: imageB64,
      role: "remint",
      mode: "real",
      provider: "g1",
      settings_code: request.sequenceCode,
      grade_session_id: getGradeSessionId(),
    },
  });
  if (error) await throwSupabaseFunctionError(error);

  const grade = assertRealG1Grade(data);
  const row: DetectionOnlyLedgerRow = {
    schema_version: GRADE_LEDGER_SCHEMA_VERSION,
    run_kind: "detection_only",
    id: crypto.randomUUID(),
    timestamp: new Date().toISOString(),
    file_id: slashBaseFileId(request),
    file_name: request.fileName,
    image_sha256: grade.image_sha256,
    mode: "real",
    vendor: "g1",
    mock: false,
    grade,
    mode_results: { real: grade },
    qa_flag: false,
    settings_code: null,
    worker_job_id: null,
    remint_dispatched: false,
    remint_credits_spent: 0,
  };
  appendDetectionOnlyLedgerRow(row);
  return row;
}

function assertRealG1Grade(value: unknown): NormalizedGrade {
  if (!isRecord(value)) throw new Error("The real grade response was invalid.");
  const verdicts = new Set(["CLEAR", "NEAR", "BORDER", "FAIL"]);
  const raw = isRecord(value.raw) ? value.raw : null;
  if (
    value.vendor !== "g1" ||
    value.mock !== false ||
    value.mode !== "real" ||
    typeof value.grade_id !== "string" ||
    !/^[a-f0-9]{64}$/.test(String(value.image_sha256)) ||
    typeof value.verdict !== "string" ||
    !verdicts.has(value.verdict) ||
    !isProbability(value.ai_probability) ||
    !isProbability(value.deepfake_probability) ||
    !isRecord(value.sources) ||
    !raw ||
    typeof raw.task_id !== "string" ||
    !raw.task_id
  ) {
    throw new Error("SlashBase accepts only real G1 grades.");
  }
  return value as NormalizedGrade;
}

async function imageUrlToDataUrl(imageUrl: string): Promise<string> {
  const response = await fetch(imageUrl, { cache: "force-cache" });
  if (!response.ok) throw new Error("This image could not be opened for grading.");
  const blob = await response.blob();
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(new Error("This image could not be read for grading."));
    reader.onload = () => {
      if (typeof reader.result !== "string") {
        reject(new Error("This image could not be prepared for grading."));
        return;
      }
      resolve(reader.result);
    };
    reader.readAsDataURL(blob);
  });
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isProbability(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value) && value >= 0 && value <= 1;
}
