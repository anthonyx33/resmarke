import { supabase } from "./supabase";
import { throwSupabaseFunctionError } from "./supabaseFunctionError";
import type { GradeMode, GradeRole, NormalizedGrade } from "./gradeLedger";

export type GradeMeta = {
  mode?: GradeMode;
  settingsCode?: string;
  ogGrade?: NormalizedGrade;
  sessionId?: string;
};

type GradeImageRequest = {
  image_b64?: string;
  image_url?: string;
  role: GradeRole;
  mode?: GradeMode;
  settings_code?: string;
  og_grade?: Pick<NormalizedGrade, "sources">;
  grade_session_id: string;
};

export async function gradeImage(
  file: File,
  role: GradeRole,
  meta: GradeMeta = {}
): Promise<NormalizedGrade> {
  const imageBase64 = await fileToBase64(file);
  return invokeGradeImage({
    image_b64: imageBase64,
    role,
    ...requestMeta(meta)
  });
}

export async function gradeOutputUrl(
  url: string,
  role: GradeRole,
  meta: GradeMeta = {}
): Promise<NormalizedGrade> {
  if (!url) throw new Error("A secure output URL is required for grading.");
  return invokeGradeImage({
    image_url: url,
    role,
    ...requestMeta(meta)
  });
}

export function getGradeSessionId(): string {
  const key = "resmarke:relab:grade-session";
  if (typeof sessionStorage === "undefined") return crypto.randomUUID();
  const existing = sessionStorage.getItem(key);
  if (existing) return existing;
  const next = crypto.randomUUID();
  sessionStorage.setItem(key, next);
  return next;
}

async function invokeGradeImage(body: GradeImageRequest): Promise<NormalizedGrade> {
  if (!supabase) throw new Error("Supabase is not configured for image grading.");
  const { data, error } = await supabase.functions.invoke("grade-image", { body });
  if (error) await throwSupabaseFunctionError(error);
  if (!isNormalizedGrade(data)) throw new Error("grade-image returned an invalid response.");
  return data;
}

function requestMeta(meta: GradeMeta) {
  return {
    mode: meta.mode,
    settings_code: meta.settingsCode,
    og_grade: meta.ogGrade ? { sources: meta.ogGrade.sources } : undefined,
    grade_session_id: meta.sessionId ?? getGradeSessionId()
  };
}

function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(new Error(`Could not read ${file.name} for grading.`));
    reader.onload = () => {
      if (typeof reader.result !== "string") {
        reject(new Error(`Could not encode ${file.name} for grading.`));
        return;
      }
      resolve(reader.result);
    };
    reader.readAsDataURL(file);
  });
}

function isNormalizedGrade(value: unknown): value is NormalizedGrade {
  if (!value || typeof value !== "object") return false;
  const grade = value as Partial<NormalizedGrade>;
  return (
    typeof grade.grade_id === "string" &&
    typeof grade.image_sha256 === "string" &&
    typeof grade.ai_probability === "number" &&
    typeof grade.deepfake_probability === "number" &&
    typeof grade.verdict === "string" &&
    typeof grade.mode === "string" &&
    !!grade.sources &&
    typeof grade.sources === "object"
  );
}
