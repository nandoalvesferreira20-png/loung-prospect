"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { PendingMessageDialog } from "@/components/sdr/pending-message-dialog";
import { SdrLeadSummary } from "@/components/sdr/lead-summary";
import { SdrHistoryPanel } from "@/components/sdr/history-panel";
import { ArrowRight, Copy, ExternalLink, LoaderCircle, MessageSquare, RefreshCw, Search, Sparkles, UserRound } from "lucide-react";
import { PageHeader, EmptyState } from "@/components/shared";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { prospectApi, readApi } from "@/lib/api/client";
import type { Lead, Page } from "@/lib/api/contracts";
import { contactLabels, type GenerateRequest, type SdrContext, type SdrDraft, type SdrHistory } from "@/lib/api/sdr-contracts";
import { whatsappLink } from "@/lib/sdr-whatsapp";

export default function Sdr() {
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(1);
  const [leads, setLeads] = useState<Page<Lead> | null>(null);
  const [listLoading, setListLoading] = useState(true);
  const [listError, setListError] = useState("");
  const [refresh, setRefresh] = useState(0);
  const [selected, setSelected] = useState<number | null>(null);
  const [context, setContext] = useState<SdrContext | null>(null);
  const [history, setHistory] = useState<SdrHistory | null>(null);
  const [contextLoading, setContextLoading] = useState(false);
  const [recipient, setRecipient] = useState<GenerateRequest["recipient"]>("auto");
  const [service, setService] = useState<GenerateRequest["service"]>("auto");
  const [instruction, setInstruction] = useState("");
  const [draft, setDraft] = useState<SdrDraft | null>(null);
  const [message, setMessage] = useState("");
  const [savedMessage, setSavedMessage] = useState("");
  const [savedStatus, setSavedStatus] = useState("");
  const [busy, setBusy] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [feedback, setFeedback] = useState("");
  const [pending, setPending] = useState<(() => void) | null>(null);
  const operation = useRef(false);
  const contextVersion = useRef(0);
  const retry = useRef<{ signature: string; request: GenerateRequest } | null>(null);
  const dirty = message !== savedMessage;
  const count = [...message].length;
  const link = context && !context.blocked && !busy && !saving ? whatsappLink(context.normalizedPhone, message) : null;
  const canSave = !!draft && !!history?.writesEnabled && !!message.trim() && count <= 1200 && !context?.blocked && savedStatus !== "APROVADA";

  useEffect(() => {
    const controller = new AbortController();
    const timer = setTimeout(async () => {
      setListLoading(true); setListError("");
      try {
        const result = await prospectApi.listLeads({ q: query, page, pageSize: 8 }, controller.signal);
        if (controller.signal.aborted) return;
        if (result.status === "ready") setLeads(result.data);
        else { setLeads(null); setListError(result.message); }
      } catch { /* Superseded search. */ }
      finally { if (!controller.signal.aborted) setListLoading(false); }
    }, 250);
    return () => { clearTimeout(timer); controller.abort(); };
  }, [query, page, refresh]);

  useEffect(() => {
    if (!dirty) return;
    const warn = (event: BeforeUnloadEvent) => { event.preventDefault(); event.returnValue = ""; };
    const navigation = (event: MouseEvent) => {
      const anchor = (event.target as Element).closest("a[href]") as HTMLAnchorElement | null;
      if (!anchor || anchor.target === "_blank" || event.ctrlKey || event.metaKey || event.shiftKey || anchor.origin !== location.origin || anchor.pathname === location.pathname) return;
      if (!window.confirm("Há uma mensagem não salva. Sair e descartar o texto? Cancele para continuar editando ou salvar.")) { event.preventDefault(); event.stopPropagation(); }
    };
    window.addEventListener("beforeunload", warn); document.addEventListener("click", navigation, true);
    return () => { window.removeEventListener("beforeunload", warn); document.removeEventListener("click", navigation, true); };
  }, [dirty]);

  const selectLead = useCallback(async (id: number) => {
    const version = ++contextVersion.current;
    setSelected(id); setContext(null); setHistory(null); setContextLoading(true);
    setMessage(""); setSavedMessage(""); setSavedStatus(""); setDraft(null);
    setRecipient("auto"); setInstruction(""); setError(""); setFeedback(""); retry.current = null;
    const [details, previous] = await Promise.all([
      readApi<SdrContext>(`/api/sdr/leads/${id}`), readApi<SdrHistory>(`/api/sdr/history/${id}`),
    ]);
    if (version !== contextVersion.current) return;
    if (details.status === "ready") setContext(details.data); else setError(details.message);
    if (previous.status === "ready") setHistory(previous.data); else setError(previous.message);
    setContextLoading(false);
  }, []);

  useEffect(() => {
    const value = new URLSearchParams(window.location.search).get("leadId");
    if (!value || !/^[1-9]\d{0,14}$/.test(value)) return;
    const timer = setTimeout(() => void selectLead(Number(value)), 0);
    return () => clearTimeout(timer);
  }, [selectLead]);

  function protect(action: () => void) {
    if (operation.current) return;
    if (dirty) setPending(() => action); else action();
  }

  async function generate() {
    if (!context || operation.current || context.blocked) return;
    operation.current = true; setBusy(true); setError(""); setFeedback("");
    const input = { leadId: context.leadId, recipient, service, instruction, ...(draft ? { previousDraftId: draft.draftId } : {}) };
    const signature = JSON.stringify(input);
    const request = retry.current?.signature === signature ? retry.current.request : { ...input, requestId: crypto.randomUUID() };
    retry.current = { signature, request };
    try {
      const result = await prospectApi.generateDraft(request);
      if (result.status === "ready") {
        setDraft(result.data); setMessage(result.data.message); setSavedMessage(""); setSavedStatus("");
        setFeedback("Rascunho gerado. Revise os fatos e o destinatário antes de abrir a conversa."); retry.current = null;
      } else {
        setError(result.message);
        if (!result.message.startsWith("A API local não respondeu") && !result.message.startsWith("Falha de conexão")) retry.current = null;
      }
    } finally { operation.current = false; setBusy(false); }
  }

  async function save(status: "EDITADA" | "APROVADA"): Promise<boolean> {
    if (!draft || !canSave || operation.current) return false;
    operation.current = true; setSaving(true); setError(""); setFeedback("");
    try {
      const result = await readApi<{ id: number }>("/api/sdr/history", undefined, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ draftId: draft.draftId, message, status }),
      });
      if (result.status !== "ready") { setError(result.message); return false; }
      setSavedMessage(message); setSavedStatus(status);
      setFeedback(status === "APROVADA" ? "Versão aprovada e salva. Nenhuma mensagem foi enviada." : "Texto revisado salvo no histórico.");
      const previous = await readApi<SdrHistory>(`/api/sdr/history/${draft.leadId}`);
      if (previous.status === "ready") setHistory(previous.data); else setError(previous.message);
      return true;
    } finally { operation.current = false; setSaving(false); }
  }

  async function copy() {
    try { await navigator.clipboard.writeText(message); setFeedback("Mensagem copiada."); }
    catch { setError("Não foi possível copiar. Selecione o texto e copie manualmente."); }
  }

  return <>
    <PageHeader eyebrow="SDR INTELIGENTE" title="Do contexto à conversa" description="Escolha um lead, prepare a abordagem e revise antes de abrir o WhatsApp." />
    <div className="mb-6 flex flex-wrap items-center gap-3 text-xs text-slate-500">
      <span className="font-medium text-blue-700">1. Selecionar lead</span>
      <ArrowRight size={13} />
      <span>2. Gerar e revisar</span>
      <ArrowRight size={13} />
      <span>3. Abrir conversa</span>
    </div>
    <div className="grid items-start gap-5 xl:grid-cols-[300px_minmax(0,1fr)]">
      <Card>
        <CardHeader className="flex items-center justify-between gap-3">
          <CardTitle>Leads da carteira</CardTitle>
          <Button variant="ghost" className="px-2" aria-label="Atualizar leads" disabled={listLoading || busy || saving} onClick={() => { setRefresh(x => x + 1); if (selected) protect(() => void selectLead(selected)); }}>
            <RefreshCw size={16} />
          </Button>
        </CardHeader>
        <CardContent>
          <label htmlFor="lead-search" className="sr-only">Buscar lead por nome</label>
          <div className="relative">
            <Search className="pointer-events-none absolute left-3 top-3 text-slate-400" size={16} />
            <input id="lead-search" className="field !pl-9" placeholder="Buscar empresa…" value={query} maxLength={200} onChange={e => { setQuery(e.target.value); setPage(1); }} />
          </div>
          <div aria-live="polite" className="mt-3 text-xs text-slate-500">
            {listLoading ? "Carregando leads…" : leads ? `${leads.total} leads encontrados` : "Consulta indisponível"}
          </div>
          {listError && <p role="alert" className="mt-3 text-sm text-red-700">
            {listError}
          </p>}
          {!listLoading && leads?.items.length === 0 && <EmptyState icon={UserRound} title="Nenhum lead encontrado" description="Ajuste a busca ou importe leads na página Prospecção." />}
          <ul className="mt-3 space-y-1" aria-label="Leads disponíveis" aria-busy={listLoading}>
            {leads?.items.map(lead => <li key={lead.id}>
              <button type="button" disabled={busy || saving || listLoading} aria-pressed={selected === lead.id} onClick={() => selected !== lead.id && protect(() => void selectLead(lead.id))} className={`w-full rounded-lg border p-3 text-left transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600 disabled:opacity-60 ${selected === lead.id ? "border-blue-200 bg-blue-50" : "border-transparent hover:bg-slate-50"}`}>
                <span className="block break-words text-sm font-semibold text-slate-800">
                  {lead.company}
                </span>
                <span className="mt-1 block truncate text-xs text-slate-500">
                  {lead.niche || "Segmento não informado"}
                </span>
              </button>
            </li>)}
          </ul>
          {leads && leads.total > leads.pageSize && <div className="mt-4 flex items-center justify-between gap-2 border-t pt-4">
            <Button className="px-2 text-xs" variant="outline" disabled={page === 1 || listLoading} onClick={() => setPage(p => p - 1)}>Anterior</Button>
            <span className="text-xs text-slate-500">
              {page}
              /
              {Math.ceil(leads.total / leads.pageSize)}
            </span>
            <Button className="px-2 text-xs" variant="outline" disabled={page * leads.pageSize >= leads.total || listLoading} onClick={() => setPage(p => p + 1)}>Próxima</Button>
          </div>}
        </CardContent>
      </Card>
      <div className="min-w-0 space-y-5">
        {error && <p role="alert" className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800">
          {error}
        </p>}
        {contextLoading ? <Card>
          <div role="status" className="flex items-center gap-2 p-8 text-sm text-slate-500">
            <LoaderCircle size={18} className="animate-spin" />
            Carregando dados do lead…
          </div>
        </Card> : !context ? <Card>
          <EmptyState icon={MessageSquare} title="Escolha com quem conversar" description="Selecione um lead da carteira para ver os dados e preparar uma abordagem. Nenhuma mensagem é enviada automaticamente." />
        </Card> : <>
          <SdrLeadSummary lead={context} />
          <Card>
            <CardHeader>
              <CardTitle>Prepare a abordagem</CardTitle>
              <p className="mt-1 text-xs text-slate-500">A configuração Groq existente é utilizada pelo backend.</p>
            </CardHeader>
            <CardContent>
              <div className="grid gap-4 sm:grid-cols-2">
                <label htmlFor="recipient">
                  Destinatário provável
                  <select id="recipient" className="field mt-2" value={recipient} disabled={busy || saving} onChange={e => setRecipient(e.target.value as GenerateRequest["recipient"])}>
                    <option value="auto">
                      Automático ·{" "}
                      {contactLabels[context.contactType]}
                    </option>
                    <option value="direct">Responsável/proprietário</option>
                    <option value="reception">Recepção/equipe</option>
                    <option value="unknown">Desconhecido</option>
                  </select>
                </label>
                <label htmlFor="service">
                  Serviço a apresentar
                  <select id="service" className="field mt-2" value={service} disabled={busy || saving} onChange={e => setService(e.target.value as GenerateRequest["service"])}>
                    <option value="auto">Sugerir uma solução adequada</option>
                    <option value="website">Site profissional</option>
                    <option value="landing">Landing page</option>
                    <option value="management">Sistema de gestão</option>
                    <option value="crm">CRM personalizado</option>
                    <option value="automation">Automações e integrações digitais</option>
                  </select>
                </label>
              </div>
              <label htmlFor="instruction" className="mt-4 block">
                Orientação de redação
                <span className="font-normal text-slate-400">· opcional</span>
                <input id="instruction" className="field mt-2" placeholder="Ex.: use uma abertura mais breve e formal" value={instruction} maxLength={500} disabled={busy || saving} onChange={e => setInstruction(e.target.value)} />
              </label>
              <div className="mt-4 flex flex-wrap items-center gap-3">
                <Button disabled={busy || saving || context.blocked} onClick={() => protect(() => void generate())}>
                  {busy ? <LoaderCircle className="animate-spin" /> : <Sparkles />}
                  {busy ? "Gerando abordagem…" : draft ? "Regenerar com IA" : "Gerar abordagem com IA"}
                </Button>
                <span className="text-xs text-slate-500">
                  {draft ? "Cria outra versão; o histórico salvo é preservado." : "Cria um rascunho editável, sem salvar ou enviar."}
                </span>
              </div>
              {context.blocked && <p className="mt-3 text-sm text-red-700">
                {context.whatsappReason}
              </p>}
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="flex flex-wrap items-center justify-between gap-3">
              <CardTitle>Revise a mensagem</CardTitle>
              <span className="rounded-full bg-blue-50 px-3 py-1 text-xs text-blue-700">
                {savedStatus === "APROVADA" ? "Versão aprovada" : !dirty && savedMessage ? "Texto salvo" : draft ? "Rascunho não salvo" : "Editor local"}
              </span>
            </CardHeader>
            <CardContent>
              {draft && <p className="mb-3 text-xs leading-5 text-slate-500">
                Abordagem:{" "}
                {draft.angle}
                {" · "}
                {contactLabels[draft.contactType]}
              </p>}
              <label htmlFor="message" className="sr-only">Mensagem para revisão</label>
              <textarea id="message" className="field min-h-64 resize-y !leading-7" placeholder="Gere uma abordagem ou escreva uma mensagem para este lead…" value={message} disabled={busy || saving} readOnly={savedStatus === "APROVADA"} onChange={e => { setMessage(e.target.value); setFeedback(""); }} aria-describedby="message-help message-count" />
              <div className="mt-2 flex justify-between gap-3 text-xs text-slate-500">
                <span id="message-help">
                  {savedStatus === "APROVADA" ? "Gere outra versão para editar e preservar esta aprovação." : "Revise os fatos. O texto só é salvo quando você solicita."}
                </span>
                <span id="message-count" className={`shrink-0 ${count > 1200 ? "font-semibold text-red-700" : ""}`}>
                  {count}
                  / 1200
                </span>
              </div>
              <div className="mt-5 flex flex-wrap items-center justify-between gap-3 border-t pt-5">
                <Button variant="outline" disabled={!message.trim() || busy} onClick={copy}>
                  <Copy />
                  Copiar mensagem
                </Button>
                {link ? <Button asChild>
                  <a href={link} target="_blank" rel="noopener noreferrer" aria-describedby="whatsapp-help">
                    <ExternalLink />
                    Abrir WhatsApp
                  </a>
                </Button> : <Button disabled aria-describedby="whatsapp-help">
                  <ExternalLink />
                  Abrir WhatsApp
                </Button>}
              </div>
              <p id="whatsapp-help" className="mt-3 text-xs leading-5 text-slate-500">
                {context.whatsappReason || (!message.trim() ? "Escreva ou gere uma mensagem para abrir o WhatsApp." : count > 1200 ? "Reduza a mensagem para até 1200 caracteres." : "Abre uma nova aba com o texto preenchido. Confira o destinatário e envie manualmente no WhatsApp.")}
              </p>
              <div className="mt-5 flex flex-wrap gap-2">
                <Button className="text-xs" variant="outline" disabled={!canSave || busy || saving} onClick={() => void save("EDITADA")}>
                  {saving && <LoaderCircle className="animate-spin" />}
                  Salvar texto revisado
                </Button>
                <Button className="text-xs" variant="outline" disabled={!canSave || busy || saving} onClick={() => void save("APROVADA")}>Aprovar e salvar versão</Button>
              </div>
              {history?.reason && <p className="mt-2 text-xs leading-5 text-slate-500">
                {history.reason}
              </p>}
              {!draft && message.trim() && <p className="mt-2 text-xs text-slate-500">Este texto pode ser copiado ou aberto no WhatsApp. O salvamento está disponível para versões geradas nesta sessão.</p>}
              {feedback && <p role="status" className="mt-4 rounded-lg bg-blue-50 p-3 text-sm text-blue-800">
                {feedback}
              </p>}
            </CardContent>
          </Card>
          <SdrHistoryPanel history={history} busy={busy || saving} onLoad={text => protect(() => {
            setMessage(text); setSavedMessage(text); setSavedStatus(""); setDraft(null);
            setFeedback("Versão carregada para consulta e cópia; o registro original foi preservado.");
          })} />
        </>}
      </div>
    </div>
    <PendingMessageDialog open={!!pending} saving={saving} canSave={canSave} reason={history?.reason} error={error}
      onClose={() => setPending(null)}
      onDiscard={() => { const action = pending; setPending(null); action?.(); }}
      onSave={async () => { if (await save("EDITADA")) { const action = pending; setPending(null); action?.(); } }} />
  </>;
}
