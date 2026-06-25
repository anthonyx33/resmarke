const PRIVACY_KEY = "resmarke:privacy-credits";
const DEEPCLEAN_KEY = "resmarke:deepclean-credits";

export type CreditSnapshot = {
  privacyCredits: number;
  deepCleanCredits: number;
  mode: "demo" | "supabase";
};

export function readLocalCredits(): CreditSnapshot {
  const privacyCredits = Number(localStorage.getItem(PRIVACY_KEY) ?? "3");
  const deepCleanCredits = Number(localStorage.getItem(DEEPCLEAN_KEY) ?? "0");
  return {
    privacyCredits: Number.isFinite(privacyCredits) ? privacyCredits : 3,
    deepCleanCredits: Number.isFinite(deepCleanCredits) ? deepCleanCredits : 0,
    mode: "demo"
  };
}

export function spendLocalPrivacyCredit(): CreditSnapshot {
  const snapshot = readLocalCredits();
  const next = Math.max(0, snapshot.privacyCredits - 1);
  localStorage.setItem(PRIVACY_KEY, String(next));
  return { ...snapshot, privacyCredits: next };
}

export function grantLocalPrivacyCredits(amount: number): CreditSnapshot {
  const snapshot = readLocalCredits();
  const next = snapshot.privacyCredits + amount;
  localStorage.setItem(PRIVACY_KEY, String(next));
  return { ...snapshot, privacyCredits: next };
}
