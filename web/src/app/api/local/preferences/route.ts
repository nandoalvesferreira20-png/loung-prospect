import { isLocalMode } from "@/lib/runtime-mode";
import { isLocalRequest } from "@/lib/api/local-request";
import { z } from "zod";

async function preferences(request: Request) {
  const headers = {"Cache-Control":"no-store"};
  if (!isLocalRequest(request)) return Response.json({detail:"Origem não autorizada."},{status:403,headers});
  try {
    if (!isLocalMode()) return Response.json({detail:"Recurso local."},{status:404,headers});
    const base = new URL(process.env.LOUNG_API_URL ?? "http://127.0.0.1:8000");
    if (base.protocol !== "http:" || !["localhost","127.0.0.1","[::1]"].includes(base.hostname) || base.username || base.password) throw new Error();
    let body: string | undefined;
    if (request.method === "PUT") {
      const raw = await request.text();
      if (raw.length > 16000) return Response.json({detail:"Solicitação extensa demais."},{status:413,headers});
      const parsed = z.object({values:z.object({displayName:z.string().trim().min(2).max(80),startPage:z.enum(["/","/prospeccao","/leads","/sdr","/pipeline"])})}).strict().safeParse(JSON.parse(raw));
      if (!parsed.success) return Response.json({detail:"Preferências inválidas."},{status:422,headers});
      body = JSON.stringify(parsed.data);
    }
    const response = await fetch(new URL("/v1/local/preferences",base),{method:request.method,body,headers:body ? {"Content-Type":"application/json"} : {},cache:"no-store",redirect:"error",signal:AbortSignal.timeout(8000)});
    if (!response.ok) return Response.json({detail:"Não foi possível acessar as preferências locais."},{status:response.status === 403 ? 403 : 503,headers});
    return Response.json(await response.json(),{headers});
  } catch {return Response.json({detail:"Preferências locais indisponíveis."},{status:503,headers});}
}
export const GET = preferences;
export const PUT = preferences;
