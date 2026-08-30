export const SLASHBASE_PRESETS = [
  "Config A",
  "1A",
  "2B",
  "3C",
  "ReMint 1.01",
] as const;

export type SlashBasePreset = (typeof SLASHBASE_PRESETS)[number];
export type SlashBaseSide = "original" | "delivered";
export type SlashBaseVerdict = "CLEAR" | "NEAR" | "BORDER" | "FAIL";

export type SlashBaseGrade = {
  ai_probability: number;
  deepfake_probability: number;
  image_sha256: string;
  mode: "real";
  mock: false;
  task_id: string;
  vendor: "g1";
  verdict: SlashBaseVerdict;
};

export type SlashBaseSeedRow = {
  fileName: string;
  imageName: string;
  sequenceCode: string;
  side: SlashBaseSide;
  preset: "ReMint 1.01";
  timestamp: string;
  grade: SlashBaseGrade;
};

export type SlashBaseSeedOptions = {
  expectedRows?: number;
};

export type SlashBaseSeedVerification = {
  rowsVerified: number;
  imagesVerified: number;
  mockRows: 0;
  vendor: "g1";
};

const VERDICTS = new Set<SlashBaseVerdict>(["CLEAR", "NEAR", "BORDER", "FAIL"]);

/**
 * Imports the canonical phase-B JSONL. The parser is intentionally fail-closed:
 * any mock-marked source row aborts the complete import, and only real G1
 * phase_b_grade records are eligible for SlashBase.
 */
export function parseSlashBaseSeedLedger(
  text: string,
  options: SlashBaseSeedOptions = {},
): SlashBaseSeedRow[] {
  const records = parseJsonl(text);
  const gradeRecords = records.filter((record) => record.event === "phase_b_grade");
  for (const record of gradeRecords) {
    if (record.mock === true) {
      throw new Error("SlashBase import rejected a mock row.");
    }
  }

  const sequenceCodes = new Map<string, string>();
  for (const record of records) {
    if (record.event !== "cell_complete") continue;
    const imageName = requiredString(record.image, "cell image");
    const sequenceCode = requiredString(record.settings_code, "settings code");
    const existing = sequenceCodes.get(imageName);
    if (existing && existing !== sequenceCode) {
      throw new Error(`SlashBase import found conflicting settings codes for ${imageName}.`);
    }
    sequenceCodes.set(imageName, sequenceCode);
  }

  const rows = gradeRecords.map((record) => importGradeRow(record, sequenceCodes));

  if (options.expectedRows !== undefined && rows.length !== options.expectedRows) {
    throw new Error(
      `SlashBase import expected ${options.expectedRows} real rows; received ${rows.length}.`,
    );
  }

  const identities = new Set<string>();
  const sidesByImage = new Map<string, Set<SlashBaseSide>>();
  for (const row of rows) {
    const identity = `${row.imageName}:${row.side}`;
    if (identities.has(identity)) {
      throw new Error(`SlashBase import found a duplicate ${identity} row.`);
    }
    identities.add(identity);
    const sides = sidesByImage.get(row.imageName) ?? new Set<SlashBaseSide>();
    sides.add(row.side);
    sidesByImage.set(row.imageName, sides);
  }
  for (const [imageName, sides] of sidesByImage) {
    if (!sides.has("original") || !sides.has("delivered")) {
      throw new Error(`SlashBase import requires an original and delivery for ${imageName}.`);
    }
  }

  return rows.sort(
    (left, right) =>
      imageNumber(left.imageName) - imageNumber(right.imageName) ||
      (left.side === "original" ? -1 : 1),
  );
}

/**
 * Cross-checks the compact page rows against the full detection-only ledger.
 * This is kept separate so the 836 KB raw vendor payload is not shipped in the
 * browser bundle, while tests can still prove every displayed field is exact.
 */
export function verifySlashBaseDetectionLedger(
  seedRows: SlashBaseSeedRow[],
  detectionLedger: unknown,
): SlashBaseSeedVerification {
  if (!isRecord(detectionLedger) || !Array.isArray(detectionLedger.rows)) {
    throw new Error("SlashBase detection ledger is invalid.");
  }

  const detectionRows = detectionLedger.rows.map((value) => {
    if (!isRecord(value) || !isRecord(value.grade)) {
      throw new Error("SlashBase detection ledger contains an invalid row.");
    }
    if (value.mock === true || value.grade.mock === true) {
      throw new Error("SlashBase import rejected a mock row.");
    }
    if (value.vendor !== "g1" || value.grade.vendor !== "g1") {
      throw new Error("SlashBase accepts only G1 detection rows.");
    }
    return value;
  });

  for (const seed of seedRows) {
    const match = detectionRows.find((row) => {
      const grade = row.grade as Record<string, unknown>;
      const raw = isRecord(grade.raw) ? grade.raw : null;
      return (
        row.timestamp === seed.timestamp &&
        row.file_name === seed.fileName &&
        row.image_sha256 === seed.grade.image_sha256 &&
        grade.image_sha256 === seed.grade.image_sha256 &&
        raw?.task_id === seed.grade.task_id
      );
    });
    if (!match) {
      throw new Error(`SlashBase could not verify ${seed.imageName} ${seed.side}.`);
    }
    const grade = match.grade as Record<string, unknown>;
    if (
      grade.ai_probability !== seed.grade.ai_probability ||
      grade.deepfake_probability !== seed.grade.deepfake_probability ||
      grade.mode !== seed.grade.mode ||
      grade.mock !== false ||
      grade.verdict !== seed.grade.verdict
    ) {
      throw new Error(`SlashBase grade mismatch for ${seed.imageName} ${seed.side}.`);
    }
  }

  return {
    rowsVerified: seedRows.length,
    imagesVerified: new Set(seedRows.map((row) => row.imageName)).size,
    mockRows: 0,
    vendor: "g1",
  };
}

function importGradeRow(
  record: Record<string, unknown>,
  sequenceCodes: Map<string, string>,
): SlashBaseSeedRow {
  const imageName = requiredString(record.image, "image");
  const group = requiredString(record.group, "group");
  if (group !== "OG" && group !== "RM") {
    throw new Error(`SlashBase import found an invalid group for ${imageName}.`);
  }
  if (record.mock !== false) {
    throw new Error(`SlashBase requires an explicit real grade for ${imageName}.`);
  }
  if (record.vendor !== "g1") {
    throw new Error(`SlashBase accepts only G1 grades for ${imageName}.`);
  }
  if (record.mode !== "real") {
    throw new Error(`SlashBase accepts only real-mode grades for ${imageName}.`);
  }

  const verdict = requiredString(record.verdict, "verdict") as SlashBaseVerdict;
  if (!VERDICTS.has(verdict)) {
    throw new Error(`SlashBase found an invalid verdict for ${imageName}.`);
  }
  const sequenceCode = sequenceCodes.get(imageName);
  if (!sequenceCode?.startsWith("SEQ-")) {
    throw new Error(`SlashBase is missing a SEQ code for ${imageName}.`);
  }

  const timestamp = requiredString(record.timestamp, "timestamp");
  if (!Number.isFinite(Date.parse(timestamp))) {
    throw new Error(`SlashBase found an invalid timestamp for ${imageName}.`);
  }

  return {
    fileName: requiredString(record.file_name, "file name"),
    imageName,
    sequenceCode,
    side: group === "OG" ? "original" : "delivered",
    preset: "ReMint 1.01",
    timestamp,
    grade: {
      ai_probability: requiredProbability(record.ai_probability, "AI probability"),
      deepfake_probability: requiredProbability(
        record.deepfake_probability,
        "deepfake probability",
      ),
      image_sha256: requiredHash(record.image_sha256),
      mode: "real",
      mock: false,
      task_id: requiredString(record.task_id, "task id"),
      vendor: "g1",
      verdict,
    },
  };
}

function parseJsonl(text: string): Record<string, unknown>[] {
  if (!text.trim()) throw new Error("SlashBase import is empty.");
  return text
    .split(/\r?\n/)
    .filter((line) => line.trim())
    .map((line, index) => {
      let value: unknown;
      try {
        value = JSON.parse(line) as unknown;
      } catch {
        throw new Error(`SlashBase JSONL line ${index + 1} is invalid.`);
      }
      if (!isRecord(value)) {
        throw new Error(`SlashBase JSONL line ${index + 1} is not an object.`);
      }
      return value;
    });
}

function requiredString(value: unknown, label: string): string {
  if (typeof value !== "string" || !value.trim()) {
    throw new Error(`SlashBase row is missing ${label}.`);
  }
  return value;
}

function requiredProbability(value: unknown, label: string): number {
  if (typeof value !== "number" || !Number.isFinite(value) || value < 0 || value > 1) {
    throw new Error(`SlashBase row has an invalid ${label}.`);
  }
  return value;
}

function requiredHash(value: unknown): string {
  const hash = requiredString(value, "image hash");
  if (!/^[a-f0-9]{64}$/.test(hash)) {
    throw new Error("SlashBase row has an invalid image hash.");
  }
  return hash;
}

function imageNumber(imageName: string): number {
  const match = imageName.match(/(\d+)$/);
  return match ? Number(match[1]) : Number.MAX_SAFE_INTEGER;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
