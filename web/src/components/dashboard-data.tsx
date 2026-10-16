"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { localTimezone } from "./crm/date";
import {
  Users,
  CalendarDays,
  Clock3,
  AlertCircle,
  RefreshCw,
  ArrowRight,
  ListTodo,
} from "lucide-react";
import { useReadResource } from "@/lib/api/use-read-resource";
import type { Overview } from "@/lib/api/contracts";
import { Card, CardHeader, CardTitle, CardContent } from "./ui/card";
import { Button } from "./ui/button";
import { ReadStatus } from "./read-status";
import { EmptyState } from "./shared";
import { ActivityChart } from "./activity-chart";

export function DashboardData() {
  const [tz,setTz] = useState("America/Sao_Paulo");
  useEffect(() => {queueMicrotask(() => setTz(localTimezone()));},[]);
  const { result, refresh } = useReadResource<Overview>(`/api/overview?tz=${encodeURIComponent(tz)}`);
  const data = result?.status === "ready" ? result.data : null;
  const metrics = [
    {
      label: "Leads na carteira",
      value: data?.total,
      icon: Users,
      help: "Total de registros na base local",
    },
    {
      label: "Contatos para hoje",
      value: data?.today,
      icon: Clock3,
      help: "Próximo contato agendado para hoje",
    },
    {
      label: "Retornos atrasados",
      value: data?.overdue,
      icon: AlertCircle,
      help: "Exclui etapas comerciais encerradas",
    },
    {
      label: "Reuniões agendadas",
      value: data?.meetings,
      icon: CalendarDays,
      help: "Leads na etapa de reunião agendada",
    },
  ];
  return (
    <>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <ReadStatus result={result} refresh={refresh} />
        <Button variant="outline" onClick={refresh} disabled={!result}>
          <RefreshCw />
          Atualizar indicadores
        </Button>
      </div>
      <div
        className="grid grid-cols-2 gap-3 sm:gap-4 xl:grid-cols-4"
        aria-busy={!result}
      >
        {metrics.map(({ label, value, icon: Icon, help }) => (
          <Card key={label}>
            <CardContent>
              <div className="flex items-center justify-between gap-2">
                <p className="text-xs font-medium text-slate-500">{label}</p>
                <Icon size={17} className="shrink-0 text-slate-400" />
              </div>
              <p
                className="my-4 text-3xl font-semibold"
                aria-label={
                  value === undefined ? "Dado indisponível" : String(value)
                }
              >
                {value ?? "—"}
              </p>
              <p className="text-[11px] leading-5 text-slate-500">{help}</p>
            </CardContent>
          </Card>
        ))}
      </div>
      <Card className="mt-6">
        <CardHeader className="flex flex-wrap items-center justify-between gap-2">
          <CardTitle>Distribuição por etapa comercial</CardTitle>
          <span className="text-xs text-slate-500">
            {data ? `${data.total} leads · situação atual` : "Aguardando dados"}
          </span>
        </CardHeader>
        <CardContent>
          {data?.stageCounts.length ? (
            <ActivityChart data={data.stageCounts} />
          ) : (
            <EmptyState
              title={
                data
                  ? "Ainda não há leads na base"
                  : "Indicadores indisponíveis"
              }
              description={
                data
                  ? "A distribuição aparecerá quando houver registros na base desktop."
                  : "Verifique a API local para consultar os indicadores."
              }
            />
          )}
        </CardContent>
      </Card>
      <Card className="mt-6">
        <CardHeader className="flex items-center justify-between">
          <CardTitle>Próximas ações</CardTitle>
          <Link
            href="/leads"
            className="flex items-center gap-2 text-xs text-blue-600"
          >
            Ver carteira
            <ArrowRight size={14} />
          </Link>
        </CardHeader>
        {data?.actions.length ? (
          <ul className="divide-y">
            {data.actions.map((lead) => (
              <li
                key={lead.id}
                className="flex flex-wrap items-start justify-between gap-3 px-5 py-4"
              >
                <div>
                  <Link href={`/leads/${lead.id}`} className="text-sm font-semibold hover:text-blue-700">{lead.company}</Link>
                  <p className="mt-1 text-xs text-slate-500">
                    {lead.nextAction || "Próxima ação não definida"}
                  </p>
                </div>
                <div className="text-right text-xs">
                  <p>{lead.stage}</p>
                  <p className="mt-1 text-slate-500">
                    {lead.nextContact
                      ? formatDate(lead.nextContact)
                      : "Sem agendamento"}
                  </p>
                </div>
              </li>
            ))}
          </ul>
        ) : (
          <EmptyState
            icon={ListTodo}
            title={
              data ? "Nenhuma próxima ação disponível" : "Ações indisponíveis"
            }
            description={
              data
                ? "Organize os retornos pelo Meu Dia ou pelo perfil do lead. A seleção segue as regras do desktop."
                : "Conecte o backend local para consultar os próximos passos."
            }
          />
        )}
      </Card>
      {data && (
        <p className="mt-3 text-xs text-slate-500">
          Referência dos agendamentos: {data.referenceDate} · fuso local do
          backend.
          {data.invalidDates > 0
            ? ` ${data.invalidDates} data(s) inválida(s) não contabilizada(s) nos agendamentos.`
            : ""}
        </p>
      )}
    </>
  );
}
function formatDate(value: string) {
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? "Data inválida"
    : date.toLocaleString("pt-BR");
}
