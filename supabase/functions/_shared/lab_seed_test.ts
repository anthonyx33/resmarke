import { LabSeedHttpError, validateLabSeedAccess } from "./lab_seed.ts";

const verifiedAdmin = {
  email: "owner@example.com",
  email_confirmed_at: "2026-08-25T00:00:00Z",
};

Deno.test("absent lab seed takes the unchanged path without requiring lab config", () => {
  assert(validateLabSeedAccess(undefined, {}, {}) === null);
});

Deno.test("lab seed gate order and typed statuses are exact", () => {
  expectStatus(() => validateLabSeedAccess("BAD", { email: "other@example.com", email_confirmed_at: "yes" }, {}), 403);
  expectStatus(() => validateLabSeedAccess("BAD", verifiedAdmin, { corpusAdminEmails: "owner@example.com" }), 503);
  expectStatus(() => validateLabSeedAccess("BAD", verifiedAdmin, { corpusAdminEmails: "owner@example.com", enabled: "1" }), 400, "remint.seed");
  expectStatus(() => validateLabSeedAccess("lab-a", { email: "OWNER@EXAMPLE.COM", email_confirmed_at: null }, { corpusAdminEmails: "owner@example.com", enabled: "1" }), 403);
  assert(validateLabSeedAccess("lab-paired01", verifiedAdmin, { corpusAdminEmails: "owner@example.com", enabled: "1" }) === "lab-paired01");
});

Deno.test("rejection gate is before every credit ledger and job mutation", async () => {
  const source = await Deno.readTextFile(new URL("../create-deepclean-job/index.ts", import.meta.url));
  const gate = source.indexOf("validateLabSeedAccess(requestedLabSeed");
  const creditRead = source.indexOf('.from("creator_profiles")');
  const creditWrite = source.indexOf("deepclean_credits: profile.deepclean_credits - 1");
  const ledgerWrite = source.indexOf('.from("credit_ledger").insert');
  const jobWrite = source.indexOf('.from("deepclean_jobs").insert');
  assert(gate >= 0, "lab-seed gate call is missing");
  for (const [name, position] of Object.entries({ creditRead, creditWrite, ledgerWrite, jobWrite })) {
    assert(position > gate, `${name} occurs before the rejection gate`);
  }
});

function expectStatus(operation: () => unknown, status: number, includes?: string): void {
  try {
    operation();
  } catch (error) {
    assert(error instanceof LabSeedHttpError, "expected LabSeedHttpError");
    assert(error.status === status, `${error.status} !== ${status}`);
    if (includes) assert(error.message.includes(includes), `${error.message} lacks ${includes}`);
    return;
  }
  throw new Error(`expected status ${status}`);
}

function assert(condition: unknown, message = "Assertion failed"): asserts condition {
  if (!condition) throw new Error(message);
}
