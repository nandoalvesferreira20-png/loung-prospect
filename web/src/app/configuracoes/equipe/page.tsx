"use client";
import {useCallback,useEffect,useState} from "react";
import Link from "next/link";
import {PageHeader} from "@/components/shared";
import {useSession} from "@/components/session-provider";
type Member={userId:string;displayName:string;email:string|null;role:"owner"|"admin"|"member";status:string};
type Team={items:Member[];canManage:boolean;writesEnabled:boolean};
export default function TeamPage(){
  const session=useSession();const [team,setTeam]=useState<Team|null>(null);const [error,setError]=useState("");const [busy,setBusy]=useState(false);
  const load=useCallback(async()=>{const r=await fetch("/api/team",{cache:"no-store"});const data=await r.json();if(!r.ok)throw Error(data.detail);return data as Team;},[]);
  useEffect(()=>{let alive=true;load().then(data=>{if(alive)setTeam(data);}).catch(e=>{if(alive)setError(e instanceof Error?e.message:"Equipe indisponivel.");});return()=>{alive=false;};},[load]);
  async function change(member:Member,role?:string){
    if(!window.confirm(role?`Alterar o papel de ${member.displayName} para ${role}?`:`Remover o acesso de ${member.displayName}?`))return;
    setBusy(true);setError("");
    try{const r=await fetch(`/api/team/${member.userId}`,{method:role?"PATCH":"DELETE",headers:{"Content-Type":"application/json"},...(role?{body:JSON.stringify({role})}:{})});const result=await r.json();if(!r.ok)throw Error(result.detail);setTeam(await load());}catch(e){setError(e instanceof Error?e.message:"Não foi possível salvar.");}finally{setBusy(false);}
  }
  return <><PageHeader eyebrow="CONFIGURAÇÕES" title="Equipe" description="Contas individuais, carteira compartilhada e acessos da organização."/><div className="rounded-xl border bg-white p-5 space-y-5">
    <Link href="/configuracoes" className="text-blue-600 text-sm">Voltar às configurações</Link>
    {error&&<p role="alert" className="text-red-700">{error}</p>}
    {!team&&!error&&<p role="status">Consultando integrantes…</p>}
    {team&&!team.writesEnabled&&<p className="text-sm text-slate-600">Modo de leitura. Alterações de acesso estão desabilitadas.</p>}
    {team&&<div className="overflow-x-auto"><table className="w-full text-left text-sm"><thead><tr>{["Nome","E-mail","Papel","Acesso","Ações"].map(x=><th key={x} className="p-3 border-b">{x}</th>)}</tr></thead><tbody>{team.items.map(m=><tr key={m.userId}><td className="p-3">{m.displayName}</td><td className="p-3">{m.email??"Não informado"}</td><td className="p-3">{m.role}</td><td className="p-3">Vinculado</td><td className="p-3">{team.canManage&&m.userId!==session?.userId?<div className="flex gap-3"><select aria-label={`Papel de ${m.displayName}`} value={m.role} disabled={busy||!team.writesEnabled} onChange={e=>void change(m,e.target.value)} className="field"><option value="owner">Owner</option><option value="admin">Admin</option><option value="member">Member</option></select><button disabled={busy||!team.writesEnabled} onClick={()=>void change(m)} className="text-red-700 disabled:opacity-40">Remover acesso</button></div>:<span className="text-slate-500">{m.userId===session?.userId?"Sua conta":"—"}</span>}</td></tr>)}</tbody></table></div>}
    <p className="text-sm leading-6 text-slate-500">Novos integrantes são convidados pelo operador no Supabase Auth e vinculados após validação da conta. Esta tela não envia convites. “Vinculado” indica membership; a validade da sessão é verificada pelo Supabase Auth.</p>
    {(session?.role==="owner"||session?.role==="admin")&&<Link className="inline-block text-blue-600" href="/configuracoes/atividades">Consultar atividades da organização →</Link>}
  </div></>;
}
