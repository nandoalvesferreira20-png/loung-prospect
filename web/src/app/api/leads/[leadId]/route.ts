import { proxyCrm } from "@/lib/api/crm-proxy";
export const runtime = "nodejs";
export async function GET(request: Request, context: { params: Promise<{ leadId: string }> }) { return proxyCrm(request, "detail", (await context.params).leadId); }

import {proxyTeam} from "@/lib/api/team-proxy";
export async function PATCH(request:Request,{params}:{params:Promise<{leadId:string}>}){return proxyTeam(request,"leads",(await params).leadId);}
