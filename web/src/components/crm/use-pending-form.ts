"use client";
import { useEffect } from "react";
const pendingForms = new Set<symbol>();
const warn = (event: BeforeUnloadEvent) => {event.preventDefault(); event.returnValue="";};
const navigate = (event: MouseEvent) => {
  const anchor = (event.target as Element).closest("a[href]") as HTMLAnchorElement | null;
  if (!anchor || anchor.target === "_blank" || event.ctrlKey || event.metaKey || anchor.origin !== location.origin || anchor.pathname === location.pathname) return;
  if (!confirm("Há alterações não salvas. Deseja sair e descartá-las?")) {event.preventDefault();event.stopPropagation();}
};
export function usePendingForm(dirty: boolean) {
  useEffect(() => {
    if (!dirty) return;
    const token=Symbol();
    pendingForms.add(token);
    if (pendingForms.size === 1) {window.addEventListener("beforeunload",warn); document.addEventListener("click",navigate,true);}
    return () => {
      pendingForms.delete(token);
      if (!pendingForms.size) {window.removeEventListener("beforeunload",warn);document.removeEventListener("click",navigate,true);}
    };
  },[dirty]);
}
