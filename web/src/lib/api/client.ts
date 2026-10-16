import type { ApiResult, ProspectApi } from "./contracts";
export const connectionMessage = "Verifique se a API local está em execução para consultar os dados.";
export async function readApi<T>(
  path: string,
  signal?: AbortSignal,
  init?: RequestInit,
): Promise<ApiResult<T>> {
  try {
    const response = await fetch(path, { ...init, signal, cache: "no-store" });
    const body = await response.json();
    if (!response.ok)
      return {
        status: body.code === "API_UNAVAILABLE" ? "not-connected" : "error",
        message:
          typeof body.detail === "string"
            ? body.detail
            : "Não foi possível carregar os dados.",
      };
    return { status: "ready", data: body as T };
  } catch (error) {
    if (signal?.aborted) throw error;
    return {
      status: "error",
      message:
        "Falha de conexão. Verifique o servidor local e tente novamente.",
    };
  }
}
export const prospectApi: ProspectApi = {
  listLeads: (filters = {}, signal) => {
    const params = new URLSearchParams();
    for (const [key, value] of Object.entries(filters))
      if (value !== undefined && value !== "") params.set(key, String(value));
    return readApi(`/api/leads?${params}`, signal);
  },
  overview: (signal) => readApi("/api/overview", signal),
  prospect: (request) =>
    readApi("/api/prospecting/search", undefined, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(request),
    }),
  generateDraft: (request) => readApi("/api/sdr/generate", undefined, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(request),
  }),
};
