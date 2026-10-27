import { authConfig } from "./config";
import { isLocalMode } from "@/lib/runtime-mode";
import "server-only";
import { createServerClient } from "@supabase/ssr";
import { cookies } from "next/headers";
export async function serverAuth() {
  const jar = await cookies();
  const {url,key} = authConfig();
  return createServerClient(url, key, { cookies: {
    getAll: () => jar.getAll(),
    setAll: (values) => { for (const {name,value,options} of values) jar.set(name,value,options); },
  }});
}
export async function backendHeaders(json = false): Promise<Record<string,string>> {
  const headers: Record<string,string> = json ? {"Content-Type":"application/json"} : {};
  if (isLocalMode()) return headers;
  const auth = await serverAuth();
  const {data:{user},error} = await auth.auth.getUser();
  if (error && (error.name === "AuthRetryableFetchError" || error.status === 0 || (error.status ?? 0) >= 500)) throw new Error("AUTH_UNAVAILABLE");
  if (error || !user) throw new Error("SESSION_EXPIRED");
  const {data:{session}} = await auth.auth.getSession();
  if (!session) throw new Error("SESSION_EXPIRED");
  headers.Authorization = `Bearer ${session.access_token}`;
  return headers;
}
