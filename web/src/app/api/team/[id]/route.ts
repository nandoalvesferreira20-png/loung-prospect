import {proxyTeam} from "@/lib/api/team-proxy";
type Context={params:Promise<{id:string}>};
export async function PATCH(request:Request,context:Context){return proxyTeam(request,"team",(await context.params).id);}
export async function DELETE(request:Request,context:Context){return proxyTeam(request,"team",(await context.params).id);}
