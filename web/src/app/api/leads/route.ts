import { proxyRead } from "@/lib/api/proxy";
import {proxyTeam} from "@/lib/api/team-proxy";
export const POST=(request:Request)=>proxyTeam(request,"leads");
export const dynamic = "force-dynamic";
export async function GET(request: Request) {
  return proxyRead(request, "/v1/leads");
}
