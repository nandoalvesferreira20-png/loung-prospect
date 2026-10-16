import { proxySdr } from "@/lib/api/sdr-proxy";
export const runtime = "nodejs";
export async function GET(request: Request, context: { params: Promise<{ leadId: string }> }) {
  return proxySdr(request, "context", (await context.params).leadId);
}
