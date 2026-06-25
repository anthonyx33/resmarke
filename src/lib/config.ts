export const config = {
  supabaseUrl: import.meta.env.VITE_SUPABASE_URL ?? "",
  supabaseAnonKey: import.meta.env.VITE_SUPABASE_ANON_KEY ?? "",
  stripeTrialLink: import.meta.env.VITE_STRIPE_TRIAL_LINK ?? "",
  stripeProLink: import.meta.env.VITE_STRIPE_PRO_LINK ?? "",
  stripeProPlusLink: import.meta.env.VITE_STRIPE_PRO_PLUS_LINK ?? ""
};

export const hasSupabaseConfig =
  config.supabaseUrl.length > 0 && config.supabaseAnonKey.length > 0;
