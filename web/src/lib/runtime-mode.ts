// Server-side operational mode. Never infer an auth bypass from browser state.
export function isLocalMode(): boolean {
  const mode = process.env.LOUNG_AUTH_MODE ?? "local";
  if (mode !== "local" && mode !== "saas") throw new Error("LOUNG_AUTH_MODE deve ser local ou saas.");
  if (mode === "local" && ["VERCEL", "RENDER", "RAILWAY_ENVIRONMENT", "WEBSITE_INSTANCE_ID", "K_SERVICE", "FLY_APP_NAME", "AWS_EXECUTION_ENV"].some(key => process.env[key])) {
    throw new Error("Modo sem login proibido em hospedagem pública.");
  }
  return mode === "local";
}
