import {LeadEditor} from "@/components/lead-editor";
export default async function EditLead({params}:{params:Promise<{id:string}>}){return <LeadEditor id={(await params).id}/>;}
