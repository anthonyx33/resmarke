import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import {
  parseSlashBaseSeedLedger,
  verifySlashBaseDetectionLedger,
} from "../src/lib/slashbaseSeed.ts";

const corpusLedgerUrl = new URL(
  "../round-remint-1-01/full-corpus/ledger.jsonl",
  import.meta.url,
);
const detectionLedgerUrl = new URL(
  "../round-remint-1-01/full-corpus/phase-b-detection-ledger.json",
  import.meta.url,
);

test("imports and verifies the 22 real SlashBase seed rows", async () => {
  const [ledgerText, detectionText] = await Promise.all([
    readFile(corpusLedgerUrl, "utf8"),
    readFile(detectionLedgerUrl, "utf8"),
  ]);
  const rows = parseSlashBaseSeedLedger(ledgerText, { expectedRows: 22 });
  const verification = verifySlashBaseDetectionLedger(rows, JSON.parse(detectionText));

  assert.deepEqual(verification, {
    rowsVerified: 22,
    imagesVerified: 11,
    mockRows: 0,
    vendor: "g1",
  });
  assert.equal(rows.filter((row) => row.side === "original").length, 11);
  assert.equal(rows.filter((row) => row.side === "delivered").length, 11);
  assert.equal(rows.every((row) => row.grade.mock === false), true);
  assert.equal(rows.every((row) => row.grade.vendor === "g1"), true);
  assert.equal(rows.every((row) => row.sequenceCode === "SEQ-1.01-yg63qja3got4"), true);
});

test("hard-fails the whole import when a phase row is mock", () => {
  const text = [
    JSON.stringify({
      event: "cell_complete",
      image: "IMG-1",
      settings_code: "SEQ-1.01-test",
      mock: false,
    }),
    JSON.stringify({
      event: "phase_b_grade",
      image: "IMG-1",
      group: "OG",
      file_name: "IMG-1.jpg",
      image_sha256: "a".repeat(64),
      mock: true,
      mode: "real",
      vendor: "g1",
      ai_probability: 0.1,
      deepfake_probability: 0,
      task_id: "task-1",
      timestamp: "2026-08-30T00:00:00.000Z",
      verdict: "CLEAR",
    }),
  ].join("\n");

  assert.throws(() => parseSlashBaseSeedLedger(text), /rejected a mock row/i);
});

test("hard-fails detection verification when any detection row is mock", () => {
  assert.throws(
    () =>
      verifySlashBaseDetectionLedger([], {
        rows: [{ vendor: "g1", mock: true, grade: { vendor: "g1", mock: true } }],
      }),
    /rejected a mock row/i,
  );
});
