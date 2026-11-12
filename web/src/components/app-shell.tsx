"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import {
  LayoutDashboard,
  Search,
  Users,
  Sparkles,
  Columns3,
  CalendarDays,
  Settings2,
  ArrowUpRight,
  Menu,
  X,
  PanelLeftClose,
} from "lucide-react";
import { useSession, logout } from "@/components/session-provider";
import { cn } from "@/lib/utils";
const navigation = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/prospeccao", label: "Prospecção", icon: Search },
  { href: "/leads", label: "Leads", icon: Users },
  { href: "/sdr", label: "SDR Inteligente", icon: Sparkles },
  { href: "/pipeline", label: "Pipeline", icon: Columns3 },
  { href: "/meu-dia", label: "Meu Dia", icon: CalendarDays },
  { href: "/configuracoes", label: "Configurações", icon: Settings2 },
];
function Brand() {
  return (
    <Link
      href="/"
      aria-label="Loung Prospect — início"
      className="flex items-center gap-3"
    >
      <span>
        <span className="block text-sm font-semibold tracking-tight text-white">Loung Prospect</span>
        <span className="mt-1 block text-[10px] tracking-[.16em] text-neutral-400">LOUNG TECH</span>
      </span>
    </Link>
  );
}
function Sidebar({ close }: { close?: () => void }) {
  const path = usePathname();
  const session = useSession();
  return (
    <div className="sidebar flex h-full flex-col bg-brand-black px-4 py-6 text-neutral-300">
      <div className="px-3">
        <Brand />
      </div>
      <p className="mb-3 mt-9 px-3 text-[10px] font-bold tracking-[.14em] text-neutral-400">
        WORKSPACE
      </p>
      <nav aria-label="Navegação principal" className="space-y-1">
        {navigation.map(({ href, label, icon: Icon }) => (
          <Link
            key={href}
            href={href}
            onClick={close}
            aria-current={path === href ? "page" : href !== "/" && path.startsWith(href + "/") ? "location" : undefined}
            className={cn(
              "flex items-center gap-3 rounded-md px-3 py-2.5 text-sm transition-colors",
              path === href || (href !== "/" && path.startsWith(href + "/"))
                ? "bg-accent/10 font-semibold text-accent ring-1 ring-inset ring-accent/20"
                : "text-neutral-400 hover:bg-white/5 hover:text-white",
            )}
          >
            <Icon size={18} />
            {label}
          </Link>
        ))}
      </nav>
      <div className="mt-auto pt-12">
        <div className="rounded-md border border-white/10 bg-white/5 p-4">
          <p className="text-xs font-semibold">{session?.organization || "Workspace"}</p>
          <p className="mt-1 text-xs leading-5 text-neutral-400">
            Seu espaço de prospecção e relacionamento comercial.
          </p>
          <Link
            href="/configuracoes"
            onClick={close}
            className="mt-3 flex items-center gap-2 text-xs font-semibold text-accent"
          >
            Configurar workspace
            <ArrowUpRight size={14} />
          </Link>
        </div>
        <p className="px-3 pt-5 text-[10px] text-neutral-400">
          Loung Prospect · Web / Uso local
        </p>
      </div>
    </div>
  );
}
export function AppShell({ children }: { children: React.ReactNode }) {
  const [open, setOpen] = useState(false);
  const session=useSession();
  const path = usePathname();
  if (["/login","/recuperar-senha","/atualizar-senha"].includes(path)) return children;
  const label = path.startsWith("/leads/") ? "Perfil comercial" : navigation.find((n) => n.href === path)?.label ?? "Página";
  return (
    <div className="min-h-screen">
      <a
        href="#conteudo"
        className="sr-only fixed left-4 top-4 z-50 rounded bg-white p-3 focus:not-sr-only"
      >
        Pular para o conteúdo
      </a>
      <aside className="fixed inset-y-0 left-0 hidden w-60 border-r border-brand-line lg:block">
        <Sidebar />
      </aside>
      <div className="lg:pl-60">
        <div className="flex h-16 items-center justify-between border-b bg-white px-5 sm:px-8">
          <div className="flex items-center gap-3">
            <Dialog.Root open={open} onOpenChange={setOpen}>
              <Dialog.Trigger
                className="rounded p-2 lg:hidden"
                aria-label="Abrir navegação"
              >
                <Menu size={20} />
              </Dialog.Trigger>
              <Dialog.Portal>
                <Dialog.Overlay className="fixed inset-0 z-40 bg-neutral-900/30" />
                <Dialog.Content className="fixed inset-y-0 left-0 z-50 w-72 max-w-[85vw] shadow-xl">
                  <Dialog.Title className="sr-only">
                    Navegação Loung Prospect
                  </Dialog.Title>
                  <Dialog.Description className="sr-only">
                    Acesse as páginas do workspace.
                  </Dialog.Description>
                  <Sidebar close={() => setOpen(false)} />
                  <Dialog.Close
                    aria-label="Fechar navegação"
                    className="absolute right-3 top-3 rounded p-2 text-white"
                  >
                    <X size={18} />
                  </Dialog.Close>
                </Dialog.Content>
              </Dialog.Portal>
            </Dialog.Root>
            <PanelLeftClose
              size={17}
              className="hidden text-neutral-400 lg:block"
            />
            <span className="text-xs text-neutral-400">
              Workspace <span className="px-2">/</span>
              <span className="font-medium text-neutral-600">{label}</span>
            </span>
          </div>
          <div className="flex min-w-0 items-center gap-3 text-xs text-neutral-500"><span className="max-w-[40vw] truncate">{session?.displayName} · {session?.organization}</span>{session?.role !== "local" && <button className="rounded border px-3 py-2" onClick={() => void logout()}>Sair</button>}</div>
        </div>
        <main
          id="conteudo"
          tabIndex={-1}
          className="mx-auto min-w-0 max-w-[1680px] p-4 outline-none sm:p-6 xl:p-8"
        >
          {children}
        </main>
      </div>
    </div>
  );
}
