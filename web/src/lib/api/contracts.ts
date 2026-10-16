import type { SearchJob } from "./prospecting-contracts";
import type { GenerateRequest, SdrDraft } from "./sdr-contracts";
export const commercialStages = [
  "Novo",
  "Contato realizado",
  "Em conversa",
  "Reunião agendada",
  "Proposta enviada",
  "Fechado",
] as const;
export type ContactRole = "reception" | "direct" | "unknown";
export interface Lead {
  id: number;
  company: string;
  phone: string | null;
  niche: string | null;
  website: string | null;
  location: string | null;
  stage: string;
  contactRole: ContactRole;
  originalStage: string | null;
  score: number | null;
  nextContact: string | null;
  nextAction: string | null;
}
export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  pageSize: number;
  stages: string[];
}
export interface LeadFilters {
  q?: string;
  stage?: string;
  page?: number;
  pageSize?: number;
}
export interface Overview {
  total: number;
  today: number;
  overdue: number;
  meetings: number;
  referenceDate: string;
  invalidDates: number;
  stageCounts: { stage: string; count: number }[];
  actions: Lead[];
}
export interface ProspectRequest {
  niche: string;
  location: string;
  quantity: number;
}
export type DraftRequest = GenerateRequest;
export type ApiResult<T> =
  | { status: "ready"; data: T }
  | { status: "not-connected"; message: string }
  | { status: "error"; message: string };
export interface ProspectApi {
  listLeads(
    filters?: LeadFilters,
    signal?: AbortSignal,
  ): Promise<ApiResult<Page<Lead>>>;
  overview(signal?: AbortSignal): Promise<ApiResult<Overview>>;
  prospect(request: ProspectRequest): Promise<ApiResult<SearchJob>>;
  generateDraft(request: DraftRequest): Promise<ApiResult<SdrDraft>>;
}
