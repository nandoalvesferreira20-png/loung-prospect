"use client";
import Link from "next/link";
import { useState, useDeferredValue } from "react";
import {
  Search,
  Users,
  ChevronLeft,
  ChevronRight,
  RefreshCw,
} from "lucide-react";
import { EmptyState } from "./shared";
import { ReadStatus } from "./read-status";
import { Card } from "./ui/card";
import { Button } from "./ui/button";
import { commercialStages, type Lead, type Page } from "@/lib/api/contracts";
import { useReadResource } from "@/lib/api/use-read-resource";
export function LeadsTable() {
  const [search, setSearch] = useState("");
  const [stage, setStage] = useState("");
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const deferredSearch = useDeferredValue(search);
  const params = new URLSearchParams({
    q: deferredSearch,
    stage,
    page: String(page),
    pageSize: "20",
  });
  const { result, refresh } = useReadResource<Page<Lead>>(
    `/api/leads?${params}`,
  );
  const data = result?.status === "ready" ? result.data : null;
  const pending = !result || deferredSearch !== search;
  function resetSelection() {
    setPage(1);
    setSelected(new Set());
  }
  function toggle(id: number) {
    setSelected((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }
  return (
    <>
      <ReadStatus result={result} refresh={refresh} />
      <Card aria-busy={pending}>
        <div className="flex flex-wrap items-end gap-3 border-b p-5">
          <label className="min-w-48 flex-1">
            Buscar lead
            <div className="relative mt-2">
              <Search
                size={16}
                className="absolute left-3 top-3 text-slate-400"
              />
              <input
                className="field pl-9"
                value={search}
                onChange={(e) => {
                  setSearch(e.target.value);
                  resetSelection();
                }}
                placeholder="Empresa, telefone, segmento ou cidade"
              />
            </div>
          </label>
          <label>
            Etapa
            <select
              aria-label="Etapa"
              className="field mt-2"
              value={stage}
              onChange={(e) => {
                setStage(e.target.value);
                resetSelection();
              }}
            >
              <option value="">Todas as etapas</option>
              {Array.from(
                new Set([
                  ...(data?.stages ?? commercialStages),
                  ...(stage ? [stage] : []),
                ]),
              ).map((s) => (
                <option key={s}>{s}</option>
              ))}
            </select>
          </label>
          <Button variant="outline" onClick={refresh} disabled={pending}>
            <RefreshCw />
            Atualizar
          </Button>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[800px] text-left text-xs">
            <thead className="bg-slate-50 text-slate-500">
              <tr>
                <th className="w-10 p-4">
                  <input
                    type="checkbox"
                    aria-label="Selecionar leads desta página"
                    disabled={!data?.items.length || pending}
                    checked={
                      !!data?.items.length &&
                      data.items.every((l) => selected.has(l.id))
                    }
                    onChange={(e) =>
                      setSelected(
                        e.target.checked
                          ? new Set(data?.items.map((l) => l.id))
                          : new Set(),
                      )
                    }
                  />
                </th>
                {[
                  "Empresa",
                  "Telefone",
                  "Segmento",
                  "Site",
                  "Localização",
                  "Etapa",
                ].map((h) => (
                  <th key={h} scope="col" className="px-4 py-3 font-medium">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {pending ? (
                <tr>
                  <td colSpan={7} className="p-10 text-center text-slate-500">
                    Carregando leads…
                  </td>
                </tr>
              ) : data?.items.length ? (
                data.items.map((lead) => (
                  <tr
                    key={lead.id}
                    className={`border-t transition-colors ${selected.has(lead.id) ? "bg-blue-50" : "hover:bg-slate-50"}`}
                  >
                    <td className="p-4">
                      <input
                        type="checkbox"
                        checked={selected.has(lead.id)}
                        onChange={() => toggle(lead.id)}
                        aria-label={`Selecionar ${lead.company}`}
                      />
                    </td>
                    <td className="max-w-64 px-4 py-4 font-semibold break-words">
                      <Link href={`/leads/${lead.id}`} className="hover:text-blue-700 hover:underline">{lead.company}</Link>
                    </td>
                    <td className="px-4 py-4 whitespace-nowrap">
                      {lead.phone || "Não informado"}
                    </td>
                    <td className="max-w-48 px-4 py-4 break-words">
                      {lead.niche || "Não informado"}
                    </td>
                    <td className="max-w-56 px-4 py-4 break-all">
                      {lead.website || "Não informado"}
                    </td>
                    <td className="px-4 py-4">
                      {lead.location || "Não informada"}
                    </td>
                    <td className="px-4 py-4">
                      <span
                        title={
                          lead.originalStage !== lead.stage
                            ? `Salvo originalmente como: ${lead.originalStage}`
                            : undefined
                        }
                        className="inline-block rounded-full bg-slate-100 px-2.5 py-1 text-slate-600"
                      >
                        {lead.stage}
                      </span>
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={7}>
                    <EmptyState
                      icon={Users}
                      title={
                        data
                          ? search || stage
                            ? "Nenhum lead corresponde aos filtros"
                            : "Nenhum lead cadastrado"
                          : "Não foi possível carregar a carteira"
                      }
                      description={
                        data
                          ? "Ajuste os filtros ou consulte a base atualizada no desktop."
                          : "Verifique a conexão com a API e tente novamente. Nenhum dado foi alterado."
                      }
                    />
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
        <div className="flex flex-wrap items-center justify-between gap-3 border-t px-5 py-3 text-xs text-slate-500">
          <span role="status">
            {data
              ? `${data.total} lead(s) encontrado(s) · ${selected.size} selecionado(s) nesta página`
              : "Dados indisponíveis"}
          </span>
          <div className="flex items-center gap-3">
            <span>
              Página {data?.page ?? "—"}{" "}
              {data
                ? `de ${Math.max(1, Math.ceil(data.total / data.pageSize))}`
                : ""}
            </span>
            <Button
              variant="outline"
              disabled={pending || !data || page <= 1}
              onClick={() => {
                setPage((p) => p - 1);
                setSelected(new Set());
              }}
              aria-label="Página anterior"
            >
              <ChevronLeft />
            </Button>
            <Button
              variant="outline"
              disabled={pending || !data || page * data.pageSize >= data.total}
              onClick={() => {
                setPage((p) => p + 1);
                setSelected(new Set());
              }}
              aria-label="Próxima página"
            >
              <ChevronRight />
            </Button>
          </div>
        </div>
      </Card>
    </>
  );
}
