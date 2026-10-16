import { PageHeader } from "@/components/shared";
import { FollowupList } from "@/components/crm/followup-list";
export default function MyDay() {
  return <><PageHeader eyebrow="AGENDA COMERCIAL" title="Meu Dia" description="Priorize retornos e organize os próximos passos sem perder o contexto de cada lead." /><FollowupList /></>;
}
