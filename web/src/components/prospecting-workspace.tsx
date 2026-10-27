"use client";
import { useEffect, useRef, useState, useSyncExternalStore } from "react";
import { useForm, useWatch } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import Link from "next/link";
import {
  Search,
  LoaderCircle,
  X,
  Download,
  Save,
  RefreshCw,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";
import {
  searchSchema,
  type SearchInput,
  type SearchJob,
  type SearchResults,
} from "@/lib/api/prospecting-contracts";
import { PageHeader, EmptyState } from "./shared";
import { Card, CardHeader, CardTitle, CardContent } from "./ui/card";
import { Button } from "./ui/button";

const sessionKey = "loung:prospecting:active";
function subscribe(listener: () => void) {
  window.addEventListener("prospecting-session", listener);
  return () => window.removeEventListener("prospecting-session", listener);
}
function sessionId() {
  try {
    return sessionStorage.getItem(sessionKey) ?? "";
  } catch {
    return "";
  }
}
async function json<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, { ...init, cache: "no-store" });
  const payload = await response.json();
  if (!response.ok)
    throw new Error(
      typeof payload.detail === "string"
        ? payload.detail
        : "Não foi possível executar a operação.",
    );
  return payload as T;
}
const terminal = (job: SearchJob | null) =>
  !!job && ["completed", "failed", "cancelled"].includes(job.status);
const labels = {
  pending: "Aguardando",
  running: "Pesquisando",
  completed: "Concluída",
  failed: "Interrompida",
  cancelled: "Cancelada",
};

export function ProspectingWorkspace() {
  const storedId = useSyncExternalStore(subscribe, sessionId, () => "");
  const [localId, setLocalId] = useState<string | null>(null);
  const jobId = localId ?? storedId;
  const [job, setJob] = useState<SearchJob | null>(null);
  const [results, setResults] = useState<SearchResults | null>(null);
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [notice, setNotice] = useState("");
  const [pollError, setPollError] = useState("");
  const [resultsError, setResultsError] = useState("");
  const [operation, setOperation] = useState("");
  const [revision, setRevision] = useState(0);
  const initializedSearch = useRef("");
  const latestJob = useRef<SearchJob | null>(null);
  const current = job?.id === jobId ? job : null;
  const resultsReady = !!current;
  const active = !!jobId && !terminal(current);
  const busy = !!operation;
  const {
    register,
    handleSubmit,
    control,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<SearchInput, unknown, z.output<typeof searchSchema>>({
    resolver: zodResolver(searchSchema),
    defaultValues: {
      niche: "",
      location: "",
      quantity: 20,
      neighborhood: "",
      onlyWithoutWebsite: false,
      minScore: 60,
    },
  });
  const onlyWithoutWebsite = useWatch({ control, name: "onlyWithoutWebsite" });
  function remember(id: string) {
    setLocalId(id);
    try {
      if (id) sessionStorage.setItem(sessionKey, id);
      else sessionStorage.removeItem(sessionKey);
      window.dispatchEvent(new Event("prospecting-session"));
    } catch {
      /* The current view still works without session storage. */
    }
  }

  useEffect(() => {
    if (!jobId) return;
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout> | undefined;
    let failures = 0;
    async function poll() {
      try {
        const response = await fetch(`/api/prospecting/search/${jobId}`, {
          signal: controller.signal,
          cache: "no-store",
        });
        const payload = await response.json();
        if (controller.signal.aborted) return;
        if (!response.ok) {
          if (response.status === 404) {
            setLocalId("");
            try {
              sessionStorage.removeItem(sessionKey);
            } catch {
              /* optional */
            }
          }
          throw new Error(
            payload.detail || "Não foi possível acompanhar a pesquisa.",
          );
        }
        const next = payload as SearchJob;
        if (initializedSearch.current !== next.id) {
          reset(next.query);
          initializedSearch.current = next.id;
        }
        latestJob.current = next;
        setJob(next);
        setPollError("");
        failures = 0;
        if (!terminal(next)) timer = setTimeout(poll, 1500);
      } catch (error) {
        if (!controller.signal.aborted) {
          setPollError(
            error instanceof Error ? error.message : "Falha de conexão.",
          );
          if (++failures < 3) timer = setTimeout(poll, 5000);
        }
      }
    }
    void poll();
    return () => {
      controller.abort();
      if (timer) clearTimeout(timer);
    };
  }, [jobId, revision, reset]);

  useEffect(() => {
    if (!jobId || !resultsReady) return;
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout> | undefined;
    let failures = 0;
    async function load() {
      const snapshot = latestJob.current;
      try {
        const data = await json<SearchResults>(
          `/api/prospecting/search/${jobId}/results?page=${page}&pageSize=20`,
          { signal: controller.signal },
        );
        if (!controller.signal.aborted) {
          setResults(data);
          setResultsError("");
          failures = 0;
          // Finish this request before starting another. If it began while
          // running, fetch again even when the status became terminal meanwhile.
          if (!terminal(snapshot)) timer = setTimeout(load, 1500);
        }
      } catch (error) {
        if (!controller.signal.aborted) {
          setResultsError(error instanceof Error ? error.message : "Falha ao carregar resultados.");
          if (++failures < 3) timer = setTimeout(load, 5000);
        }
      }
    }
    void load();
    return () => {controller.abort();if (timer) clearTimeout(timer);};
  }, [jobId, resultsReady, page, revision]);

  async function start(values: z.output<typeof searchSchema>) {
    if (
      selected.size &&
      !window.confirm(
        "Iniciar outra pesquisa? A seleção atual será limpa. Os resultados anteriores permanecem temporariamente no backend.",
      )
    )
      return;
    setNotice("");
    try {
      const next = await json<SearchJob>("/api/prospecting/search", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(values),
      });
      remember(next.id);
      initializedSearch.current = next.id;
      latestJob.current = next;
      setJob(next);
      setResults(null);
      setSelected(new Set());
      setPage(1);
      setPollError("");
      setResultsError("");
    } catch (error) {
      setNotice(
        error instanceof Error
          ? error.message
          : "Não foi possível iniciar a pesquisa.",
      );
    }
  }
  async function cancel() {
    setOperation("cancel");
    try {
      setJob(
        await json<SearchJob>(`/api/prospecting/search/${jobId}/cancel`, {
          method: "POST",
        }),
      );
      setRevision((v) => v + 1);
    } catch (error) {
      setNotice((error as Error).message);
    } finally {
      setOperation("");
    }
  }
  async function save() {
    setOperation("save");
    setNotice("");
    try {
      const saved = await json<{ inserted: number; duplicates: number }>(
        "/api/leads/import",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            searchId: jobId,
            resultIds: Array.from(selected),
          }),
        },
      );
      setNotice(
        `${saved.inserted} lead(s) salvo(s). ${saved.duplicates} duplicado(s) preservado(s) sem alteração.`,
      );
      setSelected(new Set());
      setRevision((v) => v + 1);
    } catch (error) {
      setNotice((error as Error).message);
    } finally {
      setOperation("");
    }
  }
  async function download(format: "csv" | "xlsx") {
    setOperation(format);
    try {
      const response = await fetch(
        `/api/prospecting/search/${jobId}/export?format=${format}`,
        { cache: "no-store" },
      );
      if (!response.ok) {
        const payload = await response.json();
        throw new Error(payload.detail || "Falha ao exportar.");
      }
      const url = URL.createObjectURL(await response.blob());
      const link = document.createElement("a");
      link.href = url;
      link.download = `prospeccao-${jobId}.${format}`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
      setNotice("Exportação concluída.");
    } catch (error) {
      setNotice((error as Error).message);
    } finally {
      setOperation("");
    }
  }
  function select(id: number) {
    setSelected((previous) => {
      const next = new Set(previous);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }
  function changePage(next: number) {
    setPage(next);
    setResults(null);
  }
  const selectable = results?.items.filter((row) => !row.alreadySaved) ?? [];
  return (
    <>
      <PageHeader
        eyebrow="DESCOBERTA"
        title="Encontre seu próximo cliente"
        description="Pesquise empresas, revise os resultados e salve somente os leads que fizerem sentido para sua carteira."
      />
      <Card>
        <CardHeader>
          <CardTitle>Critérios da pesquisa</CardTitle>
        </CardHeader>
        <CardContent>
          <form
            noValidate
            onSubmit={(event) => {
              void handleSubmit(start)(event);
            }}
            className="space-y-5"
          >
            <fieldset
              disabled={active || busy || isSubmitting}
              className="grid gap-4 md:grid-cols-2 xl:grid-cols-4 disabled:opacity-60"
            >
              <label>
                Nicho ou segmento
                <input
                  aria-label="Nicho ou segmento"
                  {...register("niche")}
                  className="field mt-2"
                  placeholder="Ex.: clínicas odontológicas"
                  aria-invalid={!!errors.niche}
                />
                {errors.niche && (
                  <span className="mt-1 block text-xs text-red-600">
                    {errors.niche.message}
                  </span>
                )}
              </label>
              <label>
                Localização
                <input
                  aria-label="Localização"
                  {...register("location")}
                  className="field mt-2"
                  placeholder="Ex.: São Paulo, SP"
                  aria-invalid={!!errors.location}
                />
                {errors.location && (
                  <span className="mt-1 block text-xs text-red-600">
                    {errors.location.message}
                  </span>
                )}
              </label>
              <label>
                Bairro (opcional)
                <input
                  {...register("neighborhood")}
                  className="field mt-2"
                  maxLength={120}
                />
              </label>
              <label>
                Quantidade máxima
                <input
                  aria-label="Quantidade máxima"
                  {...register("quantity", { valueAsNumber: true })}
                  type="number"
                  min={1}
                  max={100}
                  className="field mt-2"
                  aria-invalid={!!errors.quantity}
                />
                {errors.quantity && (
                  <span className="mt-1 block text-xs text-red-600">
                    {errors.quantity.message}
                  </span>
                )}
              </label>
              <label className="check-label self-center">
                <input type="checkbox" {...register("onlyWithoutWebsite")} />
                Somente sem site próprio
              </label>
              <label>
                Score mínimo (filtro sem site)
                <input
                  {...register("minScore", { valueAsNumber: true })}
                  type="number"
                  min={0}
                  max={100}
                  disabled={!onlyWithoutWebsite}
                  className="field mt-2"
                />
                {errors.minScore && (
                  <span className="text-xs text-red-600">
                    Score deve estar entre 0 e 100.
                  </span>
                )}
              </label>
            </fieldset>
            <div className="flex flex-wrap items-center justify-between gap-3">
              <p className="max-w-xl text-xs leading-5 text-slate-500">
                A pesquisa consulta Google Places e pode consumir a quota da
                integração. Os resultados não são salvos automaticamente.
              </p>
              <Button type="submit" disabled={active || busy || isSubmitting}>
                {isSubmitting ? (
                  <LoaderCircle className="animate-spin" />
                ) : (
                  <Search />
                )}
                {isSubmitting ? "Iniciando…" : "Iniciar pesquisa"}
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
      {notice && (
        <p
          role="status"
          className="mt-5 rounded-lg border bg-blue-50 p-4 text-sm text-blue-900"
        >
          {notice}
        </p>
      )}
      {jobId && (
        <Card className="mt-6">
          <CardContent>
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div aria-live="polite">
                <p className="flex items-center gap-2 text-sm font-semibold">
                  {active && (
                    <LoaderCircle
                      size={16}
                      className="animate-spin text-blue-600"
                    />
                  )}
                  {current ? labels[current.status] : "Carregando pesquisa…"}
                </p>
                <p className="mt-2 text-xs leading-6 text-slate-500">
                  {current
                    ? `${current.found} resultado(s) · ${current.scanned} empresa(s) analisada(s) · ${current.requestsMade} chamada(s) · ${current.pagesFetched} página(s)`
                    : "Consultando andamento no backend local."}
                </p>
                <p className="mt-1 text-xs text-slate-500">
                  {current?.message}
                </p>
                {current && (
                  <p className="mt-2 text-xs text-slate-500">
                    {current.query.niche} · {current.query.location} · até{" "}
                    {current.requested} resultados. Disponíveis por 15 minutos
                    após o término.
                  </p>
                )}
              </div>
              {active && (
                <Button
                  variant="outline"
                  onClick={cancel}
                  disabled={busy || current?.cancelRequested}
                >
                  <X />
                  {current?.cancelRequested
                    ? "Cancelamento solicitado"
                    : "Cancelar pesquisa"}
                </Button>
              )}
            </div>
            {current?.error && (
              <p role="alert" className="mt-3 text-sm text-amber-800">
                {current.error}
              </p>
            )}
            {current && !current.writesEnabled && (
              <p className="mt-4 rounded-lg bg-amber-50 p-3 text-xs leading-5 text-amber-900">
                Salvar na carteira está desabilitado. Após validar a cópia de
                teste, configure LOUNG_ENABLE_WRITES=1 no backend. A pesquisa e
                a exportação continuam disponíveis.
              </p>
            )}
          </CardContent>
        </Card>
      )}
      {pollError && (
        <div
          role="alert"
          className="mt-4 flex flex-wrap items-center gap-3 rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900"
        >
          <p>{pollError}</p>
          <Button variant="outline" onClick={() => setRevision((v) => v + 1)}>
            <RefreshCw />
            Retomar acompanhamento
          </Button>
        </div>
      )}
      <Card className="mt-6">
        <CardHeader className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <CardTitle>Resultados da prospecção</CardTitle>
            <p className="mt-1 text-xs text-slate-500">
              {results
                ? `${results.total} resultado(s) · ${selected.size} selecionado(s)`
                : resultsReady ? "Carregando resultados da pesquisa…" : "Nenhuma pesquisa carregada"}
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button
              variant="outline"
              disabled={!terminal(current) || !current?.found || busy}
              onClick={() => download("csv")}
            >
              <Download />
              CSV
            </Button>
            <Button
              variant="outline"
              disabled={!terminal(current) || !current?.found || busy}
              onClick={() => download("xlsx")}
            >
              <Download />
              Excel
            </Button>
            <Button
              disabled={
                !terminal(current) ||
                !selected.size ||
                !current?.writesEnabled ||
                busy
              }
              onClick={save}
            >
              <Save />
              {operation === "save" ? "Salvando…" : "Salvar selecionados"}
            </Button>
          </div>
        </CardHeader>
        {resultsError && (
          <div role="alert" className="p-4 text-sm text-amber-900">
            {resultsError}
            <Button variant="ghost" onClick={() => setRevision((v) => v + 1)}>
              Tentar carregar resultados novamente
            </Button>
          </div>
        )}
        {results?.items.length ? (
          <>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[850px] text-left text-xs">
                <thead className="bg-slate-50 text-slate-500">
                  <tr>
                    <th className="p-4">
                      <input
                        type="checkbox"
                        aria-label="Selecionar resultados desta página"
                        disabled={active || busy || !selectable.length}
                        checked={
                          !!selectable.length &&
                          selectable.every((row) => selected.has(row.id))
                        }
                        onChange={(e) => {
                          const checked = e.target.checked;
                          setSelected((previous) => {
                            const next = new Set(previous);
                            for (const row of selectable)
                              if (checked) next.add(row.id);
                              else next.delete(row.id);
                            return next;
                          });
                        }}
                      />
                    </th>
                    {[
                      "Empresa",
                      "Segmento",
                      "Localização",
                      "Telefone",
                      "Site",
                      "Carteira",
                    ].map((column) => (
                      <th
                        key={column}
                        scope="col"
                        className="px-4 py-3 font-medium"
                      >
                        {column}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {results.items.map((row) => (
                    <tr
                      key={row.id}
                      className={`border-t ${selected.has(row.id) ? "bg-blue-50" : ""}`}
                    >
                      <td className="p-4">
                        <input
                          type="checkbox"
                          disabled={row.alreadySaved || active || busy}
                          checked={selected.has(row.id)}
                          onChange={() => select(row.id)}
                          aria-label={`Selecionar ${row.company}`}
                        />
                      </td>
                      <td className="max-w-64 px-4 py-4 font-semibold break-words">
                        {row.company}
                      </td>
                      <td className="max-w-40 px-4 py-4">
                        {row.niche || "Não informado"}
                      </td>
                      <td className="max-w-64 px-4 py-4 break-words">
                        {row.address || row.location || "Não informada"}
                      </td>
                      <td className="px-4 py-4 whitespace-nowrap">
                        {row.phone || "Não informado"}
                      </td>
                      <td className="max-w-48 px-4 py-4 break-all">
                        {row.website || "Não informado pelo Google"}
                      </td>
                      <td className="px-4 py-4">
                        <span
                          className={`rounded-full px-2 py-1 whitespace-nowrap ${row.alreadySaved ? "bg-slate-100 text-slate-600" : "bg-blue-50 text-blue-700"}`}
                        >
                          {row.alreadySaved
                            ? "Já cadastrado"
                            : "Novo resultado"}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="flex flex-wrap items-center justify-between gap-3 border-t p-4 text-xs text-slate-500">
              <p>
                Página {page} de {Math.max(1, Math.ceil(results.total / 20))} ·{" "}
                <Link href="/leads" className="text-blue-600 hover:underline">
                  Consultar carteira
                </Link>
              </p>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  aria-label="Página anterior"
                  disabled={page === 1 || busy}
                  onClick={() => changePage(page - 1)}
                >
                  <ChevronLeft />
                </Button>
                <Button
                  variant="outline"
                  aria-label="Próxima página"
                  disabled={page * 20 >= results.total || busy}
                  onClick={() => changePage(page + 1)}
                >
                  <ChevronRight />
                </Button>
              </div>
            </div>
          </>
        ) : (
          <EmptyState
            title={
              jobId
                ? active
                  ? "Buscando empresas…"
                  : !results && !resultsError
                    ? "Carregando resultados…"
                    : resultsError
                      ? "Não foi possível carregar os resultados"
                      : current?.status === "completed"
                        ? "Nenhum estabelecimento encontrado"
                        : "Nenhum resultado disponível"
                : "As empresas encontradas aparecerão aqui"
            }
            description={
              jobId
                ? "Resultados parciais ficam disponíveis quando encontrados. Não há garantia de atingir a quantidade solicitada."
                : "Defina os critérios e inicie uma pesquisa para revisar os dados antes de salvar."
            }
          />
        )}
        <div className="border-t px-5 py-3 text-right">
          <span
            translate="no"
            className="text-xs font-normal whitespace-nowrap text-[#5e5e5e]"
          >
            Google Maps
          </span>
        </div>
      </Card>
    </>
  );
}
