# Prontidão para produção

Data: 23/10/2026. Nenhum servidor iniciado, deploy realizado ou configuração real alterada.

## Avaliação operacional

| Tema | Evidência | Estado/necessidade |
|---|---|---|
| Frontend | package.json tem build/start; typecheck passou | Build não executado: grava .next e pode regenerar arquivos; validar futuramente em checkout descartável |
| Backend | main.py e scripts/run_api.py | Bind loopback e Host restrito; topologia pública pendente |
| CORS/origem | FastAPI rejeita Origin; BFF exige Host local/mesma origem | Domínio público recebe 403; não resolver abrindo CORS irrestrito |
| HTTPS | Upstream BFF só permite HTTP loopback; Auth exige HTTPS salvo loopback | Terminação TLS, rede backend e confiança em proxy precisam projeto |
| Sessões | getUser, refresh cookies, Bearer, exp JWT e no-store | TTL/revogação Supabase e cookies efetivos não inspecionados |
| Health | /health retorna status/configured sem round trip SQL | Liveness/configuração, não readiness do banco/Auth |
| Logs | Sanitização SQL/provider, eventos e Server-Timing | Correlação incompleta, sem alertas/monitoramento externo identificados |
| Timeouts | JWKS 5s; DB connect 5s; Places 15s; job 120s; Groq até 30s; BFF 5–40s | Runtime sem statement_timeout/lock_timeout ou pool explícito |
| Processamento | ThreadPoolExecutor por org; snapshots inicial/final | Execução/cache/cancel locais; drafts perdem-se em restart |
| Backups | PgStore assume backup operacional; _backup PostgreSQL indisponível | Plano, PITR e restore atuais não demonstrados |
| CI/CD | Não localizada configuração de workflow/container/deploy no inventário | Pipeline/release reversível pendentes |
| Dependências | npm lock; requirements Python com pins e intervalos | Reprodutibilidade Python e análise de vulnerabilidades pendentes; nenhum pacote atualizado |

## Variáveis e fronteiras

Backend: `LOUNG_STORAGE_BACKEND` (postgres comercial), `LOUNG_POSTGRES_DSN`, `SUPABASE_URL`, `SUPABASE_AUTH_AUDIENCE` (default authenticated) e `LOUNG_ENABLE_WRITES` (false por default). Integrações exigem `GOOGLE_PLACES_API_KEY`, `GROQ_API_KEY`, `GROQ_MODEL`; `GROQ_TIMEOUT` controla prazo. Migração usa `LOUNG_MIGRATION_DSN`, fora do runtime. `LOUNG_DATABASE_PATH` é legado.

Frontend: `NEXT_PUBLIC_SUPABASE_URL` e chave publishable ou anon pública; `LOUNG_API_URL` server-only. `LOUNG_AUTH_MODE=local` ignora proteção Next e não deve ser usado comercialmente. Browser não precisa de DSN, service role, Groq ou Places key. Valores reais não foram lidos. Exemplo de variável não comprova configuração do processo nem funcionamento do provedor.

`backend/scripts/run_api.py` carrega env-file explícito. Providers podem ler .env raiz no primeiro uso (`core/providers/environment.py`) sem sobrescrever o ambiente exportado. Secret manager e precedência precisam de um runbook consistente. DSN deve ter transporte e credencial restritos; TLS efetivo do banco não foi verificado nesta sessão.

## Hospedagem compatível: comparação proposta

| Opção | Benefício | Dependências e limites |
|---|---|---|
| Next Vercel + FastAPI persistente no Render | Serviços gerenciados por componente; worker separado disponível | BFF atual proíbe Host público e URL remota/HTTPS; adaptar rede, autenticação e origem; jobs futuros precisam fila |
| Next e FastAPI no mesmo host/VM com proxy TLS | Loopback interno preserva parte do desenho; processo persistente | Host externo ainda bloqueado pelo BFF; equipe opera SO, patches, supervisão, capacidade e restore |
| Funções efêmeras para ambos | Adequadas a APIs curtas após desacoplar estado | Threads/cache atuais não são execução durável; não migrar diretamente esse worker |

Fontes oficiais consultadas em 23/10/2026: [limites de funções Vercel](https://vercel.com/docs/functions/limitations) e [workers Render](https://render.com/docs/background-workers). Funções têm limites de execução; workers Render são processos contínuos capazes de consumir fila. A recomendação deriva dessas características e do estado observado no código. Não foram cotados planos, preços, SLA ou regiões.

Supabase pode continuar: Auth, schema e RLS já fazem parte da implementação. Condicionar à validação de ACL/roles, região, conexões, capacidade, contratos e recuperação. Trocar banco não resolve as pendências operacionais.

## Custos e margem

Medir por organização: requests Places por SKU/campo, tokens Groq de entrada/saída, export/egress, armazenamento de snapshots/histórico e suporte. A field mask contém telefone, site e avaliações; não presumir tarifa de busca básica. Não há ledger que permita confirmar margem dos planos. Medir distribuição P50/P95 de buscas, gerações e assentos em dados sintéticos e depois no piloto aprovado.

Custo fixo inclui frontend, API, worker/fila quando adotados, Supabase, observabilidade, backup e suporte. Receita de implantação é única; não cobre indefinidamente consumo mensal. Limites locais por chamada não impedem chamadas repetidas e não equivalem a teto financeiro. Usar reserva no backend e alertas/orçamentos nos provedores. Preços comerciais recebidos ainda não foram validados operacionalmente.

## Gates antes de lançar

Build isolado aprovado; domínio HTTPS e sessão inspecionados; startup recusando modos legados/credenciais administrativas; testes A/B; readiness atual; restore em destino descartável com RPO/RTO acordados; limites de consumo; alertas de erro/quota/saturação; runbooks de incidente, suspensão e recuperação. Definir responsáveis, acesso a exportação permitido no encerramento e procedimento para indisponibilidade de Google/Groq/Supabase.

Não há comprovação atual de restore, disponibilidade, carga, segurança de cookies ou prontidão de infraestrutura. Esses itens permanecem explicitamente não verificados.
