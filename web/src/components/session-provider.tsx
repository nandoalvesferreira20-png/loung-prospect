"use client";
import {createContext,useContext,useEffect,useState} from "react";
import {usePathname,useRouter} from "next/navigation";
import {browserAuth} from "@/lib/auth/browser";
type Session={userId?:string;displayName:string;organization:string;role:string;writesEnabled?:boolean};
const Context=createContext<Session|null>(null);
export const useSession=()=>useContext(Context);
export function SessionGate({children,local=false}:{children:React.ReactNode;local?:boolean}){
  const path=usePathname();const router=useRouter();
  const publicRoute=["/login","/recuperar-senha","/atualizar-senha"].includes(path);
  const [session,setSession]=useState<Session|null>(null);const [error,setError]=useState("");
  useEffect(()=>{
    if(publicRoute)return;
    let alive=true;
    const controller=new AbortController();
    async function load(){
      try{
        const response=await fetch("/api/session",{cache:"no-store",signal:controller.signal});
        if(!alive)return;
        if(response.status===401 && !local){router.replace("/login?expired=1");return;}
        const data=await response.json();
        if(alive){if(response.ok){setSession(data);setError("");}else{setSession(null);setError(data.detail??"Acesso indisponível.");}}
      }catch{if(alive)setError("Não foi possível verificar o acesso. Atualize a página.");}
    }
    void load();const timer=setInterval(()=>void load(),60000);
    return()=>{alive=false;controller.abort();clearInterval(timer);};
  },[publicRoute,router,local]);
  if(publicRoute)return children;
  if(error)return <main className="mx-auto max-w-lg p-10"><h1 className="text-xl font-semibold">Acesso indisponível</h1><p role="alert" className="my-5">{error}</p><button onClick={()=>window.location.reload()}>Tentar novamente</button>{!local && <button className="ml-6" onClick={()=>void logout()}>Sair</button>}</main>;
  if(!session)return <p role="status" className="p-10">Verificando sessão…</p>;
  return <Context.Provider value={session}>{children}</Context.Provider>;
}
export async function logout(){
  const {error}=await browserAuth().auth.signOut();
  if(error){window.alert("Não foi possível encerrar a sessão. Tente novamente.");return;}
  window.location.replace(new URL("/login",window.location.origin));
}
