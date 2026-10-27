import { createServerClient } from "@supabase/ssr";
import { NextRequest, NextResponse } from "next/server";
import { authConfig, AuthConfigurationError } from "@/lib/auth/config";
import { isLocalMode } from "@/lib/runtime-mode";
import { isLocalRequest } from "@/lib/api/local-request";
export async function proxy(request: NextRequest) {
  const started = performance.now();
  const correlationId = crypto.randomUUID();
  let stage = "configuration";
  try {
    if (isLocalMode()) {
      const peers = request.headers.get("x-forwarded-for")?.split(",").map(value => value.trim()) ?? [];
      if (!isLocalRequest(request) || request.headers.has("forwarded") || peers.some(value => !["127.0.0.1", "::1", "::ffff:127.0.0.1"].includes(value))) {
        return NextResponse.json({detail:"Acesso permitido somente na aplicação local."},{status:403});
      }
      if (["/login", "/recuperar-senha", "/atualizar-senha", "/auth/confirm", "/configuracoes/equipe", "/configuracoes/atividades"].includes(request.nextUrl.pathname)) {
        return NextResponse.redirect(new URL("/",request.url));
      }
      if (request.nextUrl.pathname.startsWith("/api/team") || request.nextUrl.pathname.startsWith("/api/organization")) {
        return NextResponse.json({detail:"Recurso disponível somente no modo SaaS."},{status:404});
      }
      const response = NextResponse.next();
      response.headers.set("Cache-Control", "no-store");
      return response;
    }
  } catch {
    return NextResponse.json({detail:"Modo operacional inválido para este ambiente."},{status:503});
  }
  const path = request.nextUrl.pathname;
  const publicRoute = ["/login","/recuperar-senha","/atualizar-senha","/auth/confirm"].includes(path);
  let response = NextResponse.next({request});
  try {
    const {url,key} = authConfig();
    const auth = createServerClient(url,key,{cookies:{
      getAll: () => request.cookies.getAll(),
      setAll: (values) => {
        for (const {name,value} of values) request.cookies.set(name,value);
        response = NextResponse.next({request});
        for (const {name,value,options} of values) response.cookies.set(name,value,options);
      },
    }});
    stage = "supabase_get_user";
    const {data:{user},error} = await auth.auth.getUser();
    // The SDK returns network/service errors instead of throwing them. These
    // do not prove expiration and must not send a valid session back to login.
    if (error && (error.name === "AuthRetryableFetchError" || error.status === 0 || error.status === 429 || (error.status ?? 0) >= 500)) {
      throw error;
    }
    if (user || publicRoute) {
      response.headers.set("Cache-Control","no-store");
      response.headers.set("X-Loung-Proxy-Auth-Ms",(performance.now()-started).toFixed(1));
      return response;
    }
  } catch (error) {
    const name = error instanceof Error ? error.name : (error as {name?:string} | null)?.name;
    const errorType = ["AuthConfigurationError","AuthRetryableFetchError","AuthApiError","TypeError","Error"].includes(name ?? "") ? name : "Error";
    console.warn(JSON.stringify({component:"next_proxy",stage,http_status:503,error_type:errorType,correlation_id:correlationId,duration_ms:Math.round(performance.now()-started)}));
    if (publicRoute) return response; // The form can show the specific configuration error.
    return NextResponse.json({detail:error instanceof AuthConfigurationError ? error.message : "Serviço de autenticação indisponível. Tente novamente."},{status:503,headers:{"Cache-Control":"no-store","X-Request-Id":correlationId}});
  }
  const denied = path.startsWith("/api/")
    ? NextResponse.json({detail:"Sessão ausente ou expirada. Entre novamente."},{status:401})
    : NextResponse.redirect(new URL("/login?expired=1",request.url));
  for (const cookie of response.cookies.getAll()) denied.cookies.set(cookie);
  denied.headers.set("Cache-Control","no-store");
  return denied;
}
export const config = {matcher:["/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|ico)$).*)"]};
