export async function throwSupabaseFunctionError(error: unknown): Promise<never> {
  const context = errorContext(error);
  if (context) {
    const text = await context.clone().text().catch(() => "");
    const message = parseErrorMessage(text) || context.statusText || "Edge Function failed.";
    throw new Error(message);
  }

  if (error instanceof Error) throw error;
  throw new Error("Edge Function failed.");
}

function errorContext(error: unknown): Response | null {
  if (!error || typeof error !== "object") return null;
  const maybeContext = (error as { context?: unknown }).context;
  return maybeContext instanceof Response ? maybeContext : null;
}

function parseErrorMessage(text: string): string {
  if (!text) return "";
  try {
    const parsed = JSON.parse(text) as { error?: unknown; message?: unknown };
    if (typeof parsed.error === "string") return parsed.error;
    if (typeof parsed.message === "string") return parsed.message;
  } catch {
    return text.slice(0, 300);
  }
  return text.slice(0, 300);
}
