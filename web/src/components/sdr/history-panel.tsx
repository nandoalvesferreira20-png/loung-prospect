import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { SdrHistory } from "@/lib/api/sdr-contracts";

export function SdrHistoryPanel({ history, busy, onLoad }: {
  history: SdrHistory | null;
  busy: boolean;
  onLoad: (message: string) => void;
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Histórico de abordagens</CardTitle>
        <p className="mt-1 text-xs text-slate-500">Até 50 versões salvas. Abrir o WhatsApp não registra um envio.</p>
      </CardHeader>
      <CardContent>
        {history?.items.length ? (
          <ul className="divide-y">
            {history.items.map(item => (
              <li key={item.id} className="py-4 first:pt-0">
                <div className="flex flex-wrap justify-between gap-2 text-xs text-slate-500">
                  <span>{item.actorName || "Autoria legada desconhecida"} / {item.status} · {item.createdAt ? new Date(item.createdAt).toLocaleString("pt-BR") : "Data não informada"}</span>
                  <button className="font-medium text-blue-700 underline-offset-4 hover:underline focus-visible:outline-2 focus-visible:outline-blue-600" disabled={busy} onClick={() => onLoad(item.message)}>Carregar no editor</button>
                </div>
                <p className="mt-2 whitespace-pre-wrap break-words text-sm leading-6 text-slate-600">{item.message}</p>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-slate-500">{history?.available ? "Nenhuma abordagem salva para este lead." : history?.reason || "Não foi possível consultar o histórico."}</p>
        )}
      </CardContent>
    </Card>
  );
}
