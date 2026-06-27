const ownerAdminEmails = ["anthonyx33@proton.me"];

export const config = {
  supabaseUrl: import.meta.env.VITE_SUPABASE_URL ?? "",
  supabaseAnonKey: import.meta.env.VITE_SUPABASE_ANON_KEY ?? "",
  stripeTrialLink: import.meta.env.VITE_STRIPE_TRIAL_LINK ?? "",
  stripeProLink: import.meta.env.VITE_STRIPE_PRO_LINK ?? "",
  stripeProPlusLink: import.meta.env.VITE_STRIPE_PRO_PLUS_LINK ?? "",
  adminEmails: Array.from(
    new Set([
      ...ownerAdminEmails,
      ...String(import.meta.env.VITE_ADMIN_EMAILS ?? "")
        .split(",")
        .map((email) => email.trim().toLowerCase())
        .filter(Boolean)
    ])
  )
};

export const hasSupabaseConfig =
  config.supabaseUrl.length > 0 && config.supabaseAnonKey.length > 0;
