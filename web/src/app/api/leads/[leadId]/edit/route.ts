import {proxyTeam} from "@/lib/api/team-proxy";
export async function GET(request:Request,{params}:{params:Promise<{leadId:string}>}){return proxyTeam(request,"lead-edit",(await params).leadId);}
