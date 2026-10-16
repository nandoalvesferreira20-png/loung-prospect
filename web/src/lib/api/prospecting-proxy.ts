import "server-only";
import { searchSchema, importSchema } from "./prospecting-contracts";
import { isLocalRequest } from "./local-request";

type Operation =
  "start" | "status" | "results" | "cancel" | "import" | "export";
export async function proxyProspecting(
  request: Request,
  operation: Operation,
  id?: string,
) {
  const headers = { "Cache-Control": "no-store" };
  const fail = (detail: string, status: number) =>
    Response.json({ detail }, { status, headers });
  if (!isLocalRequest(request))
    return fail("Acesso permitido apenas pela aplicação local.", 403);
  if (id !== undefined && !/^[0-9a-f]{32}$/.test(id))
    return fail("Identificador de pesquisa inválido.", 422);
  try {
    const base = new URL(process.env.LOUNG_API_URL ?? "http://127.0.0.1:8000");
    if (
      base.protocol !== "http:" ||
      !["127.0.0.1", "localhost", "[::1]"].includes(base.hostname) ||
      base.username ||
      base.password
    )
      return fail("Configuração da API local inválida.", 503);
    let body: string | undefined;
    if (operation === "start" || operation === "import") {
      const raw = await request.text();
      if (raw.length > 16000)
        return fail("Solicitação excede o tamanho permitido.", 413);
      let value: unknown;
      try {
        value = JSON.parse(raw);
      } catch {
        return fail("Envie um corpo JSON válido.", 422);
      }
      const parsed = (
        operation === "start" ? searchSchema : importSchema
      ).safeParse(value);
      if (!parsed.success)
        return fail(
          "Parâmetros inválidos. Revise nicho, localização, quantidade e seleção.",
          422,
        );
      body = JSON.stringify(parsed.data);
    }
    const suffix =
      operation === "results"
        ? "/results"
        : operation === "cancel"
          ? "/cancel"
          : operation === "export"
            ? "/export"
            : "";
    const path =
      operation === "import"
        ? "/v1/leads/import"
        : `/v1/prospecting/search${id ? `/${id}` : ""}${suffix}`;
    const url = new URL(path, base),
      incoming = new URL(request.url).searchParams;
    if (operation === "results") {
      for (const [key, defaultValue, max] of [
        ["page", "1", 1000000],
        ["pageSize", "20", 100],
      ] as const) {
        const value = incoming.get(key) ?? defaultValue;
        if (!/^\d+$/.test(value) || Number(value) < 1 || Number(value) > max)
          return fail("Paginação inválida.", 422);
        url.searchParams.set(key, value);
      }
    }
    if (operation === "export") {
      const format = incoming.get("format") ?? "csv";
      if (!["csv", "xlsx"].includes(format))
        return fail("Formato de exportação inválido.", 422);
      url.searchParams.set("format", format);
    }
    const response = await fetch(url, {
      method: ["start", "import", "cancel"].includes(operation)
        ? "POST"
        : "GET",
      body,
      headers: body ? { "Content-Type": "application/json" } : undefined,
      cache: "no-store",
      redirect: "error",
      signal: AbortSignal.timeout(operation === "import" ? 30000 : 10000),
    });
    if (!response.ok) {
      let detail = "Falha ao executar a operação. Verifique o backend local.";
      try {
        const payload = await response.json();
        if (typeof payload.detail === "string")
          detail = payload.detail.slice(0, 500);
      } catch {
        /* No raw upstream response is exposed. */
      }
      return fail(
        detail,
        [403, 404, 409, 422, 429, 503].includes(response.status)
          ? response.status
          : 502,
      );
    }
    if (operation === "export") {
      const format = url.searchParams.get("format");
      return new Response(await response.arrayBuffer(), {
        headers: {
          ...headers,
          "Content-Type":
            format === "csv"
              ? "text/csv; charset=utf-8"
              : "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
          "Content-Disposition": `attachment; filename="prospeccao-${id}.${format}"`,
        },
      });
    }
    return Response.json(await response.json(), {
      status: response.status,
      headers,
    });
  } catch {
    return fail(
      "API local indisponível. Verifique o backend e tente novamente. Em caso de falha ao salvar, consulte a Carteira antes de repetir.",
      503,
    );
  }
}
