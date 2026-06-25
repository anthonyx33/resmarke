import { createClient } from "https://esm.sh/@supabase/supabase-js@2.88.0";

export function adminClient() {
  const url = Deno.env.get("SUPABASE_URL");
  const key = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");
  if (!url || !key) throw new Error("Missing Supabase service configuration.");
  return createClient(url, key, {
    auth: {
      autoRefreshToken: false,
      persistSession: false
    }
  });
}

export async function userFromRequest(request: Request) {
  const authorization = request.headers.get("authorization") ?? "";
  const token = authorization.replace(/^Bearer\s+/i, "");
  if (!token) throw new Error("Missing bearer token.");

  const client = adminClient();
  const { data, error } = await client.auth.getUser(token);
  if (error || !data.user) throw new Error("Invalid bearer token.");
  return { client, user: data.user };
}
