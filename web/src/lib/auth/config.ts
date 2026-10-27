export class AuthConfigurationError extends Error {
  constructor() {
    super("Autenticação não configurada corretamente. Verifique web/.env.local: NEXT_PUBLIC_SUPABASE_URL e NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY (ou NEXT_PUBLIC_SUPABASE_ANON_KEY). Reinicie o Next.js; com npm start, refaça também o build.");
    this.name = "AuthConfigurationError";
  }
}
export function resolveAuthConfig(url?: string, publishableKey?: string, anonKey?: string) {
  const key = publishableKey?.trim() || anonKey?.trim();
  try {
    const parsed = new URL(url?.trim() || "");
    if (!key || !["https:", "http:"].includes(parsed.protocol) || parsed.username || parsed.password || parsed.search || parsed.hash || (parsed.pathname !== "/" && parsed.pathname !== "") || key.startsWith("sb_secret_")) throw new Error();
    if (parsed.protocol === "http:" && !["localhost", "127.0.0.1", "[::1]"].includes(parsed.hostname)) throw new Error();
    return { url: parsed.origin, key };
  } catch { throw new AuthConfigurationError(); }
}
export function authConfig() {
  // Direct references are required for Next.js browser build-time substitution.
  return resolveAuthConfig(process.env.NEXT_PUBLIC_SUPABASE_URL,
    process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY);
}
