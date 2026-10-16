import "server-only";
import { isLocalRequest } from "./local-request";
import { generateSchema, saveDraftSchema } from "./sdr-contracts";

export async function proxySdr(request: Request, operation: "generate" | "save" | "history" | "context", id?: string) {
  const headers = { "Cache-Control": "no-store" };
  const fail = (detail: string, status: number) => Response.json({ detail }, { status, headers });
  if (!isLocalRequest(request)) return fail("Acesso permitido apenas pela aplicação local.", 403);
  if (id !== undefined && (!/^[1-9]\d{0,14}$/.test(id) || !Number.isSafeInteger(Number(id)))) return fail("Lead inválido.", 422);
  try {
    const base = new URL(process.env.LOUNG_API_URL ?? "http://127.0.0.1:8000");
    if (base.protocol !== "http:" || !["127.0.0.1", "localhost", "[::1]"].includes(base.hostname) || base.username || base.password)
      return fail("Configuração da API local inválida.", 503);
    let body: string | undefined;
    if (operation === "generate" || operation === "save") {
      const raw = await request.text();
      if (raw.length > 12000) return fail("Solicitação excede o limite permitido.", 413);
      let value: unknown;
      try { value = JSON.parse(raw); } catch { return fail("Envie um corpo JSON válido.", 422); }
      const parsed = (operation === "generate" ? generateSchema : saveDraftSchema).safeParse(value);
      if (!parsed.success) return fail("Revise lead, destinatário, serviço e tamanho do texto.", 422);
      body = JSON.stringify(parsed.data);
    }
    const path = operation === "context" ? `leads/${id}` : operation === "history" ? `history/${id}` : operation === "save" ? "history" : "generate";
    const response = await fetch(new URL(`/v1/sdr/${path}`, base), {
      method: body ? "POST" : "GET", body,
      headers: body ? { "Content-Type": "application/json" } : undefined,
      cache: "no-store", redirect: "error", signal: AbortSignal.timeout(operation === "generate" ? 40000 : 15000),
    });
    if (!response.ok) {
      let detail = "Não foi possível concluir a operação SDR. Verifique o backend local.";
      try { const data = await response.json(); if (typeof data.detail === "string") detail = data.detail.slice(0, 500); } catch { /* Never expose upstream bodies. */ }
      return fail(detail, [403, 404, 409, 410, 422, 429, 502, 503].includes(response.status) ? response.status : 502);
    }
    return Response.json(await response.json(), { headers });
  } catch {
    return fail("A API local não respondeu a tempo. O texto foi preservado. Consulte o histórico antes de repetir um salvamento.", 503);
  }
}
