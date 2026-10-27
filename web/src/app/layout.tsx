import { isLocalMode } from "@/lib/runtime-mode";
import type { Metadata } from "next";
import { AppShell } from "@/components/app-shell";
import "./globals.css";
import { SessionGate } from "@/components/session-provider";
export const dynamic = "force-dynamic";
export const metadata: Metadata = {
  title: { default: "Loung Prospect", template: "%s | Loung Prospect" },
  description: "Workspace comercial da Loung Tech.",
};
export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="pt-BR">
      <body>
        <SessionGate local={isLocalMode()}><AppShell>{children}</AppShell></SessionGate>
      </body>
    </html>
  );
}
