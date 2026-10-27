import "server-only";
import { backendHeaders } from "@/lib/auth/server";

// Fixed numeric metrics only. Do not forward upstream header text or user data.
export async function dashboardFetch(url: URL, init: RequestInit, headers: Record<string, string>, json = false) {
  const started = performance.now();
  const auth = await backendHeaders(json);
  const authorized = performance.now();
  const response = await fetch(url, { ...init, headers: auth });
  const received = performance.now();
  const timings = [
    `bff_auth;dur=${(authorized - started).toFixed(1)}`,
    `bff_upstream;dur=${(received - authorized).toFixed(1)}`,
  ];
  for (const part of (response.headers.get("Server-Timing") ?? "").split(",")) {
    const match = part.trim().match(/^(jwt|membership|handler|fastapi|db_open|db_connect|db_metadata|db_query);dur=(\d+(?:\.\d+)?)$/);
    if (match) timings.push(`api_${match[1]};dur=${match[2]}`);
  }
  headers["Server-Timing"] = timings.join(", ");
  return response;
}
