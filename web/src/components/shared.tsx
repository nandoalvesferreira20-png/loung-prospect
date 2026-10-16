import { CircleDashed, Unplug, type LucideIcon } from "lucide-react";
import type { ReactNode } from "react";
export function PageHeader({
  eyebrow,
  title,
  description,
  action,
}: {
  eyebrow: string;
  title: string;
  description: string;
  action?: ReactNode;
}) {
  return (
    <header className="mb-7 flex flex-wrap items-start justify-between gap-4">
      <div>
        <p className="mb-2 text-[11px] font-bold tracking-[.16em] text-blue-600">
          {eyebrow}
        </p>
        <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">
          {title}
        </h1>
        <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-500">
          {description}
        </p>
      </div>
      {action}
    </header>
  );
}
export function EmptyState({
  title,
  description,
  icon: Icon = CircleDashed,
  action,
}: {
  title: string;
  description: string;
  icon?: LucideIcon;
  action?: ReactNode;
}) {
  return (
    <div className="flex min-h-60 flex-col items-center justify-center px-5 py-10 text-center">
      <div className="mb-4 rounded-xl bg-slate-50 p-3 text-slate-400">
        <Icon size={24} />
      </div>
      <h3 className="text-sm font-semibold">{title}</h3>
      <p className="mt-2 max-w-sm text-sm leading-6 text-slate-500">
        {description}
      </p>
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}
export function ConnectionNotice() {
  return (
    <aside className="mb-6 flex items-start gap-3 rounded-lg border border-blue-100 bg-blue-50/60 px-4 py-3 text-xs leading-5 text-blue-900">
      <Unplug size={16} className="mt-0.5 shrink-0" />
      <p>
        <strong>Integração parcial.</strong> Prospecção, leads e indicadores
        estão disponíveis. SDR, Pipeline e Meu Dia usam a API local; alterações
        comerciais exigem permissão de escrita no backend.
      </p>
    </aside>
  );
}
