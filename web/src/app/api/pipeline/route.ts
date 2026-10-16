import { proxyCrm } from "@/lib/api/crm-proxy";
export const runtime = "nodejs";
export async function GET(request: Request) { return proxyCrm(request, "pipeline"); }
