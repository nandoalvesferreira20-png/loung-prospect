"use client";
import { authErrorMessage } from "@/lib/auth/errors";
import { FormEvent, useState, useSyncExternalStore } from "react";
import Link from "next/link";
import {useRouter} from "next/navigation";
import { browserAuth } from "@/lib/auth/browser";
import { Button } from "@/components/ui/button";
const subscribe = () => () => {};
export function AuthForm({mode}:{mode:"login"|"recover"|"update"}) {
  const hydrated=useSyncExternalStore(subscribe,()=>true,()=>false);
  const router=useRouter();
  const expired=hydrated && mode==="login" && new URLSearchParams(window.location.search).has("expired");
  const [email,setEmail]=useState("");const [password,setPassword]=useState("");
  const [busy,setBusy]=useState(false);const [message,setMessage]=useState("");
  async function submit(event:FormEvent) {
    event.preventDefault();if(busy || !hydrated)return;setBusy(true);setMessage("");
    try {
      const auth=browserAuth();
      if(mode==="recover") {
        const {error}=await auth.auth.resetPasswordForEmail(email,{redirectTo:window.location.origin+"/atualizar-senha"});
        if(error) throw error;
        setMessage("Se o e-mail estiver autorizado, você receberá instruções para recuperar o acesso.");
      } else if(mode==="update") {
        const {error}=await auth.auth.updateUser({password});if(error)throw error;
        router.replace("/");
      } else {
        const {error}=await auth.auth.signInWithPassword({email:email.trim(),password});if(error)throw error;
        router.replace("/");
      }
    } catch (error) {setMessage(authErrorMessage(error,mode));}
    finally {setBusy(false);}
  }
  return <main className="mx-auto flex min-h-screen max-w-md items-center px-6"><section className="w-full rounded-2xl border bg-white p-8 shadow-sm"><p className="text-sm font-bold text-blue-600">LOUNG PROSPECT</p><h1 className="mt-5 text-2xl font-semibold">{mode==="login"?"Entrar no workspace":mode==="recover"?"Recuperar acesso":"Definir senha"}</h1><p className="mt-2 text-sm text-slate-500">Acesso exclusivo para membros convidados.</p>{expired && <p className="mt-4 text-sm text-amber-700">Sua sessão expirou ou você ainda não entrou. Informe suas credenciais.</p>}<form onSubmit={submit} className="mt-6 space-y-4">{mode!=="update"&&<label className="block text-sm">E-mail<input className="field mt-2" disabled={!hydrated || busy} type="email" autoComplete="email" required value={email} onChange={e=>setEmail(e.target.value)} /></label>}{mode!=="recover"&&<label className="block text-sm">Senha<input className="field mt-2" disabled={!hydrated || busy} type="password" autoComplete={mode==="login"?"current-password":"new-password"} minLength={mode==="update"?12:1} required value={password} onChange={e=>setPassword(e.target.value)} /></label>}<Button type="submit" disabled={!hydrated || busy} className="w-full">{busy?"Aguarde…":mode==="login"?"Entrar":mode==="recover"?"Enviar instruções":"Salvar senha"}</Button>{message&&<p role="status" className="text-sm text-slate-600">{message}</p>}</form><Link className="mt-5 block text-sm text-blue-600" href={mode==="login"?"/recuperar-senha":"/login"}>{mode==="login"?"Esqueci minha senha":"Voltar ao login"}</Link></section></main>;
}
