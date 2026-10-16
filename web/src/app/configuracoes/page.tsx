"use client";
import { useState, useSyncExternalStore } from "react";
import Link from "next/link";
import { Settings2, Building2, Plug, Check, ShieldCheck } from "lucide-react";
import { z } from "zod";
import { PageHeader } from "@/components/shared";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
const preferencesSchema = z.object({
  displayName: z
    .string()
    .trim()
    .min(2, "Informe pelo menos 2 caracteres.")
    .max(80, "Use até 80 caracteres."),
  startPage: z.enum(["/", "/prospeccao", "/leads", "/sdr", "/pipeline"]),
});
type Preferences = z.infer<typeof preferencesSchema>;
const key = "loung-prospect:web:preferences:v1";
function subscribe(listener: () => void) {
  window.addEventListener("storage", listener);
  return () => window.removeEventListener("storage", listener);
}
function readStorage() {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}
function parsePreferences(stored: string | null): Preferences {
  try {
    const parsed = preferencesSchema.safeParse(JSON.parse(stored ?? "null"));
    if (parsed.success) return parsed.data;
  } catch {
    /* Ignore malformed local preferences. */
  }
  return { displayName: "", startPage: "/" };
}
export default function Settings() {
  const stored = useSyncExternalStore(subscribe, readStorage, () => null);
  const [draft, setPreferences] = useState<Preferences | null>(null);
  const preferences = draft ?? parsePreferences(stored);
  const [feedback, setFeedback] = useState("");
  function save(e: React.FormEvent) {
    e.preventDefault();
    const parsed = preferencesSchema.safeParse(preferences);
    if (!parsed.success) {
      setFeedback(parsed.error.issues[0].message);
      return;
    }
    try {
      localStorage.setItem(key, JSON.stringify(parsed.data));
      setFeedback("Preferências salvas neste navegador.");
    } catch {
      setFeedback(
        "O navegador bloqueou o armazenamento. As preferências não foram salvas.",
      );
    }
  }
  return (
    <>
      <PageHeader
        eyebrow="SEU WORKSPACE"
        title="Configurações"
        description="Organize suas preferências e acompanhe a preparação das integrações."
      />
      <div className="grid gap-6 xl:grid-cols-[1.3fr_1fr]">
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Settings2 size={17} className="text-blue-600" />
                Preferências locais
              </CardTitle>
            </CardHeader>
            <CardContent>
              <form onSubmit={save} className="space-y-5">
                <label>
                  Seu nome de exibição
                  <input
                    value={preferences.displayName}
                    onChange={(e) =>
                      setPreferences({
                        ...preferences,
                        displayName: e.target.value,
                      })
                    }
                    className="field mt-2"
                    placeholder="Como você prefere ser chamado?"
                    maxLength={80}
                  />
                  <p className="label-help">
                    Guardado somente neste navegador; não cria uma conta.
                  </p>
                </label>
                <label>
                  Atalho de trabalho preferido
                  <select
                    value={preferences.startPage}
                    onChange={(e) =>
                      setPreferences({
                        ...preferences,
                        startPage: e.target.value as Preferences["startPage"],
                      })
                    }
                    className="field mt-2"
                  >
                    <option value="/">Dashboard</option>
                    <option value="/prospeccao">Prospecção</option>
                    <option value="/leads">Leads</option>
                    <option value="/sdr">SDR Inteligente</option>
                    <option value="/pipeline">Pipeline</option>
                  </select>
                </label>
                <Button type="submit">
                  <Check />
                  Salvar preferências
                </Button>
                <Link
                  href={preferences.startPage}
                  className="ml-4 inline-block text-sm font-medium text-blue-600 hover:underline"
                >
                  Abrir atalho escolhido →
                </Link>
                {feedback && (
                  <p role="status" className="text-sm text-blue-700">
                    {feedback}
                  </p>
                )}
              </form>
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Building2 size={17} className="text-blue-600" />
                Organização
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-sm font-semibold">Loung Tech</p>
              <p className="mt-2 text-sm leading-6 text-slate-500">
                Workspace de uso interno. A gestão de empresas, membros e
                permissões será disponibilizada em uma próxima fase.
              </p>
              <div className="mt-4 flex items-start gap-2 rounded-lg bg-slate-50 p-3 text-xs leading-5 text-slate-500">
                <ShieldCheck size={16} className="mt-0.5 shrink-0" />
                Esta fase ainda não possui autenticação. Utilize somente em
                ambiente local.
              </div>
            </CardContent>
          </Card>
        </div>
        <Card className="self-start">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Plug size={17} className="text-blue-600" />
              Integrações
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-5">
            {[
              {
                name: "Google Places",
                tag: "Descoberta de empresas",
                text: "Disponível em Prospecção pelo motor Python existente. Usa a configuração Google Places do backend local.",
              },
              {
                name: "GroqCloud",
                tag: "Geração de abordagens",
                text: "Disponível no SDR Inteligente pelo serviço Python existente. Usa a chave e o modelo configurados no backend.",
              },
            ].map((i) => (
              <div key={i.name} className="rounded-lg border p-4">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <h3 className="text-sm font-semibold">{i.name}</h3>
                  <span className="rounded-full bg-slate-100 px-2 py-1 text-[10px] text-slate-500">
                    Configuração no backend
                  </span>
                </div>
                <p className="mt-1 text-xs text-blue-600">{i.tag}</p>
                <p className="mt-3 text-xs leading-6 text-slate-500">
                  {i.text}
                </p>
              </div>
            ))}
            <p className="text-xs leading-6 text-slate-500">
              Nenhuma chave é solicitada ou exposta no frontend. Os arquivos de
              configuração do desktop permanecem intactos.
            </p>
          </CardContent>
        </Card>
      </div>
    </>
  );
}
