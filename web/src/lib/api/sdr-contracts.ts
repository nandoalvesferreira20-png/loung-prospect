import { z } from "zod";

export const generateSchema = z.object({
  leadId: z.number().int().positive(),
  recipient: z.enum(["auto", "direct", "reception", "unknown"]).default("auto"),
  service: z.enum(["auto", "website", "landing", "management", "crm", "automation"]).default("auto"),
  instruction: z.string().max(500).default(""),
  requestId: z.string().uuid(),
  previousDraftId: z.string().uuid().optional(),
}).strict();
export const saveDraftSchema = z.object({
  draftId: z.string().uuid(),
  message: z.string().min(1).max(1200).refine((text) => !!text.trim()),
  status: z.enum(["EDITADA", "APROVADA"]),
}).strict();
export type GenerateRequest = z.infer<typeof generateSchema>;
export type ContactType = "contato_direto" | "recepcao_equipe" | "indefinido";
export const contactLabels: Record<ContactType, string> = {
  contato_direto: "Contato direto", recepcao_equipe: "Recepção/equipe", indefinido: "Desconhecido",
};
export interface SdrContext {
  leadId: number; company: string; niche: string | null; phone: string | null;
  website: string | null; stage: string | null; contactType: ContactType;
  contactSource: string; normalizedPhone: string | null; whatsappReason: string | null; blocked: boolean;
}
export interface SdrDraft {
  draftId: string; leadId: number; message: string; angle: string;
  contactType: ContactType; contactSource: string; state: "generated";
  provider: string; model: string | null;
}
export interface SdrHistory {
  available: boolean; writesEnabled: boolean; reason: string | null;
  items: { id: number; message: string; status: string; createdAt: string; updatedAt: string; angle: string }[];
}
