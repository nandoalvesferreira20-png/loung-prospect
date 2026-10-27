# Backlog priorizado

Data: 23/10/2026. Nenhum item implementado. P0 bloqueia onboarding comercial; P1 é necessário ao lançamento; P2 é melhoria; P3 é evolução. Severidade inclui operação e lacunas de garantia, não apenas exploits. Complexidade relativa, sem compromisso de prazo.

| ID | Prioridade | Título | Complexidade |
|---|---|---|---|
| SAAS-01 | P0 | Acesso centralizado bloqueado por localhost | Alta |
| SAAS-02 | P0 | Escrita real e autoria pendentes de homologação | Média |
| SAAS-03 | P0 | Isolamento implantado não completamente verificado | Alta |
| SAAS-04 | P0 | Retenção/exportação Places sem adequação demonstrada | Alta |
| SAAS-05 | P0 condicional | Perfil legado sem identidade não pode ser comercial | Média |
| SAAS-06 | P1 | Registry e jobs limitam escala/continuidade | Alta |
| SAAS-07 | P1 | Quotas e custo por organização ausentes | Alta |
| SAAS-08 | P1 | Prompt fixa vendedor/oferta Loung | Média |
| SAAS-09 | P1 | Backup PostgreSQL e restore não demonstrados | Média |
| SAAS-10 | P1 | Contrato, entitlement e suspensão ausentes | Alta |
| SAAS-11 | P1 | Retenção, direitos e portabilidade incompletos | Alta |
| SAAS-12 | P1 | HTTPS, cookies e headers não homologados | Média |
| SAAS-13 | P1 | Readiness, monitoramento e limites SQL incompletos | Média |
| SAAS-14 | P1 | Validação completa e pipeline comercial pendentes | Alta |
| SAAS-15 | P1 | Provisionamento e seleção de organização parciais | Média |
| SAAS-16 | P2 | Auditoria tem payload e policy ampla para membros | Média |
| SAAS-17 | P2 | Datas e constraints preservam limites legados | Média |
| SAAS-18 | P3 | Automação completa de assinatura/gateway | Alta |

## SAAS-01 — Acesso centralizado bloqueado por localhost

- Categoria: operação/arquitetura. Severidade: P0. Complexidade: alta.
- Descrição: Host público é recusado e upstream admite apenas HTTP loopback.
- Evidência/referência: `web/src/lib/api/local-request.ts:isLocalRequest`; `proxy.ts`, `prospecting-proxy.ts`, `sdr-proxy.ts`, `team-proxy.ts`; `backend/persistence/runtime.py:TrustedHostMiddleware`.
- Impacto: cliente externo não opera por domínio comercial; Vercel→backend remoto não funciona com o contrato atual.
- Recomendação: definir topologia, origens explícitas, TLS, upstream autorizado e autenticação mantendo o BFF.
- Dependências: decisão de hospedagem/rede.
- Aceite: login/leads/busca/SDR passam em domínio HTTPS autorizado; origem hostil negada; upstream não é controlado pelo cliente.

## SAAS-02 — Escrita real e autoria pendentes de homologação

- Categoria: banco/operação. Severidade: P0. Complexidade: média.
- Descrição: histórico registra trigger incompatível com ACL e flag de escrita zero; não foi revalidado ao vivo.
- Evidência/referência: `web/docs/phase-3-2-claims-fix.md`; `phase-3-2-homologation.md`; `supabase/migrations/202610220001_stamp_actor_from_verified_claims.sql`.
- Impacto: criação/importação/CRM/SDR podem falhar apesar do login funcionar.
- Recomendação: homologar a correção existente em cópia isolada; planejar futura janela autorizada com rollback. Não aplicar nem habilitar flag nesta auditoria.
- Dependências: SAAS-03 e backup/rollback.
- Aceite: catálogo efetivo reconhecido; mutações sintéticas com ator correto; falha de auditoria reverte tudo; prontidão do ambiente comprovada por procedimento autorizado.

## SAAS-03 — Isolamento implantado não completamente verificado

- Categoria: segurança/garantia. Severidade: P0. Complexidade: alta.
- Descrição: RLS existe no código, mas catálogo atual e suíte negativa completa não foram verificados nesta sessão.
- Evidência/referência: `backend/persistence/postgres.py:Database.open`; `supabase/migrations/202610190001_phase31.sql`; `backend/tests/test_phase31_postgres.py` e `test_phase32_team.py`.
- Impacto: divergência de role/policy pode comprometer dados; não há exploit demonstrado.
- Recomendação: catálogo sanitizado somente leitura de ACL/RLS/owners e testes A/B em PostgreSQL nativo descartável equivalente.
- Dependências: ambiente isolado inequívoco e configuração equivalente.
- Aceite: A não lê/altera/exporta B; jobs/IA não misturam contexto; sem membership negado; member sem admin; header forjado negado; runtime efetivo sem bypass.

## SAAS-04 — Retenção e exportação Places sem adequação demonstrada

- Categoria: dados/contratos. Severidade: P0. Complexidade: alta.
- Descrição: snapshots guardam rows sem TTL persistente; leads/export retêm conteúdo do provedor.
- Evidência/referência: `backend/persistence/searches.py:checkpoint/get`; `backend/prospecting/jobs.py:export/_purge`; `core/providers/google_places.py:FIELD_MASK`; fonte oficial no documento 05.
- Impacto: modelo comercial pode depender de armazenamento/redistribuição não permitido ou retenção excessiva.
- Recomendação: validar contrato/conta, licença por campo, prazos, atribuição e exportação; somente depois propor adequação. Não afirmar infração conclusiva.
- Dependências: responsável jurídico/comercial e documentação contratual aplicável.
- Aceite: decisão documentada para cada uso, prazo e atribuição; requisitos rastreáveis para purge/export; licença não presumida por API paga.

## SAAS-05 — Perfil legado sem identidade não pode ser comercial

- Categoria: segurança/configuração. Severidade: P0 condicional. Complexidade: média.
- Descrição: modo SQLite mantém rotas sem JWT/membership; auth local pula proteção Next. Padrão de ambiente é postgres e não há fallback silencioso.
- Evidência/referência: `backend/main.py:create_app`; `backend/config.py:Settings`; `web/src/lib/auth/server.ts:backendHeaders`; `web/src/proxy.ts`.
- Impacto: implantação indevida/exposição permite acesso HTTP direto a dados locais; Host/Origin não autenticam cliente de API.
- Recomendação: perfil comercial deve recusar modos legados e credenciais administrativas; proteger rede; manter desktop separado.
- Dependências: SAAS-01.
- Aceite: startup comercial falha com sqlite/auth local; sem JWT é negado mesmo sem Origin e com Host aceito; modo legado continua restrito à finalidade autorizada.

## SAAS-06 — Registry e jobs limitam escala e continuidade

- Categoria: disponibilidade. Severidade: P1. Complexidade: alta.
- Descrição: Registry tem 32 organizações sem eviction; worker/cache/cancel por processo; snapshots inicial/final não são fila durável.
- Evidência/referência: `backend/persistence/runtime.py:Registry.get`; `backend/prospecting/jobs.py:JobManager`; `backend/persistence/searches.py:PgJobManager`.
- Impacto: 33ª org recebe 503; restart interrompe execução; múltiplas réplicas duplicam limites e não coordenam cancelamento.
- Recomendação: definir capacidade piloto/lifecycle; fila durável, leases, checkpoints e cancelamento compartilhados antes de escala distribuída.
- Dependências: SAAS-03/07 e topologia.
- Aceite: inatividade não esgota capacidade; job após restart e cancel em outra réplica tem estado coerente; execução/importação não duplica indevidamente.

## SAAS-07 — Quotas e custo por organização ausentes

- Categoria: custos/abuso. Severidade: P1. Complexidade: alta.
- Descrição: locks/TTL e orçamento por pesquisa não medem consumo financeiro mensal ou entre réplicas.
- Evidência/referência: `backend/sdr/service.py:SdrService.generate`; `core/sales/groq_provider.py:generate`; `core/prospecting/limits.py`.
- Impacto: um tenant pode consumir margem e quota global, prejudicando demais clientes.
- Recomendação: ledger, rate limit e reservas atômicas por recurso/competência, teto global e alertas de provedor.
- Dependências: definição de limites comerciais.
- Aceite: chamadas paralelas entre réplicas não excedem teto; custo/usage conciliável; suspensão bloqueia nova chamada cara antes de consumir quota.

## SAAS-08 — Prompt fixa vendedor e oferta Loung

- Categoria: produto/IA. Severidade: P1. Complexidade: média.
- Descrição: identidade Fernando/Loung Tech e oferta global são inadequadas para organizações externas independentes.
- Evidência/referência: `core/sales/prompts.py:SYSTEM_PROMPT`; `backend/sdr/policy.py`; `backend/sdr/service.py:WebAgent`.
- Impacto: abordagem pode representar outra empresa ou oferecer serviço incorreto.
- Recomendação: identidade/oferta aprovada por org e contexto tenant-scoped; manter políticas de segurança e revisão humana.
- Dependências: SAAS-03 e decisão comercial de personalização.
- Aceite: duas orgs geram identidade/oferta próprias sem mistura; ausência de configuração tem comportamento explícito; envio permanece manual.

## SAAS-09 — Backup PostgreSQL e restauração não demonstrados

- Categoria: recuperação. Severidade: P1. Complexidade: média.
- Descrição: PostgreSQL delega backup à operação; backup SQLite da migração não prova restore do serviço.
- Evidência/referência: `backend/persistence/postgres.py:PgStore._backup`; `backend/scripts/migrate_sqlite.py:inspect_source`.
- Impacto: perda de dados ou prazo de recuperação desconhecido.
- Recomendação: definir retenção, RPO/RTO e PITR conforme contrato; ensaiar restore em destino isolado.
- Dependências: responsável/plano de infraestrutura.
- Aceite: restauração isolada com integridade e tempo medido, procedimento e responsáveis; jamais sobrepor produção em teste.

## SAAS-10 — Contrato, entitlement e suspensão por cliente ausentes

- Categoria: comercial. Severidade: P1. Complexidade: alta.
- Descrição: schema/rotas não mostram plano, assinatura/estado de contrato ou suspensão comercial por org.
- Evidência/referência: `supabase/migrations/202610190001_phase31.sql`; `backend/persistence/runtime.py:authorize`; busca de termos financeiros em backend/web/src/core/supabase.
- Impacto: não há aplicação consistente de plano, vencimento e acesso de cliente pagante.
- Recomendação: separar contrato/estado, entitlement, papel e identidade; conciliação manual apenas em piloto aprovado.
- Dependências: SAAS-07 e política comercial.
- Aceite: ativo/carência/suspenso regrados e auditados; implantação separada da recorrência; suspensão não apaga ou revela dados.

## SAAS-11 — Retenção, direitos e portabilidade incompletos

- Categoria: privacidade. Severidade: P1. Complexidade: alta.
- Descrição: dados trafegam a terceiros; ciclo de retenção não identificado; export atual é de busca.
- Evidência/referência: `backend/persistence/searches.py`; `core/sales/prompts.py:FIELDS`; `web/src/lib/sdr-whatsapp.ts`; `supabase/migrations/202610190001_phase31.sql:audit_change`.
- Impacto: encerramento e exercício de direitos sem rastreabilidade suficiente.
- Recomendação: inventário, finalidade/base aplicável, contratos/suboperadores, prazos, opt-out, export permitido completo e exclusão auditada.
- Dependências: SAAS-04 e validação jurídica externa.
- Aceite: política aprovada; simulação isolada de export/exclusão abrange filhos, audit e backups conforme retenção; clientes conhecem terceiros/finalidade.

## SAAS-12 — HTTPS, cookies e headers não homologados

- Categoria: segurança web. Severidade: P1. Complexidade: média.
- Descrição: opções de cookies delegadas ao SDK; sem CSP/HSTS explícitos em next.config; domínio público não exercitado.
- Evidência/referência: `web/src/lib/auth/server.ts`; `web/src/proxy.ts`; `web/next.config.ts`.
- Impacto: configuração inadequada de sessão/origem compromete acesso no ambiente público; não é falha de cookie demonstrada.
- Recomendação: inspecionar atributos reais, refresh/logout/recovery, CSRF/origins e headers na topologia TLS escolhida.
- Dependências: SAAS-01.
- Aceite: sessão/refresh/recovery corretos no domínio; cookies compatíveis com desenho SSR; origens indevidas negadas; CSP/HSTS adequados sem quebrar interface.

## SAAS-13 — Readiness, monitoramento e limites SQL incompletos

- Categoria: operação. Severidade: P1. Complexidade: média.
- Descrição: health não verifica banco; runtime sem timeout SQL/lock ou pool explícito; monitoramento externo não identificado.
- Evidência/referência: `backend/persistence/runtime.py:health/database_failure`; `backend/persistence/postgres.py:Database.open`; `backend/prospecting/jobs.py:search_event`.
- Impacto: falha silenciosa, locks longos e saturação de conexões.
- Recomendação: readiness limitado, métricas/alertas, correlação sanitizada, orçamento de conexões e timeouts transacionais.
- Dependências: SAAS-01/09.
- Aceite: indisponibilidade detectada e alerta acionado; consultas/locks com teto; logs sem dados/segredos; runbook exercitado.

## SAAS-14 — Validação completa e pipeline comercial pendentes

- Categoria: qualidade/release. Severidade: P1. Complexidade: alta.
- Descrição: apenas JWT/tsc executados agora; pytest.ini descobre tests/, não backend/tests; sem CI/CD identificado; Python não tem lock completo revisado.
- Evidência/referência: `web/package.json`; `pytest.ini`; `backend/tests`; `web/scripts`; `requirements.txt`; `backend/requirements.txt`.
- Impacto: regressão de segurança/backend pode escapar ao release ou depender do ambiente.
- Recomendação: pipeline isolado explícito de frontend/backend/desktop, build/lint e segurança com PostgreSQL nativo; reprodução de dependências e análise de vulnerabilidades.
- Dependências: SAAS-03.
- Aceite: gates reprodutíveis bloqueiam falhas, incluem backend/tests e não usam dados reais; artefatos sanitizados; build completo aprovado.

## SAAS-15 — Provisionamento e seleção de organização parciais

- Categoria: onboarding. Severidade: P1. Complexidade: média.
- Descrição: organização/convite manuais; backend escolhe primeira membership; BFF não encaminha organização escolhida.
- Evidência/referência: `supabase/migrations/202610190001_phase31.sql`; `backend/persistence/team.py`; `backend/persistence/runtime.py:authorize`; `web/src/lib/auth/server.ts:backendHeaders`.
- Impacto: onboarding sujeito a erro e contexto inesperado para usuário multi-org.
- Recomendação: runbook idempotente inicial; seleção explícita validada; depois convite auditado e assentos.
- Dependências: SAAS-03/10.
- Aceite: duas empresas provisionadas sem dados cruzados; multi-org escolhe contexto visível/persistente; seleção não concede membership indevida.

## SAAS-16 — Auditoria tem payload e policy ampla para membros

- Categoria: menor privilégio. Severidade: P2. Complexidade: média.
- Descrição: endpoint limita owner/admin, RLS usa membership; eventos de filhos podem conter mensagem/descrição.
- Evidência/referência: `supabase/migrations/202610190001_phase31.sql:audit_change/audit_read`; `backend/persistence/team.py:activities`.
- Impacto: futuros consumidores SQL podem ampliar visibilidade administrativa; conteúdo sensível fica duplicado na auditoria.
- Recomendação: decidir autorização por papel, projeções e retenção; alinhar política do banco ao modelo aprovado.
- Dependências: SAAS-03/11.
- Aceite: matriz SQL/API testada; member não recebe conteúdo administrativo indevido; retenção cobre audit_events.

## SAAS-17 — Datas e constraints preservam limitações legadas

- Categoria: banco/desempenho. Severidade: P2. Complexidade: média.
- Descrição: datas text, empresa sem NOT NULL, CHECK admite NULL e índices não cobrem todos os padrões.
- Evidência/referência: `supabase/migrations/202610190001_phase31.sql:leads/julianday`; `backend/repository.py`; `backend/crm/service.py`.
- Impacto: dados administrativos inválidos e consultas lentas apesar da validação da API.
- Recomendação: perfil e EXPLAIN em cópia; planejar evolução incremental de tipo/constraint e índices justificados.
- Dependências: SAAS-09/14.
- Aceite: sem perda histórica; datas inválidas tratadas; entradas inválidas rejeitadas; plano/carga justificam índices e orçamento P95.

## SAAS-18 — Automação completa de assinatura e gateway

- Categoria: financeiro. Severidade: P3. Complexidade: alta.
- Descrição: integração de gateway, webhook e histórico financeiro não localizada.
- Evidência/referência: busca em backend/web/src/core/supabase por subscription/billing/webhook; schema comercial atual sem essas entidades.
- Impacto: conciliação manual não escala; divergência pode gerar cobrança ou acesso indevido.
- Recomendação: escolher gateway após validação comercial; inbox assinada/idempotente, conciliação, histórico, cancelamento e reativação.
- Dependências: SAAS-07/10/11 e oferta validada.
- Aceite: evento duplicado/fora de ordem/replay não duplica cobrança; frontend não ativa assinatura; implantação e mensalidade conciliadas. P3 refere-se à automação, não dispensa controle manual do contrato num piloto aprovado.
