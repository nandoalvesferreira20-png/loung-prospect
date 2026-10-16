"use client";
import { useEffect, useState } from "react";
import { useReadResource } from "@/lib/api/use-read-resource";
import type { CommercialMetrics } from "@/lib/api/crm-contracts";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { localTimezone } from "./date";
export function CommercialDashboard() {
  const [tz,setTz]=useState("America/Sao_Paulo");
  useEffect(() => {queueMicrotask(() => setTz(localTimezone()));},[]);
  const resource=useReadResource<CommercialMetrics>(`/api/dashboard/commercial?tz=${encodeURIComponent(tz)}`);
  const data=resource.result?.status === "ready" ? resource.result.data : null;
  const cards: [string,number | null | undefined][] = [["Total de leads",data?.total],["Contato registrado",data?.contacted],["Resposta confirmada",data?.responded],["Conversas / propostas",data?.negotiations],["Convertidos · Fechado",data?.converted],["Retornos pendentes",data?.pending],["Retornos atrasados",data?.overdue]];
  return <section className="my-6" aria-label="Indicadores comerciais"><div className="mb-3 flex flex-wrap justify-between gap-3"><h2 className="text-lg font-semibold">Operação comercial</h2><Button variant="outline" onClick={resource.refresh}>Atualizar comercial</Button></div><p className="mb-4 text-xs leading-5 text-slate-500">Contatos e respostas contam leads distintos com registros explícitos. Conversas/propostas e conversões refletem a etapa atual; gerar ou abrir WhatsApp não altera indicadores.</p>
    {resource.result && resource.result.status !== "ready" && <p role="alert" className="mb-4 text-sm text-red-700">{resource.result.message}</p>}
    <div className="grid grid-cols-2 gap-3 md:grid-cols-4">{cards.map(([label,value]) => <Card key={label}><CardContent><p className="text-xs text-slate-500">{label}</p><p className="mt-3 text-2xl font-semibold">{value ?? "—"}</p></CardContent></Card>)}</div>
  </section>;
}
