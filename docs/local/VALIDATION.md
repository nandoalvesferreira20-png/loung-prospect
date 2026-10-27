# Entrega e validação — 26/10/2026

## Resultado

Modo local padrão com SQLite, sem login, cookies Supabase, JWT ou membership. SaaS permanece separado e autenticado. Scripts oficiais escutam em 127.0.0.1. Banco novo é criado vazio; banco existente recebe backup antes da migração aditiva. Nenhum dado remoto foi importado, alterado ou excluído.

A base existente `data/loung_prospect.db` foi inspecionada somente em modo `ro`/`query_only`: `quick_check=ok`, 160 leads já presentes e todas as colunas de leads necessárias. SHA256 antes/depois confirmou ausência de alteração. Continua em `user_version=0`: a migração real ocorrerá no primeiro início autorizado do backend; a suíte só migrou bases sintéticas.

## Testes

| Validação | Resultado |
| --- | --- |
| Núcleo/desktop Python | 1.035 passaram |
| Backend local e testes unitários de segurança/diagnósticos | 143 passaram |
| Node: autenticação SaaS, BFF, prospecção, equipe e modo local | 20 passaram |
| TypeScript `npm run typecheck` | Passou |
| ESLint `npm run lint` | Passou, zero avisos |
| Build Next.js de produção | Passou, incluindo TypeScript |
| Playwright / Edge headless / Windows | Passou, zero erros JavaScript |
| `git diff --check` | Passou; apenas avisos informativos LF/CRLF |

O fluxo pelo navegador usou Next em 127.0.0.1:3138 e `backend.tests.local_fixture_server` em 127.0.0.1:8138. Verificou acesso direto ao Dashboard, criação pela interface, persistência via BFF, Pipeline, Meu Dia, SDR, Configurações, preferências SQLite, redirecionamento de `/login` para `/`, Google Places simulado e CSV/XLSX. URLs externas foram bloqueadas pelo teste.

Os testes de API cobrem também importação/deduplicação, revisão otimista e conflito 409, edição comercial, follow-ups, geração SDR simulada e revisões, persistência após reiniciar, backup/migração, base ocupada e recusa de origens/peers remotos e configurações inválidas. Todas as bases desses testes são temporárias.

Comando da regressão backend validada:

```text
python -m backend.scripts.run_offline_tests backend/tests -q -p no:cacheprovider --ignore=backend/tests/test_auth_schema_acl.py --ignore=backend/tests/test_phase31_postgres.py --ignore=backend/tests/test_phase32_writes.py --ignore=backend/tests/test_phase32_team.py --ignore=backend/tests/test_prospecting_batch.py --ignore=backend/tests/test_stamp_claims_migration.py
```

As seis suítes excluídas dependem do PostgreSQL efêmero das fases anteriores. Não foram concluídas nesta entrega; não houve conexão ao PostgreSQL remoto ou execução de migrations Supabase. Os testes unitários e Node do caminho autenticado passaram.

O ambiente possui dependências Python divididas entre `.venv` e `backend/.venv`. Para a regressão completa do núcleo, o harness temporário acrescentou o site-packages do primeiro ao segundo. Também ajustou somente o modo de criação dos diretórios temporários do pytest (ACLs de diretórios 0700 impediam acesso no sandbox Windows). Nenhum desses ajustes entrou no runtime do produto. `AI_PROVIDER=openai` foi definido apenas no processo de testes para isolar um teste antigo da configuração desktop do operador. O runner bloqueou DNS e sockets externos. Build/Node/Playwright precisaram de subprocessos fora da restrição de spawn do sandbox.

## Arquivos desta implementação

- Configuração/bootstrap/API: `backend/config.py`, `backend/main.py`, `backend/local_database.py`, `backend/local_routes.py`, `backend/prospecting/storage.py`, `backend/scripts/run_api.py`.
- Frontend: `web/src/proxy.ts`, `web/src/lib/runtime-mode.ts`, `web/src/lib/auth/server.ts`, `web/src/app/api/session/route.ts`, `web/src/app/api/local/preferences/route.ts`, `web/src/app/layout.tsx`, `web/src/components/session-provider.tsx`, `web/src/components/lead-editor.tsx`, `web/src/app/configuracoes/page.tsx`.
- Testes: `backend/tests/test_api.py`, `backend/tests/test_local_mode.py`, `backend/tests/local_fixture_server.py`, `web/scripts/auth.test.mjs`, `web/scripts/local.test.mjs`, `web/scripts/check_local.py`, script `test` em `web/package.json`.
- Exemplos/guias: `.env.example`, `backend/.env.example`, `web/.env.example`, `README.md`, `backend/README.md`, `web/README.md`, `docs/local/*`. Exemplos anteriores preservados em `docs/local/saas-env-examples`.
- `web/next-env.d.ts` foi regenerado pelo Next build para apontar aos tipos de produção.

O restante do Git já continha alterações antes desta tarefa; não foi descartado nem atribuído a esta implementação.

## Limites

- Windows foi executado; comandos macOS foram revisados, sem máquina macOS disponível para execução.
- Google Places/Groq foram simulados; credenciais, quotas e conectividade reais não foram testadas.
- Resultados de pesquisa e rascunhos não salvos continuam transitórios. Dados persistidos permanecem no SQLite após reiniciar.
- Configurações de interface são locais; preferências de contato anteriores permanecem na base. Contas/equipes pertencem somente ao modo SaaS.
- O modo local destina-se a uma instância por máquina, usando os launchers loopback. Não publique por túnel ou proxy reverso. As proteções de runtime são adicionais ao bind local dos processos.
- O aviso de depreciação Starlette/httpx já existe na suíte; não impede os testes.

Instalação, comandos para iniciar e retorno ao SaaS: [README.md](README.md). Diagnóstico anterior: [AUDIT.md](AUDIT.md).
