import { authConfig } from "./config";
import { createBrowserClient } from "@supabase/ssr";
let client: ReturnType<typeof createBrowserClient> | undefined;
export function browserAuth() {
  const {url,key} = authConfig();
  return client ??= createBrowserClient(url, key);
}
