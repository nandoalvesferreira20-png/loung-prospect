"use client";
import Link from "next/link";
import { useState } from "react";
import { useReadResource } from "@/lib/api/use-read-resource";
import type { SdrContext, SdrHistory } from "@/lib/api/sdr-contracts";
import { whatsappLink } from "@/lib/sdr-whatsapp";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { usePendingForm } from "./use-pending-form";

export function LeadContactActions({id}: {id: number}) {
  const context=useReadResource<SdrContext>(`/api/sdr/leads/${id}`);
  const history=useReadResource<SdrHistory>(`/api/sdr/history/${id}`);
  const data=context.result?.status === "ready" ? context.result.data : null;
  const previous=history.result?.status === "ready" ? history.result.data.items.find(item => item.status !== "CANCELADA") : null;
  return <Card><CardHeader><CardTitle>Prepare a conversa</CardTitle></CardHeader><CardContent>
    <Button asChild variant="outline"><Link href={`/sdr?leadId=${id}`}>Gerar abordagem com IA no SDR</Link></Button>
    {data && history.result ? <ContactEditor key={previous?.id || "manual"} lead={data} initial={previous?.message || ""} /> : <p className="mt-3 text-sm text-slate-500">{context.result && context.result.status !== "ready" ? context.result.message : "Carregando contexto da abordagem…"}</p>}
  </CardContent></Card>;
}
function ContactEditor({lead,initial}: {lead: SdrContext; initial: string}) {
  const [message,setMessage]=useState(initial);
  const [feedback,setFeedback]=useState("");
  usePendingForm(message !== initial);
  const link=lead.blocked ? null : whatsappLink(lead.normalizedPhone,message);
  return <div className="mt-5">
    <label>Mensagem para revisão<textarea aria-label="Mensagem para revisão" className="field mt-2" value={message} onChange={e => setMessage(e.target.value)} placeholder="Escreva uma mensagem ou gere uma abordagem no SDR." /></label>
    <p className="mt-2 text-xs text-slate-500">{[...message].length} / 1200 · edição local; o histórico salvo é preservado.</p>
    <div className="mt-4 flex flex-wrap gap-3">
      <Button variant="outline" disabled={!message.trim()} onClick={async () => {try {await navigator.clipboard.writeText(message);setFeedback("Mensagem copiada.");} catch {setFeedback("Não foi possível copiar. Selecione o texto e copie manualmente.");}}}>Copiar mensagem</Button>
      {link ? <Button asChild><a href={link} target="_blank" rel="noopener noreferrer">Abrir WhatsApp</a></Button> : <Button disabled>Abrir WhatsApp</Button>}
    </div>
    <p className="mt-3 text-xs leading-5 text-slate-500">{lead.whatsappReason || (!message.trim() ? "Escreva ou gere uma mensagem antes de abrir o WhatsApp." : [...message].length > 1200 ? "Reduza a mensagem para 1200 caracteres." : "Abre uma nova aba com o texto preenchido. O envio é manual e não registra contato automaticamente.")}</p>
    {feedback && <p role="status" className="mt-3 text-sm text-blue-700">{feedback}</p>}
  </div>;
}
