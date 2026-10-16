import "server-only";

export function isLocalRequest(request: Request): boolean {
  if (request.headers.get("sec-fetch-site") === "cross-site") return false;
  try {
    // Next can normalize request.url to localhost even when the browser uses
    // 127.0.0.1. Compare Origin to the actual Host, never forwarded headers.
    const incoming = new URL(request.url);
    const actual = new URL(
      `${incoming.protocol}//${request.headers.get("host") ?? incoming.host}`,
    );
    if (!["localhost", "127.0.0.1", "[::1]"].includes(actual.hostname))
      return false;
    const origin = request.headers.get("origin");
    return !origin || origin === actual.origin;
  } catch {
    return false;
  }
}
