# Arquitetura atual

Data: 23/10/2026. Evidências de código, sem execução dos fluxos integrados ou inspeção do banco real.

## Diagrama textual

```text
Navegador
 ├─ Supabase Auth: login, recuperação e sessão via SDK
 └─ Next.js App Router / React / TypeScript (web/)
     ├─ proxy.ts: getUser, refresh dos cookies e redirects
     └─ /api/* BFF: origem local, contrato, timeout, Bearer
         └─ FastAPI em loopback (backend/)
             ├─ modo postgres, padrão pelo ambiente
             │   ├─ JWT JWKS → memberships → ContextVar Identity
             │   ├─ CRM / SDR / PgJobManager por organização
             │   └─ psycopg → SET LOCAL ROLE loung_api
             │       + claims e organização locais à transação
             │       → PostgreSQL/Supabase: RLS, FKs e triggers
             ├─ Google Places New HTTPS → qualificação → resultados
             └─ Groq HTTPS → JSON validado → draft → revisão humana

Legado separado: app.py / main.py → ui/ → core/ → SQLite / Playwright / Excel
```

`Settings` construído diretamente tem default sqlite; `Settings.from_environment` usa postgres por padrão. `backend/main.py:create_app` mantém ambos. Não há fallback automático PostgreSQL→SQLite.

## Organização

| Pasta | Responsabilidade |
|---|---|
| web/src/app | Páginas, layouts, erros e handlers BFF |
| web/src/components | Shell, dashboard, tabela/editor de leads, prospecção, CRM e SDR |
| web/src/lib/api | Contratos Zod, proxies, fetch e estado de recursos |
| web/src/lib/auth | Clientes Supabase server/browser, configuração pública e erros |
| backend | Montagem FastAPI, configuração, autorização e repositório de leitura |
| backend/crm | Pipeline, atividades, follow-ups, métricas e mutações |
| backend/prospecting | Contratos, jobs, importação e exportação |
| backend/sdr | Contexto, geração, cache, política e salvamento explícito |
| backend/persistence | Runtime PostgreSQL, adaptação SQL, equipe e sessão |
| core | Regras compartilhadas: banco legado, qualificação, Places, vendas e importadores |
| ui | Interface desktop; fora do caminho HTTP SaaS |
| supabase/migrations | Esquema, RLS, grants, equipe e reparo de autoria, aplicados manualmente |
| tests, backend/tests, web/scripts | Testes, fixtures e diagnósticos |

## Rotas Next

Dashboard `/`; `/prospeccao`; `/leads`; `/leads/novo`; `/leads/[id]`; `/leads/[id]/editar`; `/sdr`; `/pipeline`; `/meu-dia`; `/configuracoes`; `/configuracoes/equipe`; `/configuracoes/atividades`. Autenticação: `/login`, `/recuperar-senha`, `/atualizar-senha`, `/auth/confirm`.

## Endpoints FastAPI

| Grupo | Métodos e caminhos |
|---|---|
| Operação/sessão | GET `/health`, `/v1/session` (sessão apenas postgres) |
| Leitura | GET `/v1/leads`, `/v1/leads/{id}`, `/v1/overview` |
| Edição manual | POST `/v1/leads`, GET `/v1/leads/{id}/edit`, PATCH `/v1/leads/{id}` (postgres) |
| CRM leitura | GET `/v1/pipeline`, `/v1/crm/leads/{id}`, `/v1/leads/{id}/activities`, `/v1/followups`, `/v1/dashboard/commercial` |
| CRM escrita | PATCH `/v1/leads/{id}/stage`; POST `/v1/leads/{id}/activities`, `/v1/leads/{id}/followups`; PATCH `/v1/followups/{id}` |
| Prospecção | POST `/v1/prospecting/search`; GET `/v1/prospecting/search/{id}`, `/{id}/results`, `/{id}/export`; POST `/{id}/cancel`; POST `/v1/leads/import` |
| SDR | GET `/v1/sdr/leads/{id}`, `/v1/sdr/history/{id}`; POST `/v1/sdr/generate`, `/v1/sdr/history` |
| Equipe | GET `/v1/team`; PATCH/DELETE `/v1/team/{user_id}`; GET `/v1/organization/activities` (postgres) |

Referências: `backend/main.py`, `backend/persistence/runtime.py`, `backend/persistence/leads.py`, `backend/persistence/team.py` e `backend/{crm,prospecting,sdr}/routes.py`. No runtime postgres, todos exceto health passam pelo middleware JWT/membership. SQLite só aplica restrições de Host/Origin, sem identidade equivalente.

`web/src/app/api` contém handlers correspondentes; proxies traduzem alguns caminhos, validam campos e filtram parâmetros. O perfil de lead usa o recurso CRM. Não encaminham URLs upstream arbitrárias do usuário.

## Fluxos principais

**Login/leitura:** SDK autentica; proxy Next chama getUser; BFF confirma usuário e obtém sessão; encaminha access_token; backend verifica assinatura/claims e memberships; seleciona org; cada conexão SQL estabelece role/contexto e revalida membership. Consultas por ID sem filtro explícito de org dependem de RLS.

**CRM:** formulário envia revision; contrato valida campos; writer obtém advisory lock da organização; busca lead sob RLS; compara hash e devolve 409 em conflito. Atualização/interação são atômicas com triggers de autoria/auditoria. Pipeline usa status de leads: não foi identificada entidade oportunidade/deal independente.

**Busca:** POST cria job e snapshot inicial; copy_context leva Identity à thread. Places é consultado em páginas; staging SQLite `:memory:` deduplica o job. Snapshot final vai ao PostgreSQL. Importação selecionada grava sob RLS. Export usa manager da org. Não há evidência de export completo da organização.

**SDR:** lead/histórico autorizados → evidência limitada → Groq → JSON/domínio validado → draft em memória. Salvar/aprovar é explícito; versões e revisões ficam no banco. WhatsApp abre link externo e envio é humano.

**Equipe:** roster via função SQL restrita; owner altera/remove outros integrantes. Função revalida autoridade e organização na transação, protege último owner e audita. Convite e criação de organização permanecem operacionais/manuais.

## Esquema, índices e transações

`202610190001_phase31.sql` define organizations, profiles ligados a auth.users e organization_members com papéis owner/admin/member e unicidade org/user. Leads, lead_interactions, outreach, outreach_revisions, lead_contact_preferences, template_drafts, prospecting_searches, organization_settings, commercial_stages e audit_events levam organization_id. Migration_map registra migração por org/origem/tabela/ID legado e não é público.

FKs compostas org/lead e org/outreach/lead impedem cruzar relações entre tenants. Há índice único parcial provider/place por org, índices de estágio, próximo contato, filhos por lead e auditoria org/lead/data. Históricos têm grants append-only pertinentes; runtime não recebe DELETE comercial geral.

Datas comerciais legadas continuam text; metadados novos usam timestamptz. `julianday` tolera valores inválidos devolvendo NULL. Empresa tem CHECK de tamanho, mas falta NOT NULL: em SQL o CHECK não rejeita NULL. APIs validam nome; cargas administrativas precisam controle. Índice de membership inicia em organization_id, não user_id; buscas não têm índice explícito org/created_at. Validar EXPLAIN/carga antes de prescrever novos índices.

`Database.open` cria conexão por operação, ro em REPEATABLE READ/read_only; configura transação local e retorna erros sanitizados. Writer usa commit/rollback e advisory lock por org. Não foi identificado pool explícito ou timeout SQL/lock no runtime. Gestão de owner acrescenta serialização MVCC na função SQL.

## Inicialização e dependências

`web/package.json`: Next 16.4.2 e React 19.3.1 declarados, Node ^22.19.0 ou >=24.6.0, scripts dev/build/start/lint/typecheck; start/dev em 127.0.0.1. `backend/requirements.txt`: FastAPI, uvicorn, psycopg, PyJWT, Groq, pandas/openpyxl, dotenv e truststore Windows. Requirements raiz incluem desktop/Playwright.

`backend/scripts/run_api.py` exige env-file explícito e usa loopback. Configuração do backend não carrega .env implicitamente no startup; providers ainda chamam `core/providers/environment.py:load_environment`, lendo .env raiz no uso sem sobrescrever o ambiente. Esse detalhe de precedência precisa entrar no runbook comercial.

JWT/Next geram diagnósticos sanitizados e alguns IDs; jobs registram eventos/contagens; SQL classifica falhas; Server-Timing mede etapas. Tracing distribuído, monitoramento externo, topologia implantada, backup e SLA não foram confirmados.
