import Link from "next/link";
import { ArrowUpRight, Search } from "lucide-react";
import { PageHeader } from "@/components/shared";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { DashboardData } from "@/components/dashboard-data";
import { CommercialDashboard } from "@/components/crm/commercial-dashboard";
import { FollowupList } from "@/components/crm/followup-list";
export default function Dashboard() {
  return (
    <>
      <PageHeader
        eyebrow="VISÃO GERAL"
        title="Uma visão clara da sua operação"
        description="Acompanhe suas oportunidades e organize os próximos passos da prospecção."
        action={
          <Button asChild>
            <Link href="/prospeccao">
              <Search />
              Nova prospecção
            </Link>
          </Button>
        }
      />
      <DashboardData />
      <CommercialDashboard />
      <FollowupList compact />
      <div className="mt-6 grid gap-6">
        <Card>
          <CardHeader>
            <CardTitle>Da descoberta à conversa</CardTitle>
            <p className="mt-1 text-xs text-slate-500">
              Um fluxo simples para sua equipe
            </p>
          </CardHeader>
          <CardContent className="space-y-5">
            {[
              {
                n: "01",
                title: "Encontre as empresas certas",
                text: "Pesquise por nicho e localização.",
                href: "/prospeccao",
              },
              {
                n: "02",
                title: "Organize sua carteira",
                text: "Revise dados e acompanhe cada etapa.",
                href: "/leads",
              },
              {
                n: "03",
                title: "Inicie uma boa conversa",
                text: "Prepare e revise sua abordagem.",
                href: "/sdr",
              },
            ].map((x) => (
              <Link
                href={x.href}
                key={x.n}
                className="group flex items-start gap-3"
              >
                <span className="rounded-lg bg-blue-50 p-2 text-xs font-semibold text-blue-600">
                  {x.n}
                </span>
                <div className="flex-1">
                  <p className="text-sm font-medium group-hover:text-blue-600">
                    {x.title}
                  </p>
                  <p className="mt-1 text-xs leading-5 text-slate-500">
                    {x.text}
                  </p>
                </div>
                <ArrowUpRight size={15} className="mt-1 text-slate-400" />
              </Link>
            ))}
          </CardContent>
        </Card>
      </div>
    </>
  );
}
