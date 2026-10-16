import { RefreshCw, Database } from "lucide-react";
import { Button } from "./ui/button";
import type { ApiResult } from "@/lib/api/contracts";
export function ReadStatus({
  result,
  refresh,
}: {
  result: ApiResult<unknown> | null;
  refresh: () => void;
}) {
  if (result?.status === "ready")
    return (
      <div className="mb-5 flex items-center gap-2 text-xs text-slate-500">
        <Database size={14} />
        Base local · somente leitura
      </div>
    );
  if (!result)
    return (
      <p role="status" className="mb-5 animate-pulse text-sm text-slate-500">
        Carregando dados da base local…
      </p>
    );
  return (
    <div
      role="alert"
      className="mb-5 flex flex-wrap items-center justify-between gap-3 rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900"
    >
      <p>{result.message}</p>
      <Button variant="outline" onClick={refresh}>
        <RefreshCw />
        Tentar novamente
      </Button>
    </div>
  );
}
