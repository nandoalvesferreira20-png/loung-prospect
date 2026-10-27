import {proxyTeam} from "@/lib/api/team-proxy";
export const GET=(request:Request)=>proxyTeam(request,"team");
