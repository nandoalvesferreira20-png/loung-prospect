"use client";
import { Button } from "@/components/ui/button";
export default function ErrorPage({
  reset,
}: {
  error: Error;
  reset: () => void;
}) {
  return (
    <div role="alert" className="rounded-xl border bg-white p-8">
      <h1 className="text-xl font-semibold">
        Não foi possível carregar esta página
      </h1>
      <p className="my-4 text-sm text-slate-500">
        Tente novamente. Nenhuma operação de prospecção foi iniciada.
      </p>
      <Button onClick={reset}>Tentar novamente</Button>
    </div>
  );
}
