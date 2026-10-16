import { proxyCrm } from "@/lib/api/crm-proxy";
export const runtime = "nodejs";
export async function POST(request: Request, context: { params: Promise<{ leadId: string }> }) { return proxyCrm(request, "schedule", (await context.params).leadId); }
