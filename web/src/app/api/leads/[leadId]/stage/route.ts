import { proxyCrm } from "@/lib/api/crm-proxy";
export const runtime = "nodejs";
export async function PATCH(request: Request, context: { params: Promise<{ leadId: string }> }) { return proxyCrm(request, "stage", (await context.params).leadId); }
