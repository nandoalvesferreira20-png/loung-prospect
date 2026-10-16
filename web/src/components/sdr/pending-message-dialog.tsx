"use client";
import * as Dialog from "@radix-ui/react-dialog";
import { Button } from "@/components/ui/button";

export function PendingMessageDialog({ open, saving, canSave, reason, error, onSave, onDiscard, onClose }: {
  open: boolean; saving: boolean; canSave: boolean; reason?: string | null; error: string;
  onSave: () => Promise<void>; onDiscard: () => void; onClose: () => void;
}) {
  return (
    <Dialog.Root open={open} onOpenChange={value => { if (!value && !saving) onClose(); }}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-slate-950/35" />
        <Dialog.Content className="fixed left-1/2 top-1/2 z-50 w-[calc(100%_-_2rem)] max-w-md -translate-x-1/2 -translate-y-1/2 rounded-2xl border bg-white p-6 shadow-xl">
          <Dialog.Title className="text-lg font-semibold">Preservar a mensagem?</Dialog.Title>
          <Dialog.Description className="mt-2 text-sm leading-6 text-slate-500">Há um texto não salvo. Salve o rascunho revisado, descarte esta edição ou continue editando.</Dialog.Description>
          {!canSave && <p className="mt-3 text-xs text-slate-500">{reason || "Este texto não está vinculado a uma versão gerada salvável. Copie-o antes de descartar."}</p>}
          {error && <p role="alert" className="mt-3 text-sm text-red-700">{error}</p>}
          <div className="mt-5 flex flex-wrap gap-2">
            <Button disabled={!canSave || saving} onClick={() => void onSave()}>Salvar e continuar</Button>
            <Button variant="outline" disabled={saving} onClick={onDiscard}>Descartar e continuar</Button>
            <Dialog.Close asChild><Button variant="ghost" disabled={saving}>Continuar editando</Button></Dialog.Close>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
