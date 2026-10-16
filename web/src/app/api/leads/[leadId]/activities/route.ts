import { proxyCrm } from "@/lib/api/crm-proxy";
export const runtime = "nodejs";
export async function GET(request: Request, context: { params: Promise<{ leadId: string }> }) { return proxyCrm(request, "activities", (await context.params).leadId); }
export async function POST(request: Request, context: { params: Promise<{ leadId: string }> }) { return proxyCrm(request, "activity", (await context.params).leadId); }
