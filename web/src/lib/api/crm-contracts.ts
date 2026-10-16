import { z } from "zod";
import type { Lead } from "./contracts";
export interface CommercialLead extends Lead {
  revision: string; lastActivity: {kind: string; at: string} | null;
  lastContact: string | null; notes: string | null; createdAt: string | null;
}
export interface Capabilities { writesEnabled: boolean; reason: string | null }
export interface Pipeline extends Capabilities {
  columns: {stage: string; total: number; offset: number; items: CommercialLead[]}[];
  stages: string[]; niches: string[]; total: number;
}
export interface CommercialDetail extends Capabilities { lead: CommercialLead; stages: string[] }
export interface Activities {
  items: {id: string; kind: string; description: string; at: string | null; origin: "manual" | "record" | "draft"}[];
  total: number; available: boolean;
}
export interface Followups extends Capabilities {
  available: boolean; items: (CommercialLead & {today: boolean; overdue: boolean; hasFollowup: boolean})[];
  total: number; pending?: number; overdue?: number; invalidDates: number; referenceDate?: string; timezone?: string;
}
export interface CommercialMetrics {
  total: number; contacted: number | null; responded: number | null; negotiations: number;
  converted: number; pending: number | null; overdue: number | null; invalidDates: number;
}
const mutation = z.object({ revision: z.string().regex(/^[a-f0-9]{64}$/) });
export const stageSchema = mutation.extend({ stage: z.string().min(1).max(200), confirmed: z.boolean().default(false) }).strict();
export const activitySchema = mutation.extend({
  kind: z.enum(["Observação", "Contato realizado", "Resposta recebida", "Reunião agendada", "Proposta enviada"]),
  description: z.string().trim().min(1).max(4000), confirmed: z.boolean().default(false),
  channel: z.enum(["whatsapp", "telefone", "instagram", "email", "outro"]).default("outro"),
}).strict();
export const followupSchema = mutation.extend({
  action: z.enum(["schedule", "complete"]).default("schedule"),
  dueAt: z.string().datetime({offset: true}).nullable().default(null), note: z.string().max(240).default(""),
}).strict();
