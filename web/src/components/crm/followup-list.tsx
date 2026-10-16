"use client";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { useReadResource } from "@/lib/api/use-read-resource";
import { readApi } from "@/lib/api/client";
import type { Followups } from "@/lib/api/crm-contracts";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, CardContent, CardTitle } from "@/components/ui/card";
import { dateLabel, localTimezone } from "./date";

export function FollowupList({compact=false}: {compact?: boolean}) {
  const [tz,setTz]=useState("America/Sao_Paulo");
  const [scope,setScope]=useState("day");
  const [page,setPage]=useState(0);
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState("");
  const [feedback,setFeedback]=useState("");
  const lock=useRef(false);
  useEffect(() => {queueMicrotask(() => setTz(localTimezone()));},[]);
  const size=compact ? 5 : 20;
  const resource=useReadResource<Followups>(`/api/followups?${new URLSearchParams({tz,scope,offset:String(page*size),limit:String(size)})}`);
  const data=resource.result?.status === "ready" ? resource.result.data : null;
  return <Card><CardHeader><div className="flex flex-wrap justify-between gap-3"><CardTitle>Meu Dia</CardTitle><div className="flex flex-wrap gap-2"><Button variant="outline" disabled={busy} onClick={resource.refresh}>Atualizar retornos</Button>{compact && <Button asChild variant="outline"><Link href="/meu-dia">Ver Meu Dia</Link></Button>}</div></div><p className="mt-2 text-xs leading-5 text-slate-500">Regras do desktop: hoje, atrasados, novos, reuniões e propostas. Atraso é por dia local, excluindo etapas encerradas.</p></CardHeader><CardContent>
    <label className="mb-4 max-w-xs">Visualização<select className="field mt-2" value={scope} disabled={busy} onChange={e => {setScope(e.target.value);setPage(0);}}><option value="day">Meu Dia · seleção comercial</option><option value="pending">Todos os retornos pendentes</option></select></label>
    {data && <p className="mb-4 text-xs text-slate-500">{data.total} registros · {tz}{data.invalidDates ? ` · ${data.invalidDates} datas inválidas na origem` : ""}</p>}
    {data?.reason && <p className="mb-3 text-xs text-slate-500">{data.reason}</p>}
    {error && <p role="alert" className="mb-3 text-sm text-red-700">{error}</p>}
    {feedback && <p role="status" className="mb-3 text-sm text-blue-700">{feedback}</p>}
    {!resource.result && <p role="status">Carregando próximos passos…</p>}
    {resource.result && resource.result.status !== "ready" && <p role="alert">{resource.result.message}</p>}
    {data && <ul className="divide-y">{data.items.map(lead => <li key={lead.id} className="flex flex-wrap items-center justify-between gap-3 py-4"><div className="min-w-0 flex-1"><Link href={`/leads/${lead.id}`} className="break-words text-sm font-semibold text-slate-800 hover:text-blue-700">{lead.company}</Link><p className="mt-1 text-xs text-slate-500">{lead.stage} · {dateLabel(lead.nextContact)}</p><p className="mt-1 break-words text-sm text-slate-600">{lead.nextAction || "Defina o próximo passo no perfil"}</p><span className={`mt-2 inline-block text-xs ${lead.overdue ? "text-red-700" : "text-blue-700"}`}>{lead.overdue ? "Atrasado" : lead.today ? "Para hoje" : lead.hasFollowup ? "Retorno pendente" : "Ação comercial"}</span></div><div className="flex gap-2"><Button variant="outline" asChild><Link href={`/leads/${lead.id}`}>Detalhes / reagendar</Link></Button><Button disabled={!data.writesEnabled || !lead.hasFollowup || busy} aria-label={`Concluir retorno de ${lead.company}`} onClick={async () => {
      if (lock.current || !confirm("Concluir este follow-up? Isso não registra contato realizado.")) return;
      lock.current=true;setBusy(true);setError("");setFeedback("");
      const result=await readApi(`/api/followups/${lead.id}`,undefined,{method:"PATCH",headers:{"Content-Type":"application/json"},body:JSON.stringify({revision:lead.revision,action:"complete"})});
      if (result.status !== "ready") setError(result.message); else {setFeedback("Follow-up concluído.");resource.refresh();}
      setBusy(false);lock.current=false;
    }}>Concluir</Button></div></li>)}</ul>}
    {data?.items.length === 0 && <p className="py-5 text-sm text-slate-500">Nenhuma ação nesta visualização.</p>}
    {data && !data.available && <p role="status" className="text-sm text-slate-500">Retornos indisponíveis neste schema; nenhuma migração foi executada.</p>}
    {data && data.total > size && <div className="mt-4 flex items-center gap-3"><Button variant="outline" disabled={!page || busy} onClick={() => setPage(value => value-1)}>Anterior</Button><span className="text-xs">{page+1} / {Math.ceil(data.total/size)}</span><Button variant="outline" disabled={(page+1)*size >= data.total || busy} onClick={() => setPage(value => value+1)}>Próxima</Button></div>}
  </CardContent></Card>;
}
