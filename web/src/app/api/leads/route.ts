import { proxyRead } from "@/lib/api/proxy";
export const dynamic = "force-dynamic";
export async function GET(request: Request) {
  return proxyRead(request, "/v1/leads");
}
