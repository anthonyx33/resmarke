export type GradeCacheRow = {
  grade_id: string;
  image_sha256: string;
  vendor: string;
  mode: string;
  ai_probability: number;
  deepfake_probability: number;
  verdict: string;
  top_source: string | null;
  sources: Record<string, number>;
  raw: Record<string, unknown>;
  mock: boolean;
  created_at: string;
};

export type CorpusGradePair = {
  gradeStatus: "PENDING" | "COMPLETE";
  ogGrade: Record<string, unknown> | null;
  remintGrade: Record<string, unknown> | null;
  delta: number | null;
  swapIndex: number | null;
  retentionIndex: number | null;
  qaFlag: boolean;
};

export async function cachedGradePair(
  client: SupabaseClient,
  input: { ogSha256: string; outputSha256: string; vendor: string; mode: string },
): Promise<CorpusGradePair> {
  const { data, error } = await client
    .from("grade_cache")
    .select("grade_id,image_sha256,vendor,mode,ai_probability,deepfake_probability,verdict,top_source,sources,raw,mock,created_at")
    .eq("vendor", input.vendor)
    .eq("mode", input.mode)
    .in("image_sha256", [input.ogSha256, input.outputSha256]);
  if (error) throw error;
  const rows = (data ?? []) as GradeCacheRow[];
  const og = rows.find((row) => row.image_sha256 === input.ogSha256) ?? null;
  const remint = rows.find((row) => row.image_sha256 === input.outputSha256) ?? null;
  return gradePairFromRows(og, remint);
}

export function gradePairFromRows(
  og: GradeCacheRow | null,
  remint: GradeCacheRow | null,
): CorpusGradePair {
  if (!og || !remint) {
    return {
      gradeStatus: "PENDING",
      ogGrade: null,
      remintGrade: null,
      delta: null,
      swapIndex: null,
      retentionIndex: null,
      qaFlag: false,
    };
  }
  const indexes = pairIndexes(remint.sources ?? {}, og.sources ?? {});
  const ogGrade = { ...og, swap_index: 0, retention_index: 0 };
  const remintGrade = {
    ...remint,
    swap_index: indexes.swapIndex,
    retention_index: indexes.retentionIndex,
  };
  return {
    gradeStatus: "COMPLETE",
    ogGrade,
    remintGrade,
    delta: round6(Number(og.ai_probability) - Number(remint.ai_probability)),
    swapIndex: indexes.swapIndex,
    retentionIndex: indexes.retentionIndex,
    qaFlag: remint.verdict === "BORDER",
  };
}

function pairIndexes(
  remintSources: Record<string, number>,
  ogSources: Record<string, number>,
): { swapIndex: number; retentionIndex: number } {
  const ogTopThree = new Set(
    Object.entries(ogSources).sort((left, right) => right[1] - left[1]).slice(0, 3)
      .map(([family]) => family),
  );
  const entries = Object.entries(remintSources).filter(([, value]) => value > 0);
  const total = entries.reduce((sum, [, value]) => sum + value, 0);
  if (total <= 0) return { swapIndex: 0, retentionIndex: 0 };
  const retained = entries.reduce(
    (sum, [family, value]) => sum + (ogTopThree.has(family) ? value : 0),
    0,
  );
  return {
    swapIndex: round6(clamp01((total - retained) / total)),
    retentionIndex: round6(clamp01(retained / total)),
  };
}

function round6(value: number): number {
  return Math.round(value * 1_000_000) / 1_000_000;
}

function clamp01(value: number): number {
  return Math.min(1, Math.max(0, value));
}
import type { SupabaseClient } from "https://esm.sh/@supabase/supabase-js@2.88.0";
