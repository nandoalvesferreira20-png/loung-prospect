import { notFound } from "next/navigation";
import { LeadProfile } from "@/components/crm/lead-profile";
export default async function LeadPage({params}: {params: Promise<{id: string}>}) {
  const {id}=await params;
  if (!/^[1-9]\d{0,14}$/.test(id)) notFound();
  return <LeadProfile key={id} id={Number(id)} />;
}
