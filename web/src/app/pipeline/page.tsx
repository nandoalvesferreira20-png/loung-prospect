"use client";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { GripVertical, RefreshCw } from "lucide-react";
import { PageHeader } from "@/components/shared";
import { Button } from "@/components/ui/button";
import { readApi } from "@/lib/api/client";
import type { CommercialLead, Pipeline } from "@/lib/api/crm-contracts";
import { dateLabel } from "@/components/crm/date";

export default function PipelinePage() {
  const [data,setData] = useState<Pipeline | null>(null);
  const [query,setQuery] = useState("");
  const [niche,setNiche] = useState("");
  const [revision,setRevision] = useState(0);
  const [loading,setLoading] = useState(true);
  const [error,setError] = useState("");
  const [feedback,setFeedback] = useState("");
  const [busy,setBusy] = useState(false);
  const [dragged,setDragged] = useState<CommercialLead | null>(null);
  const [target,setTarget] = useState<string | null>(null);
  const lock = useRef(false);
  const readEpoch = useRef(0);
  useEffect(() => {
    const abort = new AbortController();
    const epoch = ++readEpoch.current;
    const timer = setTimeout(async () => {
      if (epoch !== readEpoch.current) return;
      setLoading(true);setError("");
      try {
        const result = await readApi<Pipeline>(`/api/pipeline?${new URLSearchParams({q:query,niche})}`,abort.signal);
        if (abort.signal.aborted || epoch !== readEpoch.current) return;
        if (result.status === "ready") setData(result.data); else {setData(null);setError(result.message);}
      } catch { /* Superseded filters. */ }
      finally {if (!abort.signal.aborted && epoch === readEpoch.current) setLoading(false);}
    },200);
    return () => {clearTimeout(timer);abort.abort();};
  },[query,niche,revision]);

  async function move(lead: CommercialLead, stage: string) {
    if (!data?.writesEnabled || lock.current || loading || stage === lead.stage) return;
    const confirmed = ["Contato realizado","Fechado","Perdido"].includes(stage);
    if (confirmed && !confirm(`Confirma que ${stage === "Contato realizado" ? "o contato realmente ocorreu" : stage === "Fechado" ? "o negócio foi convertido" : "o negócio foi perdido"}? Esta informação será registrada manualmente.`)) return;
    lock.current=true;setBusy(true);setError("");setFeedback("");
    readEpoch.current++;
    const before=data;
    setData({...data,columns:data.columns.map(column => column.stage === lead.stage ? {...column,total:column.total-1,items:column.items.filter(item => item.id !== lead.id)} : column.stage === stage ? {...column,total:column.total+1,items:[{...lead,stage},...column.items]} : column)});
    const result = await readApi(`/api/leads/${lead.id}/stage`,undefined,{method:"PATCH",headers:{"Content-Type":"application/json"},body:JSON.stringify({stage,confirmed,revision:lead.revision})});
    if (result.status !== "ready") {setData(before);setError(result.message + " A movimentação visual foi revertida. Atualize o quadro antes de repetir.");}
    else {setFeedback(`${lead.company}: etapa alterada para ${stage}.`);setLoading(true);setRevision(value => value+1);}
    setBusy(false);lock.current=false;
  }
  async function more(stage: string) {
    if (!data || lock.current) return;
    const column=data.columns.find(item => item.stage === stage)!;
    lock.current=true;setBusy(true);
    const result=await readApi<Pipeline>(`/api/pipeline?${new URLSearchParams({q:query,niche,stage,offset:String(column.items.length)})}`);
    if (result.status === "ready") setData({...data,columns:data.columns.map(item => item.stage === stage ? {...item,items:[...item.items,...result.data.columns[0].items].filter((lead,index,all) => all.findIndex(other => other.id === lead.id) === index),total:result.data.columns[0].total} : item)});
    else setError(result.message);
    setBusy(false);lock.current=false;
  }
  return <>
    <PageHeader eyebrow="GESTÃO COMERCIAL" title="Cada oportunidade no seu momento" description="Organize as próximas ações. Mover uma etapa não registra envio ou resposta automaticamente." action={<Button variant="outline" disabled={busy || loading} onClick={() => setRevision(value => value+1)}><RefreshCw />Atualizar quadro</Button>} />
    <div className="mb-5 grid gap-3 sm:grid-cols-[minmax(220px,1fr)_260px_auto]">
      <label>Buscar empresa<input className="field mt-2" placeholder="Nome da empresa" maxLength={200} value={query} disabled={busy} onChange={e => {setQuery(e.target.value);setFeedback("");}} /></label>
      <label>Nicho<select className="field mt-2" value={niche} disabled={busy} onChange={e => {setNiche(e.target.value);setFeedback("");}}><option value="">Todos os nichos</option>{data?.niches.map(item => <option key={item}>{item}</option>)}</select></label>
      <Button asChild variant="outline" className="self-end"><Link href="/meu-dia">Meu Dia</Link></Button>
    </div>
    {data?.reason && <p className="mb-4 rounded-lg border bg-blue-50 p-3 text-sm text-blue-900">{data.reason}</p>}
    {error && <p role="alert" className="mb-4 rounded-lg bg-red-50 p-3 text-sm text-red-800">{error}</p>}
    <p role="status" className="mb-4 text-sm text-slate-500">{loading ? "Carregando pipeline…" : feedback || (data ? `${data.total} leads · arraste um card ou use o seletor de etapa.` : "Quadro indisponível.")}</p>
    <div role="region" aria-label="Etapas do pipeline" tabIndex={0} className="max-w-full overflow-x-auto rounded-xl pb-5 focus-visible:outline-blue-500" aria-busy={loading || busy}>
      <div className="flex items-start gap-4">
        {data?.columns.map((column,index) => <section key={column.stage} aria-label={`Etapa ${column.stage}`} onDragOver={event => {if (data.writesEnabled && dragged && !busy) {event.preventDefault();setTarget(column.stage);}}} onDragLeave={() => setTarget(null)} onDrop={event => {event.preventDefault();if (dragged) void move(dragged,column.stage);setDragged(null);setTarget(null);}} className={`w-72 shrink-0 rounded-xl border p-3 ${target === column.stage ? "border-blue-400 bg-blue-50" : "bg-slate-100/70"}`}>
          <div className="mb-4 flex items-center gap-2"><span className={`size-2 rounded-full ${index === 5 ? "bg-emerald-500" : "bg-blue-400"}`} /><h2 className="flex-1 text-sm font-semibold">{column.stage}</h2><span className="rounded-full bg-white px-2 py-1 text-xs">{column.total}</span></div>
          <ul className="space-y-3">{column.items.map(lead => <li key={lead.id} draggable={data.writesEnabled && !busy && !loading} onDragStart={event => {setDragged(lead);event.dataTransfer.setData("text/plain",String(lead.id));event.dataTransfer.effectAllowed="move";}} onDragEnd={() => {setDragged(null);setTarget(null);}} className={`rounded-lg border bg-white p-3 shadow-sm ${dragged?.id === lead.id ? "opacity-50" : ""}`}>
            <div className="flex items-start gap-2"><Link className="flex-1 break-words text-sm font-semibold text-slate-900 hover:text-blue-700" href={`/leads/${lead.id}`}>{lead.company}</Link><GripVertical size={16} className="shrink-0 text-slate-300" aria-hidden="true" /></div>
            <p className="mt-2 text-xs text-slate-500">{lead.niche || "Nicho não informado"} · {lead.location || "Local não informado"}</p>
            {lead.originalStage !== lead.stage && <p className="mt-2 text-xs text-slate-500">Registro original: {lead.originalStage || "Sem etapa"}</p>}
            <p className="mt-3 text-xs text-slate-600">Retorno: {dateLabel(lead.nextContact)}{lead.nextAction ? ` · ${lead.nextAction}` : ""}</p>
            <p className="mt-2 text-xs text-slate-400">{lead.lastActivity ? `${lead.lastActivity.kind} · ${dateLabel(lead.lastActivity.at)}` : "Nenhuma atividade registrada"}</p>
            <label className="mt-3 text-xs">Mover {lead.company}<select aria-label={`Mover ${lead.company}`} className="field mt-1" disabled={!data.writesEnabled || busy || loading} value={lead.stage} onChange={event => void move(lead,event.target.value)}>{data.stages.map(stage => <option key={stage}>{stage}</option>)}</select></label>
          </li>)}</ul>
          {column.total === 0 && <p className="rounded-lg border border-dashed bg-white/60 p-5 text-center text-xs text-slate-400">Nenhum lead nesta etapa</p>}
          {column.items.length < column.total && <Button className="mt-3 w-full text-xs" variant="outline" disabled={busy || loading} onClick={() => void more(column.stage)}>Carregar mais · {column.items.length} de {column.total}</Button>}
        </section>)}
      </div>
    </div>
  </>;
}
