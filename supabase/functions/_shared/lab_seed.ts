/** Small dependency-free lab-seed gate shared only by edge validation/tests. */
export const LAB_SEED_PATTERN = /^lab-[a-z0-9]{1,32}$/;

export class LabSeedHttpError extends Error {
  constructor(message: string, readonly status: 400 | 403 | 503) {
    super(message);
    this.name = "LabSeedHttpError";
  }
}

export type LabSeedUser = {
  email?: string | null;
  email_confirmed_at?: string | null;
};

export type LabSeedEnvironment = {
  corpusAdminEmails?: string;
  enabled?: string;
};

/**
 * Exact gate order after authentication: absent -> allowlist -> flag -> regex.
 * The returned value is verbatim; this function never trims or normalizes it.
 */
export function validateLabSeedAccess(
  rawSeed: unknown,
  user: LabSeedUser,
  environment: LabSeedEnvironment,
): string | null {
  if (rawSeed === undefined) return null;

  const email = user.email?.trim().toLowerCase() ?? "";
  const allowlist = Array.from(new Set(
    (environment.corpusAdminEmails ?? "")
      .split(",")
      .map((value) => value.trim().toLowerCase())
      .filter(Boolean),
  ));
  if (!email || !user.email_confirmed_at || !allowlist.includes(email)) {
    throw new LabSeedHttpError("Corpus admin access is required for remint.seed.", 403);
  }
  if (environment.enabled !== "1") {
    throw new LabSeedHttpError("lab fixed seeds are not enabled", 503);
  }
  if (typeof rawSeed !== "string" || !LAB_SEED_PATTERN.test(rawSeed)) {
    throw new LabSeedHttpError("remint.seed must match ^lab-[a-z0-9]{1,32}$.", 400);
  }
  return rawSeed;
}
