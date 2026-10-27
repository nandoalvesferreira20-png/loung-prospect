import { AuthConfigurationError } from "./config";
export function authErrorMessage(error: unknown, mode: "login" | "recover" | "update"): string {
  if (error instanceof AuthConfigurationError) return error.message;
  const e = error as {code?: string; name?: string; status?: number; message?: string} | null;
  const code=e?.code ?? (e?.message === "Invalid login credentials" ? "invalid_credentials" : undefined);
  switch (code) {
    case "invalid_credentials": return "E-mail ou senha inválidos. Confira suas credenciais.";
    case "email_not_confirmed": return "Confirme seu e-mail pelo convite recebido antes de entrar.";
    case "session_not_found": case "refresh_token_not_found": case "refresh_token_already_used":
    case "bad_jwt": case "otp_expired": return "Sessão ou link expirado. Entre novamente ou solicite outro link de recuperação.";
    case "over_request_rate_limit": case "over_email_send_rate_limit": return "Muitas tentativas. Aguarde alguns minutos e tente novamente.";
    case "weak_password": return "A senha não atende à política de segurança do projeto. Escolha uma senha mais forte.";
    case "invalid_api_key": return "Configuração de autenticação recusada pelo Supabase. Confira a URL e a chave pública do mesmo projeto.";
  }
  if (e?.name === "AuthSessionMissingError" || e?.status === 401) return "Sessão ausente ou expirada. Entre novamente.";
  if (e?.name === "AuthRetryableFetchError" || error instanceof TypeError) return "Não foi possível conectar ao Supabase. Verifique sua conexão, a URL do projeto e os bloqueios de rede.";
  // Never display raw SDK messages, request bodies or credentials.
  return mode === "login" ? "O Supabase não concluiu o login. Tente novamente; se persistir, verifique a configuração de Auth do projeto." : "Não foi possível concluir a operação de autenticação. Tente novamente ou solicite um novo link.";
}
