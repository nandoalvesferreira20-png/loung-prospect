import {dashboardFetch} from "@/lib/api/dashboard-timing";
import {AuthConfigurationError} from "@/lib/auth/config";
import {accessFailure} from "@/lib/auth/access-errors";
import {isLocalRequest} from "@/lib/api/local-request";
export async function GET(request: Request){
  const headers: Record<string,string>={"Cache-Control":"no-store"};
  if(!isLocalRequest(request))return Response.json({detail:"Origem não autorizada."},{status:403,headers});
  try{
    const base=new URL(process.env.LOUNG_API_URL??"http://127.0.0.1:8000");
    if(base.protocol!=="http:" || !["localhost","127.0.0.1","[::1]"].includes(base.hostname) || base.username || base.password)return Response.json({detail:"LOUNG_API_URL deve apontar para o FastAPI local, sem credenciais na URL.",code:"BFF_CONFIG_INVALID"},{status:503,headers});
    const response=await dashboardFetch(new URL("/v1/session",base),{cache:"no-store",redirect:"error",signal:AbortSignal.timeout(8000)},headers);
    if(!response.ok){
      let diagnostic=null;
      try {diagnostic=accessFailure((await response.json()).code);}catch{/* Never forward raw upstream responses. */}
      if(diagnostic)return Response.json(diagnostic,{status:response.status,headers});
      const detail=response.status===403 ? "Login realizado, mas o usuário não pertence à organização autorizada. Solicite ao administrador o provisionamento da membership."
        :response.status===401 ? "Sessão expirada ou inválida. Entre novamente."
        :"Login realizado, mas não foi possível consultar o acesso no backend. Verifique o serviço FastAPI e sua configuração.";
      return Response.json({detail},{status:response.status,headers});
    }
    return Response.json(await response.json(),{headers});
  }catch(error){
    if(error instanceof Error && error.message==="SESSION_EXPIRED")return Response.json({detail:"Sessão ausente ou expirada. Entre novamente."},{status:401,headers});
    if(error instanceof Error && error.message==="AUTH_UNAVAILABLE")return Response.json({detail:"Serviço Supabase Auth indisponível. Verifique a conexão e tente novamente."},{status:503,headers});
    return Response.json({detail:error instanceof AuthConfigurationError ? error.message : "Não foi possível verificar o acesso. Verifique a conexão com o backend."},{status:503,headers});
  }
}
