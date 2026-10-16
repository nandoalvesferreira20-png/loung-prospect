import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { contactLabels, type SdrContext } from "@/lib/api/sdr-contracts";

export function SdrLeadSummary({ lead }: { lead: SdrContext }) {
  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="mb-1 text-xs text-slate-500">LEAD SELECIONADO</p>
            <h2 className="break-words text-lg font-semibold text-slate-900">{lead.company}</h2>
            <p className="mt-1 text-sm text-slate-500">{lead.niche || "Segmento não informado"}</p>
          </div>
          <span className="rounded-full bg-slate-100 px-3 py-1 text-xs text-slate-600">{lead.stage || "Sem etapa"}</span>
        </div>
      </CardHeader>
      <CardContent>
        <dl className="grid gap-4 text-sm sm:grid-cols-2">
          <div>
            <dt className="text-xs text-slate-500">Telefone de contato</dt>
            <dd className="mt-1 break-all font-medium">{lead.phone || "Não informado"}</dd>
          </div>
          <div>
            <dt className="text-xs text-slate-500">Site informado na fonte</dt>
            <dd className="mt-1 break-all text-slate-700">{lead.website || "Não informado"}</dd>
          </div>
        </dl>
        <p className="mt-4 text-xs leading-5 text-slate-500">
          Contato provável: <strong className="font-medium text-slate-700">{contactLabels[lead.contactType]}</strong>
          {lead.contactSource === "preferencia_desktop" ? " · preferência salva no desktop" : " · indicação do nicho"}.
          {" "}Isso não confirma cargo ou poder de decisão.
        </p>
      </CardContent>
    </Card>
  );
}
