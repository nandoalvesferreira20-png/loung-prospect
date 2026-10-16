import { z } from "zod";
export const searchSchema = z
  .object({
    niche: z
      .string()
      .trim()
      .min(2, "Informe um nicho com pelo menos 2 caracteres.")
      .max(160),
    location: z.string().trim().min(2, "Informe a cidade e o estado.").max(160),
    quantity: z
      .number()
      .int()
      .min(1, "Mínimo de 1 empresa.")
      .max(100, "Máximo de 100 empresas."),
    neighborhood: z.string().trim().max(120).default(""),
    onlyWithoutWebsite: z.boolean().default(false),
    minScore: z.number().int().min(0).max(100).default(60),
  })
  .strict();
export const importSchema = z
  .object({
    searchId: z.string().regex(/^[0-9a-f]{32}$/),
    resultIds: z.array(z.number().int().min(1).max(100)).min(1).max(100),
  })
  .strict();
export type SearchInput = z.input<typeof searchSchema>;
export interface SearchJob {
  id: string;
  query: z.output<typeof searchSchema>;
  status: "pending" | "running" | "completed" | "failed" | "cancelled";
  found: number;
  scanned: number;
  requestsMade: number;
  pagesFetched: number;
  requested: number;
  cancelRequested: boolean;
  message: string;
  error: string | null;
  writesEnabled: boolean;
  expiresInSeconds: number;
}
export interface SearchResult {
  id: number;
  company: string;
  phone: string | null;
  niche: string | null;
  location: string | null;
  address: string | null;
  website: string | null;
  score: number | null;
  alreadySaved: boolean;
}
export interface SearchResults {
  items: SearchResult[];
  total: number;
  page: number;
  pageSize: number;
}
