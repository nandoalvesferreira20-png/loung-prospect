import { proxySdr } from "@/lib/api/sdr-proxy";
export const runtime = "nodejs";
export async function GET(request: Request, context: { params: Promise<{ leadId: string }> }) {
  return proxySdr(request, "history", (await context.params).leadId);
}
