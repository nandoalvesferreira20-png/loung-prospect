"use client";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { useReadResource } from "@/lib/api/use-read-resource";
import { readApi } from "@/lib/api/client";
import type { Activities, CommercialDetail } from "@/lib/api/crm-contracts";
import { PageHeader } from "@/components/shared";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { dateLabel, localInput } from "./date";
import { usePendingForm } from "./use-pending-form";
import { LeadContactActions } from "./lead-contact-actions";

export function LeadProfile({id}: {id: number}) {
  const [data,setData]=useState<CommercialDetail | null>(null);
  const [error,setError]=useState("");
  const [loading,setLoading]=useState(true);
  const [reset,setReset]=useState(0);
  useEffect(() => {
    const abort=new AbortController();
    readApi<CommercialDetail>(`/api/leads/${id}`,abort.signal).then(result => {
      if (abort.signal.aborted) return;
      if (result.status === "ready") setData(result.data); else setError(result.message);
      setLoading(false);
    }).catch(() => {});
    return () => abort.abort();
  },[id]);
  async function load() {
    setLoading(true);
    const result=await readApi<CommercialDetail>(`/api/leads/${id}`);
    if (result.status === "ready") {setData(result.data);setError("");} else setError(result.message);
    setLoading(false);
    return result.status === "ready";
  }
  return <>
    <PageHeader eyebrow="PERFIL COMERCIAL" title={data?.lead.company || "Detalhes do lead"} description="Contexto, relacionamento e próximos passos em um só lugar." action={<Button asChild variant="outline"><Link href="/pipeline">Voltar ao pipeline</Link></Button>} />
    <Link href={`/leads/${id}/editar`} className="mb-4 inline-block text-sm text-blue-600">Editar dados e contato</Link>
    {loading && <p role="status">Carregando perfil…</p>}
    {error && <div role="alert"><p>{error}</p><Button onClick={() => void load()}>Tentar novamente</Button></div>}
    {data && <ProfileForms key={reset} data={data} refresh={load} reload={async () => {if (await load()) setReset(value => value+1);}} />}
    {data && <div className="mt-5"><LeadContactActions id={id} /></div>}
  </>;
}

function ProfileForms({data,refresh,reload}: {data: CommercialDetail; refresh: () => Promise<boolean>; reload: () => void}) {
  const lead=data.lead;
  const timeline=useReadResource<Activities>(`/api/leads/${lead.id}/activities`);
  const [historyPage,setHistoryPage]=useState(0);
  const older=useReadResource<Activities>(`/api/leads/${lead.id}/activities?offset=${historyPage*20}`);
  const history=historyPage === 0 ? timeline.result : older.result;
  const [stage,setStage]=useState(lead.stage);
  const [kind,setKind]=useState("Observação");
  const [description,setDescription]=useState("");
  const [channel,setChannel]=useState("outro");
  const [confirmed,setConfirmed]=useState(false);
  const [due,setDue]=useState(localInput(lead.nextContact));
  const [note,setNote]=useState(lead.nextAction || "");
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState("");
  const [feedback,setFeedback]=useState("");
  const lock=useRef(false);
  const revision=useRef(lead.revision);
  // Props can refresh after a successful mutation; revision remains server-owned.
  useEffect(() => {revision.current=lead.revision;},[lead.revision]);
  const dirty=!!description || stage !== lead.stage || due !== localInput(lead.nextContact) || note !== (lead.nextAction || "");
  usePendingForm(dirty);
  async function mutate(path: string, method: string, values: Record<string,unknown>, success: string) {
    if (lock.current || !data.writesEnabled) return false;
    lock.current=true;setBusy(true);setError("");setFeedback("");
    const result=await readApi<{revision: string}>(path,undefined,{method,headers:{"Content-Type":"application/json"},body:JSON.stringify({...values,revision:revision.current})});
    if (result.status !== "ready") {setError(result.message);setBusy(false);lock.current=false;return false;}
    revision.current=result.data.revision;setFeedback(success);await refresh();timeline.refresh();older.refresh();
    setBusy(false);lock.current=false;return true;
  }
  return <div className="space-y-5">
    <div className="flex flex-wrap items-center justify-between gap-3"><p className="text-sm text-slate-500">{data.reason || "Alterações são salvas apenas pelas ações explícitas abaixo."}</p><Button variant="outline" disabled={busy} onClick={() => {if (!dirty || confirm("Descartar as edições e atualizar os dados?")) reload();}}>Atualizar perfil</Button></div>
    {error && <p role="alert" className="rounded-lg bg-red-50 p-3 text-sm text-red-800">{error}</p>}
    {feedback && <p role="status" className="rounded-lg bg-blue-50 p-3 text-sm text-blue-800">{feedback}</p>}
    <div className="grid items-start gap-5 lg:grid-cols-2">
      <Card><CardHeader><CardTitle>Dados da empresa</CardTitle></CardHeader><CardContent><dl className="grid gap-4 text-sm sm:grid-cols-2">{[["Nicho",lead.niche],["Telefone",lead.phone],["Localização",lead.location],["Site",lead.website],["Etapa original",lead.originalStage],["Última atividade",lead.lastActivity ? `${lead.lastActivity.kind} · ${dateLabel(lead.lastActivity.at)}` : null]].map(([label,value]) => <div key={label}><dt className="text-xs text-slate-500">{label}</dt><dd className="mt-1 break-words">{value || "Não informado"}</dd></div>)}</dl>{lead.notes && <div className="mt-5 border-t pt-4"><h3 className="text-xs font-semibold text-slate-500">Observações existentes</h3><p className="mt-2 whitespace-pre-wrap break-words text-sm">{lead.notes}</p></div>}</CardContent></Card>
      <Card><CardHeader><CardTitle>Situação comercial</CardTitle></CardHeader><CardContent>
        <form onSubmit={async event => {event.preventDefault();const confirmed=["Contato realizado","Fechado","Perdido"].includes(stage);if (confirmed && !confirm(`Confirma o registro manual da etapa ${stage}? Para contato, confirme que a conversa realmente ocorreu.`)) return;await mutate(`/api/leads/${lead.id}/stage`,"PATCH",{stage,confirmed},"Etapa alterada. Nenhum contato foi inferido.");}}><label>Etapa atual<select aria-label="Etapa atual" className="field mt-2" value={stage} disabled={busy || !data.writesEnabled} onChange={e => setStage(e.target.value)}>{data.stages.map(item => <option key={item}>{item}</option>)}</select></label><Button className="mt-3" disabled={busy || !data.writesEnabled || stage === lead.stage}>Salvar etapa</Button></form>
        <p className="mt-4 text-xs text-slate-500">Último contato registrado: {dateLabel(lead.lastContact)}</p>
        <p className="mt-2 text-xs text-slate-500">Próximo retorno: {dateLabel(lead.nextContact)} · {lead.nextAction || "Sem ação definida"}</p>
      </CardContent></Card>
      <Card><CardHeader><CardTitle>Registrar atividade ou observação</CardTitle></CardHeader><CardContent><form onSubmit={async event => {event.preventDefault();if (await mutate(`/api/leads/${lead.id}/activities`,"POST",{kind,description,channel,confirmed},"Atividade registrada no histórico.")) {setDescription("");setConfirmed(false);}}} className="space-y-4">
        <div className="grid gap-3 sm:grid-cols-2"><label>Tipo de atividade<select aria-label="Tipo de atividade" className="field mt-2" value={kind} disabled={busy} onChange={e => {setKind(e.target.value);setConfirmed(false);}}>{["Observação","Contato realizado","Resposta recebida","Reunião agendada","Proposta enviada"].map(item => <option key={item}>{item}</option>)}</select></label><label>Canal<select aria-label="Canal" className="field mt-2" value={channel} disabled={busy} onChange={e => setChannel(e.target.value)}>{["outro","whatsapp","telefone","email","instagram"].map(item => <option key={item}>{item}</option>)}</select></label></div>
        <label>Descrição<textarea aria-label="Descrição" className="field mt-2" maxLength={4000} value={description} disabled={busy} onChange={e => setDescription(e.target.value)} required /></label>
        {kind !== "Observação" && <label className="check-label"><input type="checkbox" checked={confirmed} disabled={busy} onChange={e => setConfirmed(e.target.checked)} />Confirmo que esta atividade realmente ocorreu</label>}
        <p className="text-xs leading-5 text-slate-500">Copiar ou abrir o WhatsApp não confirma contato. Registrar uma atividade não move a etapa.</p>
        <Button disabled={busy || !data.writesEnabled || !description.trim() || (kind !== "Observação" && !confirmed)}>Registrar atividade</Button>
      </form></CardContent></Card>
      <Card><CardHeader><CardTitle>Próximo follow-up</CardTitle></CardHeader><CardContent><form className="space-y-4" onSubmit={async event => {event.preventDefault();await mutate(`/api/leads/${lead.id}/followups`,"POST",{action:"schedule",dueAt:due ? new Date(due).toISOString() : null,note},"Retorno salvo no Meu Dia.");}}>
        <label>Data e horário locais · opcionais<input className="field mt-2" type="datetime-local" value={due} disabled={busy} onChange={e => setDue(e.target.value)} /></label>
        <label>Próxima ação / observação<input className="field mt-2" value={note} maxLength={240} disabled={busy} onChange={e => setNote(e.target.value)} /></label>
        <p className="text-xs leading-5 text-slate-500">Um retorno pendente por lead, como no desktop. Sem data, informe a ação. Reagendamentos e conclusões ficam no histórico.</p>
        <div className="flex flex-wrap gap-2"><Button disabled={busy || !data.writesEnabled || (!due && !note.trim())}>Salvar retorno</Button><Button type="button" variant="outline" disabled={busy || !data.writesEnabled || (!lead.nextContact && !lead.nextAction)} onClick={async () => {if (await mutate(`/api/followups/${lead.id}`,"PATCH",{action:"complete"},"Follow-up concluído. Nenhum contato foi registrado automaticamente.")) {setDue("");setNote("");}}}>Concluir follow-up</Button></div>
      </form></CardContent></Card>
    </div>
    <Card><CardHeader><CardTitle>Histórico do relacionamento</CardTitle><p className="mt-1 text-xs text-slate-500">Atividades manuais e registros existentes são identificados separadamente.</p></CardHeader><CardContent>
      {!history && <p role="status">Carregando histórico…</p>}
      {history && history.status !== "ready" && <p role="alert">{history.message}</p>}
      {history?.status === "ready" && <><ol className="space-y-4">{history.data.items.map(item => <li key={item.id} className="border-l-2 border-blue-100 pl-4"><p className="text-sm font-semibold">{item.kind}</p><p className="mt-1 text-xs text-slate-500">{item.actorName || "Autoria legada não identificada"} · {dateLabel(item.at)} · {item.origin === "manual" ? "Confirmado manualmente" : item.origin === "draft" ? "Rascunho salvo · não comprova contato" : "Registro existente"}</p><p className="mt-2 whitespace-pre-wrap break-words text-sm leading-6 text-slate-600">{item.description}</p></li>)}</ol>{history.data.total === 0 && <p className="text-sm text-slate-500">Nenhuma atividade registrada.</p>}<div className="mt-5 flex items-center gap-3"><Button variant="outline" disabled={!historyPage || busy} onClick={() => setHistoryPage(value => value-1)}>Mais recentes</Button><span className="text-xs text-slate-500">Página {historyPage+1}</span><Button variant="outline" disabled={(historyPage+1)*20 >= history.data.total || busy} onClick={() => setHistoryPage(value => value+1)}>Mais antigas</Button></div></>}
    </CardContent></Card>
  </div>;
}
