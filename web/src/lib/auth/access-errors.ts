// Whitelisted diagnostic codes only: never forward raw backend/driver bodies.
export const accessFailures: Record<string,string> = {
  BACKEND_NOT_CONFIGURED: "O FastAPI iniciou sem SUPABASE_URL ou LOUNG_POSTGRES_DSN. Reinicie o backend carregando explicitamente o arquivo de ambiente.",
  DB_DNS_FAILED: "O backend não conseguiu resolver o endereço PostgreSQL. Confira o host da DSN no painel Connect do Supabase.",
  DB_LOGIN_REJECTED: "O PostgreSQL recusou o login restrito. Revise a configuração de conexão do backend.",
  DB_POOLER_USER_FORMAT: "O pooler recusou o identificador de conexão. Confira o formato loung_web.PROJECT_REF no painel Connect.",
  DB_PERMISSION_DENIED: "O papel restrito não possui uma permissão necessária. Revise os grants autorizados; não use uma conta administrativa como alternativa.",
  DB_SCHEMA_MISSING: "O backend não encontrou uma estrutura PostgreSQL necessária. Confira o projeto e as migrations aplicadas, sem executá-las automaticamente.",
  DB_NETWORK_UNREACHABLE: "O backend não alcança a rede do PostgreSQL. Confira a conectividade IPv4/IPv6 e o modo de conexão.",
  DB_CONNECTION_FAILED: "Não foi possível conectar ao PostgreSQL. Confira o endpoint, TLS e a conectividade do backend.",
  DB_UNAVAILABLE: "A persistência PostgreSQL está indisponível. Tente novamente após verificar o backend.",
  BFF_REQUIRED: "O FastAPI recusou a origem da requisição. Acesse o sistema pelo Next.js BFF.",
};
export function accessFailure(code:unknown){return typeof code === 'string' && Object.hasOwn(accessFailures,code) ? {code,detail:accessFailures[code]} : null;}
