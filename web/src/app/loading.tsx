export default function Loading() {
  return (
    <div
      role="status"
      aria-label="Carregando página"
      className="animate-pulse space-y-6"
    >
      <div className="h-9 w-2/3 rounded bg-slate-200" />
      <div className="grid gap-4 sm:grid-cols-3">
        {[1, 2, 3].map((i) => (
          <div key={i} className="h-36 rounded-xl border bg-white" />
        ))}
      </div>
      <div className="h-72 rounded-xl border bg-white" />
      <span className="sr-only">Carregando…</span>
    </div>
  );
}
