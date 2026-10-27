import { PageHeader } from "@/components/shared";
import { LeadsTable } from "@/components/leads-table";
import { Button } from "@/components/ui/button";
import { Download } from "lucide-react";
import Link from "next/link";
export default function Leads() {
  return (
    <>
      <PageHeader
        eyebrow="RELACIONAMENTO"
        title="Sua carteira de leads"
        description="Encontre contatos, revise informações e acompanhe cada oportunidade."
        action={
          <div className="text-right">
            <Button asChild className="mr-3"><Link href="/leads/novo">Criar lead</Link></Button>
            <Button variant="outline" disabled>
              <Download />
              Exportar leads
            </Button>
            <p className="mt-2 text-[11px] text-slate-500">
              Exportação da carteira ainda não disponível
            </p>
          </div>
        }
      />
      <LeadsTable />
    </>
  );
}
