import "server-only";
import {z} from "zod";
import {backendHeaders} from "@/lib/auth/server";
import {isLocalRequest} from "./local-request";

const fields={empresa:z.string().trim().min(1).max(200),cidade:z.string().max(500),segmento:z.string().max(500),telefone:z.string().max(500),whatsapp:z.string().max(500),email:z.string().max(500),site:z.string().max(500),endereco:z.string().max(500)};
export async function proxyTeam(request:Request,resource:"team"|"activities"|"leads"|"lead-edit",id?:string){
  const headers={"Cache-Control":"no-store"};
  const fail=(detail:string,status:number)=>Response.json({detail},{status,headers});
  if(!isLocalRequest(request))return fail("Origem não autorizada.",403);
  if(id && !(resource==="team" ? z.string().uuid().safeParse(id).success : /^[1-9]\d{0,14}$/.test(id)))return fail("Identificador inválido.",422);
  try{
    const base=new URL(process.env.LOUNG_API_URL??"http://127.0.0.1:8000");
    if(base.protocol!=="http:" || !["localhost","127.0.0.1","[::1]"].includes(base.hostname) || base.username || base.password)return fail("Configuração da API inválida.",503);
    const url=new URL(resource==="activities"?"/v1/organization/activities":resource==="lead-edit"?`/v1/leads/${id}/edit`:`/v1/${resource}${id?`/${id}`:""}`,base);
    if(resource==="activities")for(const key of ["before","limit"]){const value=new URL(request.url).searchParams.get(key);if(value && /^\d{1,19}$/.test(value))url.searchParams.set(key,value);}
    let body:string|undefined;
    if(request.method==="POST" || request.method==="PATCH"){
      const raw=await request.text();if(raw.length>16000)return fail("Solicitação extensa demais.",413);
      let value:unknown;try{value=JSON.parse(raw);}catch{return fail("JSON inválido.",422);}
      const schema=resource==="team"?z.object({role:z.enum(["owner","admin","member"])}).strict():request.method==="POST"?z.object(fields).strict():z.object({...fields,observacoes:z.string().max(4000),revision:z.string().regex(/^[a-f0-9]{64}$/)}).strict();
      const parsed=schema.safeParse(value);if(!parsed.success)return fail("Revise os campos informados.",422);
      body=JSON.stringify(parsed.data);
    }
    const response=await fetch(url,{method:request.method,body,headers:await backendHeaders(!!body),cache:"no-store",redirect:"error",signal:AbortSignal.timeout(15000)});
    if(!response.ok){
      const messages:Record<number,string>={401:"Sessão expirada. Entre novamente.",403:"Operação não autorizada ou escrita desabilitada.",404:"Registro não encontrado.",409:"Os dados mudaram ou a operação viola uma regra de acesso. Atualize antes de repetir.",422:"Revise os campos informados."};
      return fail(messages[response.status]??"Não foi possível concluir a operação.",[401,403,404,409,422,503].includes(response.status)?response.status:502);
    }
    return Response.json(await response.json(),{headers});
  }catch(error){return fail(error instanceof Error && error.message==="SESSION_EXPIRED"?"Sessão expirada.":"Serviço indisponível. Confira os dados antes de repetir.",error instanceof Error && error.message==="SESSION_EXPIRED"?401:503);}
}
