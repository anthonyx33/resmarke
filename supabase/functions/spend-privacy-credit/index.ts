import { corsHeaders, jsonResponse } from "../_shared/cors.ts";
import { userFromRequest } from "../_shared/supabase.ts";

Deno.serve(async (request) => {
  if (request.method === "OPTIONS") return new Response("ok", { headers: corsHeaders });
  if (request.method !== "POST") return jsonResponse({ error: "Method not allowed" }, 405);

  try {
    const { client, user } = await userFromRequest(request);
    const body = (await request.json()) as { amount?: number };
    const amount = Math.max(1, Math.min(25, Number(body.amount ?? 1)));

    const { data: profile, error: profileError } = await client
      .from("creator_profiles")
      .select("privacy_exports_remaining, deepclean_credits")
      .eq("user_id", user.id)
      .single();

    if (profileError) throw profileError;
    if (!profile || profile.privacy_exports_remaining < amount) {
      return jsonResponse({ error: "No Privacy-Max credits available." }, 402);
    }

    const nextPrivacyCredits = profile.privacy_exports_remaining - amount;
    const { error: updateError } = await client
      .from("creator_profiles")
      .update({
        privacy_exports_remaining: nextPrivacyCredits,
        updated_at: new Date().toISOString()
      })
      .eq("user_id", user.id);
    if (updateError) throw updateError;

    await client.from("credit_ledger").insert({
      user_id: user.id,
      kind: "privacy_spend",
      amount: -amount,
      balance_after: nextPrivacyCredits
    });

    return jsonResponse({
      privacyCredits: nextPrivacyCredits,
      deepCleanCredits: profile.deepclean_credits
    });
  } catch (error) {
    return jsonResponse(
      { error: error instanceof Error ? error.message : "Could not spend credit." },
      500
    );
  }
});
