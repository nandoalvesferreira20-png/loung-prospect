import Link from "next/link";
import { Button } from "@/components/ui/button";
export default function NotFound() {
  return (
    <div className="rounded-xl border bg-white p-10 text-center">
      <p className="text-sm text-blue-600">404</p>
      <h1 className="my-3 text-2xl font-semibold">Página não encontrada</h1>
      <p className="mb-6 text-sm text-slate-500">
        Escolha uma opção na navegação para continuar.
      </p>
      <Button asChild>
        <Link href="/">Voltar ao dashboard</Link>
      </Button>
    </div>
  );
}
