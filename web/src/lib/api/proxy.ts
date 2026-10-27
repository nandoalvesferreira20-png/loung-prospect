import { dashboardFetch } from "./dashboard-timing";
import "server-only";
import { isLocalRequest } from "./local-request";

// Server-side only. Never forward user-supplied URLs, cookies or credentials.
export async function proxyRead(
  request: Request,
  path: "/v1/leads" | "/v1/overview",
) {
  const headers: Record<string,string> = {"Cache-Control":"no-store"};
  if (!isLocalRequest(request)) {
    return Response.json(
      { detail: "Acesso permitido apenas pela aplicação local." },
      { status: 403 },
    );
  }
  try {
    const base = new URL(process.env.LOUNG_API_URL ?? "http://127.0.0.1:8000");
    if (
      base.protocol !== "http:" ||
      !["127.0.0.1", "localhost", "[::1]"].includes(base.hostname) ||
      base.username ||
      base.password
    ) {
      throw new Error("Backend must be local in this phase");
    }
    const url = new URL(path, base);
    if (path === "/v1/overview") {
      const tz = new URL(request.url).searchParams.get("tz");
      if (tz && tz.length <= 100) url.searchParams.set("tz",tz);
    }
    if (path === "/v1/leads") {
      const params = new URL(request.url).searchParams;
      for (const key of ["q", "stage", "page", "pageSize"]) {
        const value = params.get(key);
        if (value !== null) url.searchParams.set(key, value);
      }
    }
    const response = await dashboardFetch(url, {
      cache: "no-store",
      signal: AbortSignal.timeout(5000),
      redirect: "error",
    }, headers);
    if (!response.ok) {
      return Response.json(
        {
          detail:
            response.status === 422
              ? "Filtros inválidos. Revise os valores informados."
              : "Não foi possível consultar a base de leads. Verifique o backend local.",
        },
        { status: [401,403,422,503].includes(response.status) ? response.status : 502, headers },
      );
    }
    return Response.json(await response.json(), {
      headers,
    });
  } catch (error) {
    if (error instanceof Error && error.message === "SESSION_EXPIRED") return Response.json({detail:"Sessao expirada. Entre novamente."},{status:401});
    return Response.json(
      {
        detail:
          "API local indisponível. Inicie o backend FastAPI e tente novamente.",
        code: "API_UNAVAILABLE",
      },
      { status: 503 },
    );
  }
}
