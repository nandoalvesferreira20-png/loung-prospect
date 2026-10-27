# Tarefas por desenvolvedor

Reorganização: 23/10/2026. Somente planejamento. Todos programam componentes ou automações de teste/infra; correções pertencem ao dono do módulo e a estratégia de QA continua com Miqueias. Critérios integrais dos 15 pais estão no [documento 09](09-BACKLOG-EQUILIBRADO.md); não podem ser substituídos pelos aceites locais abaixo.

Dependências listadas são pré-requisitos para concluir/executar a fatia integrada na agenda. Análise, casos de teste e contratos podem ser preparados cedo. COM-04-B contém uma liberação externa adicional sem prazo conhecido; a agenda assume essa decisão disponível. D0 significa acessos e contexto inicial disponíveis; baseline, topologia e contratos são fechados nas primeiras fatias COM-01-A/02-A/04-A/05-A, dentro de suas horas, sem criar uma fase de trabalho gratuita. Nenhuma branch ou alteração do aplicativo é criada nesta fase documental.

## Fernando — 40–72h; referência 56h; 25%

Começar por COM-01-A. Programa BFF, prompt, operação comercial, verificador de restore, testes de jobs/IA, experiência de prospecção e CI. A integração operacional/release é de Marwin e a consolidação QA é de Miqueias.

### COM-01-A — Topologia e BFF com allowlists explícitas

- **Pai / prioridade / horas:** COM-01 / P0 / 6–10h.
- **Arquivos envolvidos:** web/src/lib/api/local-request.ts, proxy.ts, crm-proxy.ts, prospecting-proxy.ts, sdr-proxy.ts, team-proxy.ts; contratos de upstream.
- **Dependências de execução/integração:** D0; pode iniciar na primeira onda.
- **Critério objetivo de aceite:** BFF admite somente domínio/upstream aprovados, sem URL controlada pelo cliente; contrato TLS/Host entregue a COM-12-B.
- **Testes obrigatórios:** Unitários BFF de Host/Origin/SSRF, redirects e headers; teste de leitura/mutação no domínio final em COM-14-B.
- **Revisor técnico independente:** Miqueias; Miqueias conserva o gate QA global, sem autor aprovar sozinho controle crítico.

### COM-03-C — Programar provas de contexto isolado nos jobs e IA

- **Pai / prioridade / horas:** COM-03 / P0 / 4–6h.
- **Arquivos envolvidos:** backend/tests/test_tenant_jobs_ai.py (proposto); spies dos providers de busca e SDR.
- **Dependências de execução/integração:** COM-03-A, COM-06-B, COM-07-A, COM-07-B.
- **Critério objetivo de aceite:** Jobs simultâneos e prompts/rascunhos não cruzam tenants, mesmo com requestId igual; revogação e restart documentados.
- **Testes obrigatórios:** Dois tenants, provider spy do contexto exato, draftId alheio, revogação durante job, cache e snapshots pós-restart.
- **Revisor técnico independente:** Miqueias; Miqueias conserva o gate QA global, sem autor aprovar sozinho controle crítico.

### COM-04-B — Decisão contratual e especificação técnica rastreável

- **Pai / prioridade / horas:** COM-04 / P0 / 4–8h.
- **Arquivos envolvidos:** Inventário COM-04-A; requisitos/runbooks futuros de dados, Groq, WhatsApp e LGPD.
- **Dependências de execução/integração:** COM-04-A; decisão externa contratual/jurídica é obrigatória e pode bloquear prazo.
- **Critério objetivo de aceite:** Responsável externo aprova/veta por escrito uso/campos/retenção/export/atribuição; matriz alimenta COM-09 e COM-11; veto mantém NO-GO.
- **Testes obrigatórios:** Revisão dos requisitos com inventário, casos de licença/retention/export e checklist QA; não é parecer jurídico emitido pelo dev.
- **Revisor técnico independente:** Miqueias; Miqueias conserva o gate QA global, sem autor aprovar sozinho controle crítico.

### COM-07-B — Aplicar identidade e oferta ao prompt seguro

- **Pai / prioridade / horas:** COM-07 / P1 / 4–8h.
- **Arquivos envolvidos:** core/sales/prompts.py; backend/sdr/policy.py; adaptador puro de prompt proposto.
- **Dependências de execução/integração:** COM-07-A.
- **Critério objetivo de aceite:** Nenhum Fernando/Loung global indevido para o cliente; identidade/oferta vêm da org autorizada; políticas globais e revisão humana permanecem.
- **Testes obrigatórios:** Prompts A/B, campos hostis, dados ausentes, oferta aprovada; spy garante minimização; COM-03-C valida integração.
- **Revisor técnico independente:** Laís; Miqueias conserva o gate QA global, sem autor aprovar sozinho controle crítico.

### COM-08-B — Programar verificador independente de restore

- **Pai / prioridade / horas:** COM-08 / P1 / 4–8h.
- **Arquivos envolvidos:** backend/scripts/verify_restore.py e testes (propostos); tabelas/relacionamentos/RLS.
- **Dependências de execução/integração:** COM-08-A.
- **Critério objetivo de aceite:** Relatório independente de contagens/checksums/FKs/RLS após restore; confirma tempo e RPO<=24h/RTO<=4h ou meta formalmente renegociada.
- **Testes obrigatórios:** Backup adulterado/incompleto, filho órfão, policy divergente, diferença de contagens e retorno operacional sem tocar produção.
- **Revisor técnico independente:** Marwin; Miqueias conserva o gate QA global, sem autor aprovar sozinho controle crítico.

### COM-10-B — Programar operação restrita de contrato e conciliação

- **Pai / prioridade / horas:** COM-10 / P1 / 4–8h.
- **Arquivos envolvidos:** backend/scripts/manage_contract.py e testes (propostos); contrato COM-10-A; runbook comercial.
- **Dependências de execução/integração:** COM-10-A.
- **Critério objetivo de aceite:** Comando/fluxo operacional mínimo seguro, sem portal billing; não expõe service role; implantação/mensalidade e razão de suspensão conciliáveis.
- **Testes obrigatórios:** Operador indevido negado, idempotência da ação, trilha de auditoria, reativação e preservação dos dados/export conforme política.
- **Revisor técnico independente:** Miqueias; Miqueias conserva o gate QA global, sem autor aprovar sozinho controle crítico.

### COM-11-B — Programar UX de prospecção, sessão e contexto

- **Pai / prioridade / horas:** COM-11 / P1 / 8–14h.
- **Arquivos envolvidos:** web/src/components/prospecting-workspace.tsx; session-provider.tsx; app-shell.tsx; contratos de erro.
- **Dependências de execução/integração:** COM-01-A, COM-01-B, COM-06-B, COM-10-A.
- **Critério objetivo de aceite:** Limite compartilhado visível, sem retry agressivo; org/papel certos e feedback honesto; encerramento/erro de sessão sem perda silenciosa.
- **Testes obrigatórios:** Burst/429, cancel, 409 e falha de persistência, abort/resposta tardia, status/resultados e navegação; acessibilidade e mobile.
- **Revisor técnico independente:** Laís; Miqueias conserva o gate QA global, sem autor aprovar sozinho controle crítico.

### COM-14-A — Programar gates CI e regressão integrada

- **Pai / prioridade / horas:** COM-14 / P1 / 6–10h.
- **Arquivos envolvidos:** Workflow futuro; pytest.ini; web/package.json/scripts; suites selecionadas explícitas.
- **Dependências de execução/integração:** COM-03-A, COM-03-B, COM-03-C, COM-11-A, COM-11-B, COM-13-B, COM-08-B, COM-09-B, COM-12-B.
- **Critério objetivo de aceite:** CI inclui backend/tests, web e desktop pertinentes; build/lint/typecheck e segurança ligados ao candidato; erro/setup bloqueado não fica verde.
- **Testes obrigatórios:** Pipeline falha de propósito, build isolado, regressão completa, A/B SQL/API/jobs/IA e verificação de artefatos sem segredos.
- **Revisor técnico independente:** Miqueias; Miqueias conserva o gate QA global, sem autor aprovar sozinho controle crítico.

**Correções:** implementar/revisar as correções dos componentes sob sua autoria, atualizar seus testes e participar da regressão final. Alteração em arquivo de outro dono passa por handoff explícito; não abrir edição concorrente para apenas redistribuir horas.

## Laís — 40–72h; referência 56h; 25%

Começar por COM-04-A e COM-05-B, depois sessão COM-01-B. Atua Full Stack em configuração SDR e retenção PostgreSQL, além de UI e testes HTTP/E2E. Marwin revisa seu adaptador de banco e Miqueias revisa retenção/isolamento.

### COM-01-B — Sessão SSR, cookies e fluxos Auth no domínio

- **Pai / prioridade / horas:** COM-01 / P0 / 6–10h.
- **Arquivos envolvidos:** web/src/proxy.ts; web/src/lib/auth/{server,browser,config}.ts; web/scripts/auth.test.mjs.
- **Dependências de execução/integração:** D0; pode iniciar na primeira onda.
- **Critério objetivo de aceite:** Login/refresh/logout/recovery compatíveis com HTTPS, cookies e erros seguros; não encaminha credenciais arbitrárias.
- **Testes obrigatórios:** SDK fake, cookies nas duas fronteiras SSR, expiração e 401/503; E2E real de homologação em COM-14-B.
- **Revisor técnico independente:** Fernando; Miqueias conserva o gate QA global, sem autor aprovar sozinho controle crítico.

### COM-03-B — Testes HTTP de IDOR e exportação por tenant

- **Pai / prioridade / horas:** COM-03 / P0 / 4–6h.
- **Arquivos envolvidos:** web/scripts/tenant-http.test.mjs (proposto); backend/tests/test_tenant_http.py (proposto).
- **Dependências de execução/integração:** COM-01-A, COM-01-B, COM-02-B, COM-05-A, COM-05-B.
- **Critério objetivo de aceite:** A não lê/altera/importa/exporta/cancela/consulta resultado/status de B; corpo/header não concede organização ou papel.
- **Testes obrigatórios:** API/BFF com IDs trocados, sem sessão/membership, x-organization-id indevido e export CSV/XLSX; domínio final rechecado em COM-14-B.
- **Revisor técnico independente:** Miqueias; Miqueias conserva o gate QA global, sem autor aprovar sozinho controle crítico.

### COM-04-A — Inventário técnico de dados e rastreamento por campo

- **Pai / prioridade / horas:** COM-04 / P0 / 4–8h.
- **Arquivos envolvidos:** core/providers/google_places.py:FIELD_MASK; backend/persistence/searches.py; core/sales/prompts.py; script de inventário sintético proposto.
- **Dependências de execução/integração:** D0; pode iniciar na primeira onda.
- **Critério objetivo de aceite:** Mapa verificável de origem→payload→lead→export/audit/terceiro; identifica campos, finalidade e retenção, sem dados reais.
- **Testes obrigatórios:** Fixtures que detectam inclusão de campo novo, captura sintética de export e allowlist de prompt; dados de contato não entram por engano.
- **Revisor técnico independente:** Fernando; Miqueias conserva o gate QA global, sem autor aprovar sozinho controle crítico.

### COM-05-B — Implementar guarda de modo local no Next

- **Pai / prioridade / horas:** COM-05 / P0 / 2–4h.
- **Arquivos envolvidos:** web/src/lib/auth/config.ts; web/src/proxy.ts; web/src/lib/auth/server.ts; web/scripts/auth.test.mjs.
- **Dependências de execução/integração:** D0; pode iniciar na primeira onda.
- **Critério objetivo de aceite:** Configuração comercial recusa auth local; não há bypass silencioso no proxy ou backendHeaders.
- **Testes obrigatórios:** Combinações inválidas antes de criar SDK, chaves públicas/secretas, auth local e falhas de configuração; sem expor valores.
- **Revisor técnico independente:** Fernando; Miqueias conserva o gate QA global, sem autor aprovar sozinho controle crítico.

### COM-07-A — Programar configuração SDR por organização

- **Pai / prioridade / horas:** COM-07 / P1 / 4–8h.
- **Arquivos envolvidos:** backend/persistence/sdr.py ou módulo settings dedicado proposto; rota/contrato específico futuro; web/src/lib/api/sdr-contracts.ts.
- **Dependências de execução/integração:** COM-02-A.
- **Critério objetivo de aceite:** Configuração persistente autorizada por tenant, campos aprovados e comportamento explícito se ausente; preferências locais não se tornam configuração global.
- **Testes obrigatórios:** API/settings A/B, campos e papéis permitidos, falta de configuração, escape de instruções e contrato TypeScript.
- **Revisor técnico independente:** Marwin; Miqueias conserva o gate QA global, sem autor aprovar sozinho controle crítico.

### COM-09-A — Programar retenção e impedir reidratação expirada

- **Pai / prioridade / horas:** COM-09 / P1 / 6–12h.
- **Arquivos envolvidos:** backend/persistence/searches.py: checkpoint/get; rotina de purge proposta e testes próprios.
- **Dependências de execução/integração:** COM-04-B, COM-02-A, COM-06-B.
- **Critério objetivo de aceite:** TTL persistente conforme decisão COM-04-B; limpar cache não é suficiente; resultado expirado não reaparece via fallback SQL.
- **Testes obrigatórios:** Relógio controlado, cache limpo/restart, snapshot expirado e não expirado, tenant A/B; compatibilidade com quota já integrada.
- **Revisor técnico independente:** Miqueias; Miqueias conserva o gate QA global, sem autor aprovar sozinho controle crítico.

### COM-11-A — Programar UI de configuração, SDR e atribuição

- **Pai / prioridade / horas:** COM-11 / P1 / 8–14h.
- **Arquivos envolvidos:** web/src/app/configuracoes; app/sdr/page.tsx; componentes SDR e avisos/atribuição.
- **Dependências de execução/integração:** COM-07-A, COM-07-B, COM-10-A, COM-06-B, COM-04-B.
- **Critério objetivo de aceite:** Org/papel e identidade SDR claros; configuração validada ou erro; revisão/aprovação humana e aviso/atribuição conforme decisão; drafts preservados.
- **Testes obrigatórios:** 401/403/409/429/503, teclado/mobile, payload permitido, aprovação e link manual correto; sem dados falsos de integração.
- **Revisor técnico independente:** Fernando; Miqueias conserva o gate QA global, sem autor aprovar sozinho controle crítico.

### COM-14-B — Programar E2E de jornadas e revisão humana

- **Pai / prioridade / horas:** COM-14 / P1 / 6–10h.
- **Arquivos envolvidos:** web/scripts/e2e/ ou harness UI existente (adaptação futura); cenários owner/admin/member.
- **Dependências de execução/integração:** COM-03-A, COM-03-B, COM-03-C, COM-11-A, COM-11-B, COM-09-B, COM-12-B.
- **Critério objetivo de aceite:** Jornada real de homologação login→busca→import→CRM→SDR→aprovação→WhatsApp manual/export funciona; sem envio de mensagem.
- **Testes obrigatórios:** Cookies/HTTPS/recovery/logout, org/role, erros/limites, drafts, keyboard/mobile e links; teardown só no ambiente sintético.
- **Revisor técnico independente:** Miqueias; Miqueias conserva o gate QA global, sem autor aprovar sozinho controle crítico.

**Correções:** implementar/revisar as correções dos componentes sob sua autoria, atualizar seus testes e participar da regressão final. Alteração em arquivo de outro dono passa por handoff explícito; não abrir edição concorrente para apenas redistribuir horas.

## Miqueias — 40–72h; referência 56h; 25%

Começar por COM-05-A e preparação de COM-13-A. Além de estratégia QA, programa entitlement, hooks de quota e readiness/alertas. Fernando/Marwin revisam independentemente esses controles; Laís implementa parte dos testes HTTP/E2E e Fernando os de jobs/IA.

### COM-02-B — Automatizar homologação de autoria e rollback

- **Pai / prioridade / horas:** COM-02 / P0 / 4–8h.
- **Arquivos envolvidos:** backend/tests/test_stamp_claims_migration.py; test_phase32_writes.py; fixture nativa descartável.
- **Dependências de execução/integração:** COM-02-A.
- **Critério objetivo de aceite:** Testes executáveis demonstram autoria inforjável e transação integral; não aprovam schema divergente.
- **Testes obrigatórios:** Falha de audit, claims ausentes/malformadas, ator falso, 409 e zero linhas parciais; SQL nativo isolado.
- **Revisor técnico independente:** Marwin; Miqueias conserva o gate QA global, sem autor aprovar sozinho controle crítico.

### COM-03-A — Estratégia QA e testes SQL/RBAC multiempresa

- **Pai / prioridade / horas:** COM-03 / P0 / 8–12h.
- **Arquivos envolvidos:** backend/tests/test_tenant_sql_isolation.py (proposto); test_phase32_team.py; catálogo/ACL/RLS.
- **Dependências de execução/integração:** COM-02-B, COM-05-A.
- **Critério objetivo de aceite:** Matriz cobre A/B, membership, revogação, member/admin/owner, grants herdados e último owner; Miqueias define gates e reporta evidências.
- **Testes obrigatórios:** Leitura/mutação SQL negativa, membership revogada, owner concorrente com snapshots, funções/grants efetivos e sem bypass.
- **Revisor técnico independente:** Marwin; Miqueias conserva o gate QA global, sem autor aprovar sozinho controle crítico.

### COM-05-A — Implementar guarda de perfil comercial no backend

- **Pai / prioridade / horas:** COM-05 / P0 / 2–4h.
- **Arquivos envolvidos:** backend/config.py; backend/main.py; backend/tests/test_commercial_profile.py (proposto).
- **Dependências de execução/integração:** D0; pode iniciar na primeira onda.
- **Critério objetivo de aceite:** Perfil comercial recusa SQLite/login administrativo e exige JWT/membership; origem/Host não substituem identidade.
- **Testes obrigatórios:** Matriz de config, tentativa sem JWT com Host permitido/sem Origin e falha antes de conectar com credencial proibida.
- **Revisor técnico independente:** Marwin; Miqueias conserva o gate QA global, sem autor aprovar sozinho controle crítico.

### COM-06-B — Integrar quota e estado antes de chamar providers

- **Pai / prioridade / horas:** COM-06 / P1 / 6–12h.
- **Arquivos envolvidos:** backend/prospecting/jobs.py; backend/persistence/searches.py: start; backend/sdr/service.py; testes fake separados.
- **Dependências de execução/integração:** COM-06-A, COM-10-A, COM-05-A, COM-07-A.
- **Critério objetivo de aceite:** Busca/IA só executam com orçamento e org ativa; falha/retry/cancel seguem política sem cobrar/consumir em duplicidade; sem 429 oculto.
- **Testes obrigatórios:** Spies verificam zero chamada acima do teto/suspensa, 429/5xx, retries, concorrência e contador; mantém contexto e revisão humana.
- **Revisor técnico independente:** Fernando; Miqueias conserva o gate QA global, sem autor aprovar sozinho controle crítico.

### COM-10-A — Programar entitlement e suspensão por organização

- **Pai / prioridade / horas:** COM-10 / P1 / 4–8h.
- **Arquivos envolvidos:** backend/persistence/entitlements.py (proposto); organization_settings; contrato para hooks runtime.
- **Dependências de execução/integração:** COM-02-A, COM-05-A.
- **Critério objetivo de aceite:** Estado ativo/suspenso e limite por org auditáveis; chamada cara suspensa não alcança provider; política de leitura/export definida.
- **Testes obrigatórios:** A/B ativo/suspenso, mudança sem autorização, reativação/invalidação e auditoria; integração efetiva em COM-06-B/12-B.
- **Revisor técnico independente:** Marwin; Miqueias conserva o gate QA global, sem autor aprovar sozinho controle crítico.

### COM-12-B — Programar readiness, Host e alertas sanitizados

- **Pai / prioridade / horas:** COM-12 / P1 / 4–8h.
- **Arquivos envolvidos:** backend/persistence/runtime.py; módulo readiness proposto; backend/scripts/run_api.py; testes de alerta.
- **Dependências de execução/integração:** COM-12-A, COM-01-A, COM-10-A, COM-06-B.
- **Critério objetivo de aceite:** Readiness distingue falhas de banco/Auth; Host/TLS/topologia COM-01 integrados; hooks de entitlement preservam auth; alerta<=5min sem PII.
- **Testes obrigatórios:** Origin/Host indevidos, credenciais e sessão, falha SQL/Auth/provider, endpoint de health seguro e entrega do alerta ao responsável.
- **Revisor técnico independente:** Fernando; Miqueias conserva o gate QA global, sem autor aprovar sozinho controle crítico.

### COM-13-A — Programar harness e estratégia mensurável de carga

- **Pai / prioridade / horas:** COM-13 / P1 / 8–14h.
- **Arquivos envolvidos:** backend/tests/load/ e gerador de cenário (propostos); fixtures fake de provider e identidades sintéticas.
- **Dependências de execução/integração:** D0; pode iniciar na primeira onda.
- **Critério objetivo de aceite:** Harness reproduzível com 100 contas, 5/20/50/100 VUs, volume/think time/seed, duas orgs e falhas; Miqueias define métricas/gates.
- **Testes obrigatórios:** Autoteste do harness conta 409/429 separadamente, proíbe DSN real/chamada paga, mede RPS/P95/erros/custo e valida integridade.
- **Revisor técnico independente:** Marwin; Miqueias conserva o gate QA global, sem autor aprovar sozinho controle crítico.

### COM-15-B — Programar agregação de evidências e coordenar aceite QA

- **Pai / prioridade / horas:** COM-15 / P1 / 4–6h.
- **Arquivos envolvidos:** Validador de manifesto QA proposto; checklist/go-live; artefatos de candidato.
- **Dependências de execução/integração:** COM-14-A, COM-14-B, COM-15-A, COM-08-B, COM-13-B, COM-09-A.
- **Critério objetivo de aceite:** Manifesto rejeita testes faltantes/versão divergente; todos os 15 pais aceitos, revisão independente e decisão técnica/comercial registradas.
- **Testes obrigatórios:** Evidência ausente/antiga falha gate; smoke candidato e restauração anexados; dois responsáveis aprovam; sem autor aprovar sozinho controle crítico.
- **Revisor técnico independente:** Laís; Miqueias conserva o gate QA global, sem autor aprovar sozinho controle crítico.

**Correções:** implementar/revisar as correções dos componentes sob sua autoria, atualizar seus testes e participar da regressão final. Alteração em arquivo de outro dono passa por handoff explícito; não abrir edição concorrente para apenas redistribuir horas.

## Marwin — 40–72h; referência 56h; 25%

Começar por COM-02-A, depois preparar backup COM-08-A. Programa núcleo de reserva SQL, limites/conexões, export/exclusão e ferramentas de coleta/release. Não é o único dono de backend: Laís e Miqueias assumem módulos delimitados com revisão.

### COM-02-A — Catálogo, correção existente e transações de autoria

- **Pai / prioridade / horas:** COM-02 / P0 / 4–8h.
- **Arquivos envolvidos:** backend/persistence/postgres.py; persistence/leads.py; supabase/migrations/202610220001_stamp_actor_from_verified_claims.sql (existente); scripts de diagnóstico.
- **Dependências de execução/integração:** D0; pode iniciar na primeira onda.
- **Critério objetivo de aceite:** Catálogo equivalente documentado, correção homologada em cópia, mutações carimbam ator; plano de aplicação/retorno separado de liberação.
- **Testes obrigatórios:** Preflight sanitizado, criação/edição/import/SDR sintéticos, rollback e revisão 409; sem aplicar em banco real nesta etapa.
- **Revisor técnico independente:** Miqueias; Miqueias conserva o gate QA global, sem autor aprovar sozinho controle crítico.

### COM-06-A — Programar quota/reserva persistente e atômica

- **Pai / prioridade / horas:** COM-06 / P1 / 6–12h.
- **Arquivos envolvidos:** backend/persistence/usage.py (proposto); schema incremental futuro de consumo; testes SQL próprios.
- **Dependências de execução/integração:** COM-02-A.
- **Critério objetivo de aceite:** Contador por org/competência sobrevive a restart; reserva/expiração/liquidação concorrentes respeitam teto.
- **Testes obrigatórios:** Dois clientes SQL, disputa do último crédito, idempotência, falha/cancel/reserva expirada e reconciliação de usage/custo.
- **Revisor técnico independente:** Miqueias; Miqueias conserva o gate QA global, sem autor aprovar sozinho controle crítico.

### COM-08-A — Programar/definir backup e restauração isolada

- **Pai / prioridade / horas:** COM-08 / P1 / 4–8h.
- **Arquivos envolvidos:** Scripts operacionais de backup/restore propostos; infraestrutura de homologação; documentação de recuperação.
- **Dependências de execução/integração:** COM-02-A.
- **Critério objetivo de aceite:** Backup restaurável em destino descartável, origem e destino validados; responsáveis e RPO/RTO acordados.
- **Testes obrigatórios:** Captura e restauração ensaiadas, origem intocada, identificação de destino descartável, falha de backup e tempo medido.
- **Revisor técnico independente:** Fernando; Miqueias conserva o gate QA global, sem autor aprovar sozinho controle crítico.

### COM-09-B — Programar portabilidade e exclusão operacional auditada

- **Pai / prioridade / horas:** COM-09 / P1 / 6–12h.
- **Arquivos envolvidos:** Scripts operacionais propostos; backend/prospecting/jobs.py: export (trecho após COM-06-B); audit_events e filhos.
- **Dependências de execução/integração:** COM-04-B, COM-02-A, COM-06-B; COM-06-B entrega a edição de jobs.py antes desta fatia.
- **Critério objetivo de aceite:** Export permitido completo por org e exclusão sob procedimento restrito; filhos/audit/backups seguem política sem apagar outra org.
- **Testes obrigatórios:** Export A/B, CSV injection, FKs, execução repetida, auditoria, prazos e exclusão conforme retenção; restore COM-08-B antes do aceite final.
- **Revisor técnico independente:** Laís; Miqueias conserva o gate QA global, sem autor aprovar sozinho controle crítico.

### COM-12-A — Programar limites SQL e orçamento de conexões

- **Pai / prioridade / horas:** COM-12 / P1 / 8–12h.
- **Arquivos envolvidos:** backend/persistence/postgres.py; timing.py; diagnóstico de conexões proposto; supervisão/hospedagem futuras.
- **Dependências de execução/integração:** COM-02-A, COM-05-A.
- **Critério objetivo de aceite:** Timeout query/lock e orçamento documentados; sem leak; uma instância persistente supervisionada; pool só se medição justificar.
- **Testes obrigatórios:** Falha/timeout/lock, rollback/close, pico/cooldown de conexões, orçamento<=80% e compatibilidade SET LOCAL/RLS.
- **Revisor técnico independente:** Miqueias; Miqueias conserva o gate QA global, sem autor aprovar sozinho controle crítico.

### COM-13-B — Executar carga e programar coleta/análise operacional

- **Pai / prioridade / horas:** COM-13 / P1 / 8–14h.
- **Arquivos envolvidos:** Scripts coletores/relatório propostos; banco nativo descartável; métricas das camadas BFF/API/SQL.
- **Dependências de execução/integração:** COM-13-A, COM-12-A, COM-12-B, COM-06-B, COM-10-B, COM-09-A, COM-09-B, COM-07-B.
- **Critério objetivo de aceite:** Relatório ligado ao candidato e envelope; zero mistura/corrupção; metas do documento 06 cumpridas ou bloqueio explícito, sem declarar 100 simultâneos por haver 100 contas.
- **Testes obrigatórios:** Degraus, soak 2h, burst, refresh, falhas/restart, lock/conexões e contagens antes/depois; correção material exige reteste.
- **Revisor técnico independente:** Miqueias; Miqueias conserva o gate QA global, sem autor aprovar sozinho controle crítico.

### COM-15-A — Programar atualização segura e pacote operacional

- **Pai / prioridade / horas:** COM-15 / P1 / 4–6h.
- **Arquivos envolvidos:** Scripts propostos de preflight/drain/retorno; runbooks, candidato e onboarding.
- **Dependências de execução/integração:** COM-13-B, COM-08-B, COM-09-B.
- **Critério objetivo de aceite:** Pacote rastreável com drain/manutenção para jobs/drafts locais, suporte e retorno; onboarding controlado até 100 contas; nenhum deploy implícito.
- **Testes obrigatórios:** Smoke/drain/restart/retorno em cópia, configuração/env validados sem valores, provisionamento idempotente e suporte ensaiado.
- **Revisor técnico independente:** Fernando; Miqueias conserva o gate QA global, sem autor aprovar sozinho controle crítico.

**Correções:** implementar/revisar as correções dos componentes sob sua autoria, atualizar seus testes e participar da regressão final. Alteração em arquivo de outro dono passa por handoff explícito; não abrir edição concorrente para apenas redistribuir horas.

## Horas, percentuais e prazo

| Pessoa | Base mínima | Referência | Base máxima | Parcela da referência | Com 20% de reserva |
|---|---:|---:|---:|---:|---:|
| Fernando | 40h | 56h | 72h | 25% | 48–86,4h |
| Laís | 40h | 56h | 72h | 25% | 48–86,4h |
| Miqueias | 40h | 56h | 72h | 25% | 48–86,4h |
| Marwin | 40h | 56h | 72h | 25% | 48–86,4h |
| **Total** | **160h** | **224h** | **288h** | **100%** | **192–345,6h** |

Agenda com 6h produtivas por pessoa/dia e dependências/arquivos respeitados: **9–15 dias úteis de base**, referência **12 dias**; **10–18 dias úteis com reserva de 20%**, referência **14 dias**. É uma simulação de planejamento, não medição de produtividade nem ótimo matemático provado. Espera jurídica, acesso/provisionamento e defeito importante somam tempo adicional; dez dias só no cenário inferior. Cinco dias não comportam o mínimo. Detalhes e agenda auditável no documento 10.

Os 25% são atingíveis no orçamento sem reduzir aceites porque há backend modular e automação técnica transferíveis. Confirmar competência e registrar horas reais; se a redistribuição aumentar risco, manter revisão e reestimar, mesmo que a proporção realizada deixe de ser exata. Não cortar testes ou conformidade para forçar uma planilha.

