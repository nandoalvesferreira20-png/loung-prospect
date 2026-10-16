import "server-only";
import { isLocalRequest } from "./local-request";
import { activitySchema, followupSchema, stageSchema } from "./crm-contracts";
type Operation = "pipeline" | "detail" | "stage" | "activities" | "activity" | "schedule" | "followup" | "followups" | "metrics";
export async function proxyCrm(request: Request, operation: Operation, id?: string) {
  const headers = {"Cache-Control":"no-store"};
  const fail = (detail: string, status: number) => Response.json({detail},{status,headers});
  if (!isLocalRequest(request)) return fail("Utilize a aplicação local.",403);
  if (id !== undefined && !/^[1-9]\d{0,14}$/.test(id)) return fail("Identificador inválido.",422);
  try {
    const base = new URL(process.env.LOUNG_API_URL ?? "http://127.0.0.1:8000");
    if (base.protocol !== "http:" || !["127.0.0.1","localhost","[::1]"].includes(base.hostname) || base.username || base.password) return fail("Configuração da API local inválida.",503);
    const routes: Record<Operation,string> = {
      pipeline:"/v1/pipeline", detail:`/v1/crm/leads/${id}`,stage:`/v1/leads/${id}/stage`,
      activities:`/v1/leads/${id}/activities`,activity:`/v1/leads/${id}/activities`,
      schedule:`/v1/leads/${id}/followups`,followup:`/v1/followups/${id}`,followups:"/v1/followups",metrics:"/v1/dashboard/commercial",
    };
    const url = new URL(routes[operation],base);
    const incoming = new URL(request.url).searchParams;
    for (const key of ["q","niche","stage","offset","limit","tz","scope"]) {
      const value = incoming.get(key);
      if (value !== null) { if (value.length > 200) return fail("Filtro excede o limite permitido.",422); url.searchParams.set(key,value); }
    }
    let body: string | undefined;
    if (["stage","activity","schedule","followup"].includes(operation)) {
      const raw = await request.text();
      if (raw.length > 16000) return fail("Solicitação muito extensa.",413);
      let value: unknown;
      try { value = JSON.parse(raw); } catch { return fail("JSON inválido.",422); }
      const parsed = (operation === "stage" ? stageSchema : operation === "activity" ? activitySchema : followupSchema).safeParse(value);
      if (!parsed.success) return fail("Revise etapa, confirmação, data com fuso e tamanho dos campos.",422);
      body = JSON.stringify(parsed.data);
    }
    const response = await fetch(url,{ method:operation === "stage" || operation === "followup" ? "PATCH" : body ? "POST" : "GET", body,
      headers:body ? {"Content-Type":"application/json"} : undefined, cache:"no-store",redirect:"error",signal:AbortSignal.timeout(20000) });
    if (!response.ok) {
      let detail = "Não foi possível concluir a operação comercial.";
      try {const data = await response.json(); if (typeof data.detail === "string") detail = data.detail.slice(0,500);} catch { /* Keep errors sanitized. */ }
      return fail(detail,[403,404,409,422,503].includes(response.status) ? response.status : 502);
    }
    return Response.json(await response.json(),{headers});
  } catch {
    return fail("API local indisponível. O texto foi preservado. Atualize os dados antes de repetir uma alteração.",503);
  }
}
