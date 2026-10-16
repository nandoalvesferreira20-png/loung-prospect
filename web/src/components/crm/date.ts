export const localTimezone = () => Intl.DateTimeFormat().resolvedOptions().timeZone;
const hasOffset = (value: string) => /(?:Z|[+-]\d{2}:\d{2})$/i.test(value);
export function dateLabel(value: string | null) {
  if (!value) return "Sem data";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "Data inválida na origem" : !hasOffset(value) ? `${value} · fuso não informado` : date.toLocaleString("pt-BR");
}
export function localInput(value: string | null) {
  if (!value || !hasOffset(value) || Number.isNaN(new Date(value).getTime())) return "";
  const date = new Date(value);
  return new Date(date.getTime() - date.getTimezoneOffset()*60000).toISOString().slice(0,16);
}
