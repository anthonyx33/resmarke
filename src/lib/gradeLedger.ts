import { canonicalJson } from "./settingsCode";

export const GRADE_LEDGER_SCHEMA_VERSION = 1 as const;
export const GRADE_LEDGER_LIMIT = 500;
const STORAGE_KEY = "resmarke:relab:grade-ledger:v1";
const DETECTION_ONLY_STORAGE_KEY = "resmarke:relab:detection-only-ledger:v1";
const NON_SOURCE_FAMILIES = new Set([
  "ai_generated",
  "not_ai_generated",
  "deepfake",
  "none",
  "inconclusive",
  "ai_generated_audio",
  "not_ai_generated_audio"
]);

export type GradeMode = "sdxl" | "flux_schnell" | "real";
export type GradeRole = "og" | "remint";
export type GradeVerdict = "CLEAR" | "NEAR" | "BORDER" | "FAIL";

export type RankedAiSource = {
  rank: number;
  family: string;
  probability: number;
};

export type NormalizedGrade = {
  grade_id: string;
  image_sha256: string;
  vendor: string;
  mode: GradeMode;
  ai_probability: number;
  deepfake_probability: number;
  verdict: GradeVerdict;
  top_source: string | null;
  sources: Record<string, number>;
  swap_index: number;
  retention_index: number;
  raw: Record<string, unknown>;
  mock: boolean;
  cache_hit: boolean;
  provider_calls: number;
  vendor_error?: string;
  requested_mode?: GradeMode;
  session_usage?: {
    vendor_calls: number;
    cap: number;
  };
};

export type ModeGradePair = {
  mode: GradeMode;
  og: NormalizedGrade;
  remint: NormalizedGrade;
  delta: number;
  verdict: GradeVerdict;
  qa_flag: boolean;
};

export type WorkerReportProvenance = {
  digest_sha256: string;
  settings: unknown;
  attempts: unknown[];
  finish_adaptive: unknown;
  detector_gate: unknown;
  rating_88: unknown;
  quality_finish_qc: unknown;
  full: Record<string, unknown> | null;
};

export type GradeLedgerRow = {
  schema_version: typeof GRADE_LEDGER_SCHEMA_VERSION;
  id: string;
  timestamp: string;
  file_id: string;
  file_name: string;
  job_id: string;
  image_sha256: string;
  settings_code: string;
  requested_settings: Record<string, unknown>;
  executed: WorkerReportProvenance;
  mode: GradeMode;
  vendor: string;
  mock: boolean;
  og_grade: NormalizedGrade;
  remint_grade: NormalizedGrade;
  mode_results: Partial<Record<GradeMode, ModeGradePair>>;
  delta: number;
  verdict: GradeVerdict;
  qa_flag: boolean;
  swap_index: number;
  retention_index: number;
};

export type DetectionOnlyLedgerRow = {
  schema_version: typeof GRADE_LEDGER_SCHEMA_VERSION;
  run_kind: "detection_only";
  id: string;
  timestamp: string;
  file_id: string;
  file_name: string;
  image_sha256: string;
  mode: GradeMode;
  vendor: string;
  mock: boolean;
  grade: NormalizedGrade;
  mode_results: Partial<Record<GradeMode, NormalizedGrade>>;
  qa_flag: boolean;
  settings_code: null;
  worker_job_id: null;
  remint_dispatched: false;
  remint_credits_spent: 0;
};

type StoredLedger = {
  schema_version: typeof GRADE_LEDGER_SCHEMA_VERSION;
  rows: GradeLedgerRow[];
};

type StoredDetectionOnlyLedger = {
  schema_version: typeof GRADE_LEDGER_SCHEMA_VERSION;
  rows: DetectionOnlyLedgerRow[];
};

export function loadGradeLedger(): GradeLedgerRow[] {
  if (typeof localStorage === "undefined") return [];
  const raw = localStorage.getItem(STORAGE_KEY);
  if (!raw) return [];
  try {
    const parsed = JSON.parse(raw) as unknown;
    if (!isStoredLedger(parsed)) return [];
    return parsed.rows.slice(-GRADE_LEDGER_LIMIT);
  } catch {
    return [];
  }
}

/** Append-only persistence. Existing rows are never edited; re-grades append
 * a new record with a new id and timestamp. */
export function appendGradeLedgerRow(row: GradeLedgerRow): GradeLedgerRow[] {
  const rows = [...loadGradeLedger(), assertLedgerRow(row)].slice(-GRADE_LEDGER_LIMIT);
  persist(rows);
  return rows;
}

export function loadDetectionOnlyLedger(): DetectionOnlyLedgerRow[] {
  if (typeof localStorage === "undefined") return [];
  const raw = localStorage.getItem(DETECTION_ONLY_STORAGE_KEY);
  if (!raw) return [];
  try {
    const parsed = JSON.parse(raw) as unknown;
    if (!isStoredDetectionOnlyLedger(parsed)) return [];
    return parsed.rows.slice(-GRADE_LEDGER_LIMIT);
  } catch {
    return [];
  }
}

export function appendDetectionOnlyLedgerRow(
  row: DetectionOnlyLedgerRow
): DetectionOnlyLedgerRow[] {
  const rows = [...loadDetectionOnlyLedger(), assertDetectionOnlyRow(row)].slice(
    -GRADE_LEDGER_LIMIT
  );
  persistDetectionOnly(rows);
  return rows;
}

export function exportDetectionOnlyLedgerJsonl(
  rows = loadDetectionOnlyLedger()
): string {
  return rows.map((row) => JSON.stringify(row)).join("\n") + (rows.length ? "\n" : "");
}

export function exportDetectionOnlyLedgerCsv(
  rows = loadDetectionOnlyLedger()
): string {
  const header = [
    "timestamp",
    "file_id",
    "file_name",
    "image_sha256",
    "grade_id",
    "vendor",
    "mode",
    "ai_probability",
    "deepfake_probability",
    "verdict",
    "qa_flag",
    "cache_hit",
    "provider_calls",
    "session_vendor_calls",
    "session_cap",
    "top_5_sources_json",
    "vendor_error",
    "remint_dispatched",
    "remint_credits_spent"
  ];
  const lines = rows.map((row) =>
    [
      row.timestamp,
      row.file_id,
      row.file_name,
      row.image_sha256,
      row.grade.grade_id,
      row.vendor,
      row.mode,
      row.grade.ai_probability,
      row.grade.deepfake_probability,
      row.grade.verdict,
      row.qa_flag,
      row.grade.cache_hit,
      row.grade.provider_calls,
      row.grade.session_usage?.vendor_calls ?? "",
      row.grade.session_usage?.cap ?? "",
      JSON.stringify(topAiSources(row.grade.sources)),
      row.grade.vendor_error ?? "",
      row.remint_dispatched,
      row.remint_credits_spent
    ].map(csvCell).join(",")
  );
  return [header.join(","), ...lines].join("\n") + "\n";
}

/** Import accepts this module's JSONL export or a JSON array. Valid rows are
 * appended, duplicate ids are ignored, and the same 500-row retention rule
 * is applied. */
export function importGradeLedger(text: string): GradeLedgerRow[] {
  const trimmed = text.trim();
  if (!trimmed) return loadGradeLedger();

  let values: unknown[];
  if (trimmed.startsWith("[")) {
    const parsed = JSON.parse(trimmed) as unknown;
    if (!Array.isArray(parsed)) throw new Error("Ledger import must be a JSON array or JSONL.");
    values = parsed;
  } else {
    values = trimmed
      .split(/\r?\n/)
      .filter(Boolean)
      .map((line, index) => {
        try {
          return JSON.parse(line) as unknown;
        } catch {
          throw new Error(`Ledger JSONL line ${index + 1} is not valid JSON.`);
        }
      });
  }

  const current = loadGradeLedger();
  const ids = new Set(current.map((row) => row.id));
  for (const value of values) {
    const row = assertLedgerRow(value);
    if (!ids.has(row.id)) {
      current.push(row);
      ids.add(row.id);
    }
  }
  const rows = current.slice(-GRADE_LEDGER_LIMIT);
  persist(rows);
  return rows;
}

export function exportGradeLedgerJsonl(rows = loadGradeLedger()): string {
  return rows.map((row) => JSON.stringify(row)).join("\n") + (rows.length ? "\n" : "");
}

export function exportGradeLedgerCsv(rows = loadGradeLedger()): string {
  const header = [
    "timestamp",
    "file_id",
    "file_name",
    "job_id",
    "settings_code",
    "vendor",
    "mode",
    "mock",
    "image_sha256",
    "og_ai_probability",
    "og_deepfake_probability",
    "og_top_source",
    "og_top_5_sources_json",
    "og_cache_hit",
    "og_provider_calls",
    "remint_ai_probability",
    "remint_deepfake_probability",
    "remint_top_source",
    "remint_top_5_sources_json",
    "remint_cache_hit",
    "remint_provider_calls",
    "delta",
    "swap_index",
    "retention_index",
    "verdict",
    "qa_flag",
    "worker_report_digest"
  ];
  const lines = rows.map((row) =>
    [
      row.timestamp,
      row.file_id,
      row.file_name,
      row.job_id,
      row.settings_code,
      row.vendor,
      row.mode,
      row.mock,
      row.image_sha256,
      row.og_grade.ai_probability,
      row.og_grade.deepfake_probability,
      row.og_grade.top_source ?? "",
      JSON.stringify(topAiSources(row.og_grade.sources)),
      row.og_grade.cache_hit,
      row.og_grade.provider_calls,
      row.remint_grade.ai_probability,
      row.remint_grade.deepfake_probability,
      row.remint_grade.top_source ?? "",
      JSON.stringify(topAiSources(row.remint_grade.sources)),
      row.remint_grade.cache_hit,
      row.remint_grade.provider_calls,
      row.delta,
      row.swap_index,
      row.retention_index,
      row.verdict,
      row.qa_flag,
      row.executed.digest_sha256
    ].map(csvCell).join(",")
  );
  return [header.join(","), ...lines].join("\n") + "\n";
}

/** This header is a protocol surface consumed by the optimization loop. */
export function compactGradeReport(rows = loadGradeLedger()): string {
  const header = "| OG | OG AI% | top source | remint AI% | remint top | delta | verdict |";
  const divider = "|---|---:|---|---:|---|---:|---|";
  const body = rows.map(
    (row) =>
      `| ${compactCell(row.file_name)} | ${percent(row.og_grade.ai_probability)} | ${compactCell(
        row.og_grade.top_source ?? "—"
      )} | ${percent(row.remint_grade.ai_probability)} | ${compactCell(
        row.remint_grade.top_source ?? "—"
      )} | ${signedPercent(row.delta)} | ${row.verdict} |`
  );
  return [header, divider, ...body].join("\n");
}

export function verdictFor(probability: number): GradeVerdict {
  const value = clamp01(probability);
  if (value <= 0.1) return "CLEAR";
  if (value <= 0.15) return "NEAR";
  if (value <= 0.3) return "BORDER";
  return "FAIL";
}

/** Stable, machine-readable ranking derived from the full normalized source
 * map. The ledger keeps every source; displays and CSVs surface the top five. */
export function topAiSources(
  sources: Record<string, number>,
  limit = 5
): RankedAiSource[] {
  const safeLimit = Math.max(0, Math.min(100, Math.floor(limit)));
  return Object.entries(sources)
    .filter(
      ([family, probability]) =>
        family.trim().length > 0 &&
        !NON_SOURCE_FAMILIES.has(family.trim().toLowerCase()) &&
        Number.isFinite(probability) &&
        probability >= 0
    )
    .map(([family, probability]) => ({
      family,
      probability: clamp01(probability > 1 ? probability / 100 : probability)
    }))
    .sort((a, b) => b.probability - a.probability || a.family.localeCompare(b.family))
    .slice(0, safeLimit)
    .map((source, index) => ({ rank: index + 1, ...source }));
}

export async function workerReportProvenance(
  report: Record<string, unknown> | undefined
): Promise<WorkerReportProvenance> {
  const full = report ? structuredClone(report) : null;
  const engine = isRecord(report?.engine) ? report.engine : {};
  const qualityFinish = isRecord(engine.quality_finish)
    ? engine.quality_finish
    : isRecord(report?.quality_finish)
      ? report.quality_finish
      : engine;
  const qc = isRecord(qualityFinish.qc) ? qualityFinish.qc : null;
  return {
    digest_sha256: await sha256Hex(canonicalJson(full)),
    settings: engine.settings ?? null,
    attempts: Array.isArray(engine.attempts) ? engine.attempts : [],
    finish_adaptive:
      engine.finish_adaptive ?? qualityFinish.finish_adaptive ?? report?.finish_adaptive ?? null,
    detector_gate: engine.detector_gate ?? null,
    rating_88: engine.rating_88 ?? report?.rating_88 ?? null,
    quality_finish_qc: qc,
    full
  };
}

export async function sha256Hex(value: string | ArrayBuffer): Promise<string> {
  const bytes = typeof value === "string" ? new TextEncoder().encode(value) : value;
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  return Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, "0")).join("");
}

function persist(rows: GradeLedgerRow[]) {
  if (typeof localStorage === "undefined") return;
  const stored: StoredLedger = { schema_version: GRADE_LEDGER_SCHEMA_VERSION, rows };
  localStorage.setItem(STORAGE_KEY, JSON.stringify(stored));
}

function persistDetectionOnly(rows: DetectionOnlyLedgerRow[]) {
  if (typeof localStorage === "undefined") return;
  const stored: StoredDetectionOnlyLedger = {
    schema_version: GRADE_LEDGER_SCHEMA_VERSION,
    rows
  };
  localStorage.setItem(DETECTION_ONLY_STORAGE_KEY, JSON.stringify(stored));
}

function assertLedgerRow(value: unknown): GradeLedgerRow {
  if (!isRecord(value) || value.schema_version !== GRADE_LEDGER_SCHEMA_VERSION) {
    throw new Error(`Unsupported grade-ledger schema; expected v${GRADE_LEDGER_SCHEMA_VERSION}.`);
  }
  const required = ["id", "timestamp", "file_id", "settings_code", "mode", "verdict"];
  if (required.some((key) => typeof value[key] !== "string")) {
    throw new Error("Grade-ledger row is missing required fields.");
  }
  if (!isNormalizedGrade(value.og_grade) || !isNormalizedGrade(value.remint_grade)) {
    throw new Error("Grade-ledger row has invalid normalized grades.");
  }
  return value as GradeLedgerRow;
}

function isStoredLedger(value: unknown): value is StoredLedger {
  return (
    isRecord(value) &&
    value.schema_version === GRADE_LEDGER_SCHEMA_VERSION &&
    Array.isArray(value.rows) &&
    value.rows.every((row) => {
      try {
        assertLedgerRow(row);
        return true;
      } catch {
        return false;
      }
    })
  );
}

function assertDetectionOnlyRow(value: unknown): DetectionOnlyLedgerRow {
  if (
    !isRecord(value) ||
    value.schema_version !== GRADE_LEDGER_SCHEMA_VERSION ||
    value.run_kind !== "detection_only" ||
    value.settings_code !== null ||
    value.worker_job_id !== null ||
    value.remint_dispatched !== false ||
    value.remint_credits_spent !== 0 ||
    typeof value.id !== "string" ||
    typeof value.timestamp !== "string" ||
    typeof value.file_id !== "string" ||
    typeof value.file_name !== "string" ||
    !isNormalizedGrade(value.grade)
  ) {
    throw new Error("Detection-only ledger row is invalid.");
  }
  return value as DetectionOnlyLedgerRow;
}

function isStoredDetectionOnlyLedger(value: unknown): value is StoredDetectionOnlyLedger {
  return (
    isRecord(value) &&
    value.schema_version === GRADE_LEDGER_SCHEMA_VERSION &&
    Array.isArray(value.rows) &&
    value.rows.every((row) => {
      try {
        assertDetectionOnlyRow(row);
        return true;
      } catch {
        return false;
      }
    })
  );
}

function isNormalizedGrade(value: unknown): value is NormalizedGrade {
  return (
    isRecord(value) &&
    typeof value.grade_id === "string" &&
    typeof value.image_sha256 === "string" &&
    typeof value.ai_probability === "number" &&
    typeof value.mode === "string"
  );
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function csvCell(value: unknown): string {
  const text = String(value ?? "");
  return /[",\r\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
}

function compactCell(value: string): string {
  return value.replace(/\|/g, "\\|").replace(/[\r\n]+/g, " ");
}

function percent(value: number): string {
  return `${(clamp01(value) * 100).toFixed(1)}%`;
}

function signedPercent(value: number): string {
  const amount = Math.max(-1, Math.min(1, value)) * 100;
  return `${amount >= 0 ? "+" : ""}${amount.toFixed(1)}%`;
}

function clamp01(value: number): number {
  if (!Number.isFinite(value)) return 0;
  return Math.max(0, Math.min(1, value));
}
