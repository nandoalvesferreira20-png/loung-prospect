# Backlog técnico pronto para GitHub Projects

Revisão: 23/10/2026. Planejamento, sem criação de issues, branches, commits ou alterações no GitHub.

## Escopo, estimativas e contagem

**5 P0 + 10 P1 = 15 tarefas de piloto; 3 P2 posteriores.** IDs COM substituem a decomposição de execução, sem apagar os IDs SAAS da auditoria anterior. P1 aqui significa necessário para o piloto, conforme este pedido. P2 é pós-piloto, salvo promoção explícita por falha de carga/requisito contratual.

Horas são intervalos de esforço da pessoa responsável, incluindo implementação, seus testes locais e documentação. QA integrado está separado em COM-03/13/14; integração/revisão transversal está em COM-15. Não duplicar essas horas ao somar. P/M/G indicam escopo relativo, não duração: P é alteração pequena; M integra alguns módulos; G muda subsistema. O mesmo tamanho admite intervalos diferentes conforme evidência.

Base: **160–288 horas-pessoa**, sendo **116–216 de desenvolvimento/infra/UX/integração e 44–72 de QA**. Reserva de 20%: **192–346 horas-pessoa**. P2 soma **64–144h**, excluídas. Espera jurídica, provisionamento externo e correção de defeitos graves descobertos não têm duração conhecida e não estão embutidos como prazo garantido. Premissas: reutilizar correção de autoria, schema e regras; uma instância persistente; carteira compartilhada aceita; cobrança manual aprovada; sem substituir fonte Places nem reconstruir fila.

## Campos para importar manualmente

Criar no Projects, futuramente: ID; Title; Status (Backlog/Ready/In progress/In review/QA/Blocked/Done); Assignee; Priority; Size; Estimate min/max; Dependencies; Labels; Milestone (Pilot/Post-pilot). Mapear nomes aos usernames reais quando conhecidos; não inventar handles. Cada seção abaixo é o corpo completo de um cartão. Campos e critérios podem ser copiados diretamente; nenhuma API GitHub foi usada.

| ID | Responsável | Prioridade | P/M/G | Horas | Título |
|---|---|---|---|---:|---|
| COM-01 | Fernando | P0 | M | 12–20 | Habilitar topologia comercial e sessão segura |
| COM-02 | Marwin | P0 | M | 8–16 | Homologar escrita e autoria com correção existente |
| COM-03 | Miqueias | P0 | M | 16–24 | Provar isolamento multiempresa e papéis ponta a ponta |
| COM-04 | Fernando | P0 | M | 8–16 | Fechar decisão de uso comercial dos dados e APIs |
| COM-05 | Marwin | P0 | P | 4–8 | Impedir modos legados e privilégios administrativos em perfil comercial |
| COM-06 | Marwin | P1 | M | 12–24 | Aplicar quota, reserva e limite de chamadas caras por organização |
| COM-07 | Fernando | P1 | M | 8–16 | Configurar identidade e oferta SDR por organização |
| COM-08 | Marwin | P1 | M | 8–16 | Demonstrar backup e restauração com RPO/RTO |
| COM-09 | Marwin | P1 | M | 12–24 | Aplicar ciclo mínimo de retenção e portabilidade aprovado |
| COM-10 | Fernando | P1 | M | 8–16 | Controlar contrato e suspensão mínima sem billing completo |
| COM-11 | Laís | P1 | M | 16–28 | Concluir experiência mínima de cliente e limites compartilhados |
| COM-12 | Marwin | P1 | M | 12–20 | Preparar operação limitada, conexões e alertas |
| COM-13 | Miqueias | P1 | M | 16–28 | Medir capacidade de 100 contas e concorrência acordada |
| COM-14 | Miqueias | P1 | M | 12–20 | Fechar regressão, gates de CI e aceite do piloto |
| COM-15 | Fernando | P1 | M | 8–12 | Integrar release e handover com atualização segura |
| COM-16 | Fernando | P2 | G | 24–48 | Automatizar assinaturas e gateway após validar piloto |
| COM-17 | Marwin | P2 | G | 24–56 | Distribuir jobs somente se o envelope exigir |
| COM-18 | Marwin | P2 | G | 16–40 | Otimizar SQL/índices e constraints após medição |

## COM-01 — Habilitar topologia comercial e sessão segura

- **Responsável sugerido:** Fernando.
- **Prioridade / complexidade / esforço:** P0 / M / 12–20 horas-pessoa.
- **Descrição técnica:** BFF e API recusam domínio público/upstream remoto. Definir topologia e adaptar allowlists/TLS/encaminhamento seguro preservando autenticação.
- **Evidência e arquivos/módulos:** web/src/lib/api/local-request.ts; proxies; auth/server.ts; web/src/proxy.ts; backend/persistence/runtime.py:TrustedHost.
- **Impacto:** Sem alteração, clientes externos não acessam a plataforma.
- **Labels:** area:bff, area:auth, security, pilot.
- **Dependências:** Decisão de domínio/rede no D1; COM-05 para aceite comercial.
- **Critério objetivo de aceite:** Domínio HTTPS autorizado opera login/leitura/mutação; origem/Host/upstream hostis negados; refresh/logout/recovery homologados.
- **Testes obrigatórios:** BFF local e remoto permitido; cross-origin e SSRF negativos; cookies e expiração no staging.

## COM-02 — Homologar escrita e autoria com correção existente

- **Responsável sugerido:** Marwin.
- **Prioridade / complexidade / esforço:** P0 / M / 8–16 horas-pessoa.
- **Descrição técnica:** Histórico registra correção não aplicada; ler catálogo e validar migration já existente em banco descartável. Preparar aplicação futura e retorno autorizados.
- **Evidência e arquivos/módulos:** backend/persistence/leads.py; postgres.py; supabase/migrations/202610220001_stamp_actor_from_verified_claims.sql; web/docs/phase-3-2-claims-fix.md.
- **Impacto:** CRM pode falhar ao salvar mesmo com sessão válida.
- **Labels:** area:database, security, pilot.
- **Dependências:** Ambiente descartável; definição atual/backup antes de eventual implantação.
- **Critério objetivo de aceite:** Criação/edição/import/SDR sintéticos persistem ator correto; erro em trigger não deixa linhas parciais; catálogo compatível documentado.
- **Testes obrigatórios:** test_phase32_writes; test_stamp_claims_migration; falha de auditoria e revisão 409.

## COM-03 — Provar isolamento multiempresa e papéis ponta a ponta

- **Responsável sugerido:** Miqueias.
- **Prioridade / complexidade / esforço:** P0 / M / 16–24 horas-pessoa.
- **Descrição técnica:** Controles existem, mas falta evidência atual integrada; ampliar negativos de export/jobs/IA e registrar catálogo sanitizado.
- **Evidência e arquivos/módulos:** backend/tests/test_phase31_postgres.py; test_phase32_team.py; persistence/postgres.py; migrations/policies.
- **Impacto:** Gap de garantia impede receber dados comerciais reais.
- **Labels:** area:qa, security, multi-tenant, pilot.
- **Dependências:** Pode preparar D1; aceite após COM-02/05 e integração COM-01.
- **Critério objetivo de aceite:** Zero leitura/escrita/exportação/contexto entre A/B; sem membership negado; member sem admin; revogação e header forjado negados.
- **Testes obrigatórios:** A/B HTTP e SQL; provider spy; jobs simultâneos; ACL/owners; concorrência nativa do último owner.

## COM-04 — Fechar decisão de uso comercial dos dados e APIs

- **Responsável sugerido:** Fernando.
- **Prioridade / complexidade / esforço:** P0 / M / 8–16 horas-pessoa.
- **Descrição técnica:** Snapshots/export retêm dados Places; mapear por campo e obter decisão contratual. Confirmar enquadramento Groq/WhatsApp/LGPD com responsável externo.
- **Evidência e arquivos/módulos:** core/providers/google_places.py:FIELD_MASK; persistence/searches.py; jobs.py:export; sdr/service.py; fontes oficiais do documento 02.
- **Impacto:** Licença e tratamento não demonstrados; pode inviabilizar o modelo atual.
- **Labels:** compliance, product, external-dependency, pilot.
- **Dependências:** Acesso aos contratos e responsável jurídico/comercial; tempo externo não estimado.
- **Critério objetivo de aceite:** Decisão escrita aprova ou veta campos, retenção, export e atribuição; COM-09/11 recebem requisitos; veto mantém NO-GO.
- **Testes obrigatórios:** Rastrear campos reais em captura sintética; revisão do inventário e dos requisitos com QA; sem chamada real nesta auditoria.

## COM-05 — Impedir modos legados e privilégios administrativos em perfil comercial

- **Responsável sugerido:** Marwin.
- **Prioridade / complexidade / esforço:** P0 / P / 4–8 horas-pessoa.
- **Descrição técnica:** SQLite não aplica JWT e auth local desvia Next; criar validação de perfil comercial e segregação de credenciais/rede.
- **Evidência e arquivos/módulos:** backend/main.py:create_app; config.py; web/src/lib/auth/server.ts; web/src/proxy.ts.
- **Impacto:** Configuração equivocada pode expor base sem identidade multiempresa.
- **Labels:** area:config, security, pilot.
- **Dependências:** Contrato de ambiente COM-01; pode iniciar validações em paralelo.
- **Critério objetivo de aceite:** Startup comercial recusa sqlite/auth local/login administrativo; rotas privadas exigem JWT mesmo sem Origin e com Host válido.
- **Testes obrigatórios:** Matriz de configurações inválidas e acesso HTTP direto; leitura de ACL efetiva sem imprimir credenciais.

## COM-06 — Aplicar quota, reserva e limite de chamadas caras por organização

- **Responsável sugerido:** Marwin.
- **Prioridade / complexidade / esforço:** P1 / M / 12–24 horas-pessoa.
- **Descrição técnica:** Budgets por busca e locks não são quota mensal. Implementar controle mínimo persistente em PostgreSQL com reserva atômica e contagem conciliável.
- **Evidência e arquivos/módulos:** backend/sdr/service.py; prospecting/jobs.py; persistence/runtime.py; PostgreSQL; core/sales/groq_provider.py.
- **Impacto:** Risco de consumo excessivo e margem negativa.
- **Labels:** area:backend, cost-control, pilot.
- **Dependências:** Limites acordados D1; COM-02/05; decisão COM-04 para fonte.
- **Critério objetivo de aceite:** Chamadas paralelas/repetidas não ultrapassam teto; falhas/retries/cancel têm política; suspensão bloqueia antes do provider; contador sobrevive a restart.
- **Testes obrigatórios:** Reservas concorrentes, expiração de reserva, idempotência, rate limit e falhas fake 429/5xx; custo/usage reconciliado.

## COM-07 — Configurar identidade e oferta SDR por organização

- **Responsável sugerido:** Fernando.
- **Prioridade / complexidade / esforço:** P1 / M / 8–16 horas-pessoa.
- **Descrição técnica:** Prompt global fixa Fernando/Loung. Reutilizar configuração tenant existente para identidade/oferta aprovadas, sem alterar a fronteira do modelo.
- **Evidência e arquivos/módulos:** core/sales/prompts.py; backend/sdr/policy.py; sdr/service.py; organization_settings.
- **Impacto:** Mensagens podem representar empresa errada.
- **Labels:** area:sdr, multi-tenant, pilot.
- **Dependências:** COM-02/03 para persistência/aceite; contrato de configuração com Laís no D1.
- **Critério objetivo de aceite:** Duas organizações geram identidade/oferta próprias; contexto não cruza tenants; configuração ausente tem erro explícito; revisão humana mantida.
- **Testes obrigatórios:** Provider fake captura prompts A/B; validação de configuração e instrução hostil; histórico e WhatsApp manuais.

## COM-08 — Demonstrar backup e restauração com RPO/RTO

- **Responsável sugerido:** Marwin.
- **Prioridade / complexidade / esforço:** P1 / M / 8–16 horas-pessoa.
- **Descrição técnica:** PgStore delega backup à operação; não há restore atual demonstrado. Documentar e executar ensaio em destino descartável futuro.
- **Evidência e arquivos/módulos:** backend/persistence/postgres.py:PgStore._backup; infraestrutura Supabase; scripts de diagnóstico.
- **Impacto:** Recuperação e perda máxima de dados desconhecidas.
- **Labels:** area:infra, recovery, pilot.
- **Dependências:** Plano de infraestrutura e acesso autorizado a backup; começar inventário D1, ensaio após baseline COM-02.
- **Critério objetivo de aceite:** Proposta de RPO<=24h e RTO<=4h aceita ou renegociada; restore medido, íntegro e sem tocar produção; responsável e runbook definidos.
- **Testes obrigatórios:** Contagens/checksums/relacionamentos e RLS após restore; medir tempo; provar procedimento de retorno.

## COM-09 — Aplicar ciclo mínimo de retenção e portabilidade aprovado

- **Responsável sugerido:** Marwin.
- **Prioridade / complexidade / esforço:** P1 / M / 12–24 horas-pessoa.
- **Descrição técnica:** Purge atual limpa só cache e export é de busca. Adequar retenção e procedimento operacional auditado de export/exclusão por tenant conforme decisão.
- **Evidência e arquivos/módulos:** backend/persistence/searches.py; prospecting/jobs.py; audit_events; tabelas filhas e scripts operacionais futuros.
- **Impacto:** Dados podem persistir além do permitido e encerramento não é demonstrável.
- **Labels:** area:database, privacy, pilot.
- **Dependências:** COM-04 define política; COM-02 e backup COM-08 para liberação.
- **Critério objetivo de aceite:** TTL persistente verificável; dados expirados não reaparecem via fallback; export permitido completo e exclusão por org testados incluindo auditoria/backups conforme política.
- **Testes obrigatórios:** Relógio controlado e reidratação de snapshot expirado; export A/B; integridade dos filhos e execução operacional registrada.

## COM-10 — Controlar contrato e suspensão mínima sem billing completo

- **Responsável sugerido:** Fernando.
- **Prioridade / complexidade / esforço:** P1 / M / 8–16 horas-pessoa.
- **Descrição técnica:** Não há estado comercial por org. Implementar controle mínimo auditado de ativo/suspenso e limites contratados, com operação manual segura.
- **Evidência e arquivos/módulos:** backend/persistence/runtime.py; organization_settings; mecanismo operacional restrito; schema se necessário.
- **Impacto:** Não é possível interromper chamadas caras por contrato ou incidente de uma só org.
- **Labels:** area:backend, commercial, pilot.
- **Dependências:** COM-02/05; contrato de integração com COM-06 no D1.
- **Critério objetivo de aceite:** Suspensão por org bloqueia nova execução cara e não apaga dados; leitura/export conforme política; implantação/mensalidade conciliadas manualmente.
- **Testes obrigatórios:** A/B ativo/suspenso; alteração sem privilégio negada; auditoria; reativação e cache invalidados.

## COM-11 — Concluir experiência mínima de cliente e limites compartilhados

- **Responsável sugerido:** Laís.
- **Prioridade / complexidade / esforço:** P1 / M / 16–28 horas-pessoa.
- **Descrição técnica:** Preferências são locais; UI ainda menciona desktop/local e não explica plenamente locks por org. Integrar identidade SDR/contexto e estados reais.
- **Evidência e arquivos/módulos:** web/src/app/configuracoes; components/prospecting-workspace.tsx; app/sdr/page.tsx; session-provider.tsx; app-shell.tsx.
- **Impacto:** Usuários podem operar contexto inesperado, repetir ações ou esperar recursos inexistentes.
- **Labels:** area:frontend, ux, pilot.
- **Dependências:** Preparação D1; integração COM-01/04/07/10 e contrato de estados COM-06.
- **Critério objetivo de aceite:** Org/papel visíveis; identidade SDR aprovada ou erro; 429 por uso compartilhado compreensível sem retry agressivo; atribuição/aviso conforme política; recuperação de draft e sessão sem perda silenciosa.
- **Testes obrigatórios:** UX de 401/403/409/429/503, teclado/mobile, origem de dados, revisão humana e link WhatsApp; nenhuma promessa falsa de integração.

## COM-12 — Preparar operação limitada, conexões e alertas

- **Responsável sugerido:** Marwin.
- **Prioridade / complexidade / esforço:** P1 / M / 12–20 horas-pessoa.
- **Descrição técnica:** Health é liveness, SQL abre conexão por operação e não limita duração de lock; medir orçamento e preparar readiness, alertas e supervisão.
- **Evidência e arquivos/módulos:** backend/persistence/runtime.py; persistence/postgres.py; timing.py; scripts/run_api.py; configuração futura de hospedagem.
- **Impacto:** Saturação/locks e falhas podem deixar usuários sem diagnóstico.
- **Labels:** area:infra, observability, performance, pilot.
- **Dependências:** Contrato de topologia COM-01; COM-05/06; entradas de COM-13.
- **Critério objetivo de aceite:** Orçamento de conexões aprovado, sem leak; timeouts; readiness detecta falha sem PII; alerta chega ao responsável; uma instância persistente supervisionada no piloto.
- **Testes obrigatórios:** Falha SQL/Auth/provider, timeout/lock, conexões pós-carga, restart/drain e alerta exercitado; pool só se medição justificar.

## COM-13 — Medir capacidade de 100 contas e concorrência acordada

- **Responsável sugerido:** Miqueias.
- **Prioridade / complexidade / esforço:** P1 / M / 16–28 horas-pessoa.
- **Descrição técnica:** Não existe evidência de carga. Preparar harness e executar cenários por org, volume e simultaneidade com provedores fake e PostgreSQL nativo.
- **Evidência e arquivos/módulos:** backend/tests; web/scripts; repository.py:overview; crm/service.py:pipeline/followups/metrics; plano do documento 06.
- **Impacto:** Não se pode prometer capacidade de 100 simultâneos.
- **Labels:** area:qa, load-test, performance, pilot.
- **Dependências:** Preparação D1; ensaios após COM-01/02/06/12; critérios acordados com cliente.
- **Critério objetivo de aceite:** Relatório inclui VUs/RPS/volumes/P95/erros/conexões/locks/custos; atende envelope contratado; zero mistura/corrupção; 429 contabilizado separadamente.
- **Testes obrigatórios:** Degraus 5/20/50/100; duas orgs; soak; concorrência de escrita; refresh; falhas/restart; ver critérios do documento 06.

## COM-14 — Fechar regressão, gates de CI e aceite do piloto

- **Responsável sugerido:** Miqueias.
- **Prioridade / complexidade / esforço:** P1 / M / 12–20 horas-pessoa.
- **Descrição técnica:** pytest.ini omite backend/tests no padrão; build/E2E não homologados. Organizar seleção explícita e pipeline de validação isolada.
- **Evidência e arquivos/módulos:** pytest.ini; backend/tests; web/package.json; web/scripts; workflow futuro.
- **Impacto:** Regressão pode chegar ao cliente sem gate de segurança.
- **Labels:** area:qa, ci, release, pilot.
- **Dependências:** Planejar D1; aceite após COM-03/11/12/13; apoio infra COM-12.
- **Critério objetivo de aceite:** Build/lint/typecheck, regressão e A/B obrigatórios passam; teste bloqueado não vira verde; evidências ligadas à revisão candidata; pipeline impede merge em falha.
- **Testes obrigatórios:** Fluxos completos login→busca→import→CRM→SDR→aprovação→WhatsApp manual/export; usuários owner/admin/member; recuperação e revisão de segurança.

## COM-15 — Integrar release e handover com atualização segura

- **Responsável sugerido:** Fernando.
- **Prioridade / complexidade / esforço:** P1 / M / 8–12 horas-pessoa.
- **Descrição técnica:** Árvore tem alterações preexistentes; falta procedimento de release com jobs/drafts locais. Consolidar revisão candidata e janela futura autorizada.
- **Evidência e arquivos/módulos:** BFF/backend integrados; documentação/runbooks; estado local de jobs/drafts; Git/PRs futuros.
- **Impacto:** Atualização pode interromper job e perder texto não salvo.
- **Labels:** area:integration, release, pilot.
- **Dependências:** Todos COM-01 a COM-14 aceitos para liberar; revisão incremental desde D1.
- **Critério objetivo de aceite:** Commit candidato e evidências aprovados; onboarding controlado, suporte/drain/rollback documentados; nenhum deploy sem autorização futura; decisão GO registrada.
- **Testes obrigatórios:** Smoke de staging, manutenção com drafts/jobs, rollback ensaiado e dois responsáveis assinando checklist.

## COM-16 — Automatizar assinaturas e gateway após validar piloto

- **Responsável sugerido:** Fernando.
- **Prioridade / complexidade / esforço:** P2 / G / 24–48 horas-pessoa.
- **Descrição técnica:** Billing/webhooks não identificados; manual auditado basta somente se aceito no piloto.
- **Evidência e arquivos/módulos:** schema e módulos financeiros futuros; nenhum gateway atual.
- **Impacto:** Operação manual perde eficiência ao escalar.
- **Labels:** area:billing, post-pilot.
- **Dependências:** COM-06/10 e oferta/contrato validados.
- **Critério objetivo de aceite:** Webhook assinado/idempotente; conciliação, carência, cancelamento/reativação e taxa inicial separados.
- **Testes obrigatórios:** Eventos duplicados/fora de ordem/replay; checkout falso; charge/refund quando aplicável.

## COM-17 — Distribuir jobs somente se o envelope exigir

- **Responsável sugerido:** Marwin.
- **Prioridade / complexidade / esforço:** P2 / G / 24–56 horas-pessoa.
- **Descrição técnica:** Executor/cache/cancel são locais; não usar múltiplas réplicas como correção rápida.
- **Evidência e arquivos/módulos:** persistence/searches.py; prospecting/jobs.py; sdr/service.py; Registry.
- **Impacto:** Restart e concorrência distribuída não têm coordenação.
- **Labels:** area:backend, jobs, post-pilot.
- **Dependências:** COM-13 e necessidade comprovada; promover a P1 se cliente exigir.
- **Critério objetivo de aceite:** Jobs/idempotência/cancel e contexto funcionam entre workers; reinício não duplica consumo.
- **Testes obrigatórios:** Dois workers, lease expirado, crash, cancel remoto e A/B; reestimar se incluir broker/serviço novo.

## COM-18 — Otimizar SQL/índices e constraints após medição

- **Responsável sugerido:** Marwin.
- **Prioridade / complexidade / esforço:** P2 / G / 16–40 horas-pessoa.
- **Descrição técnica:** Dashboard/followups/metrics varrem tenant; pipeline consulta último evento por card; datas text e CHECK admitem limitações legadas.
- **Evidência e arquivos/módulos:** repository.py:104; crm/service.py:61/84/200/226; migrations/phase31.
- **Impacto:** Latência/memória podem crescer com o volume; ainda não medidos.
- **Labels:** area:database, performance, post-pilot.
- **Dependências:** COM-13/08; promover correção específica a P1 se critério falhar.
- **Critério objetivo de aceite:** EXPLAIN/carga justificam mudança mínima; sem perda semântica; datas/constraints reconciliadas.
- **Testes obrigatórios:** Contagens antes/depois, casos de datas legadas, P95/carga e integridade; não migrar tecnologia.

## Limite das estimativas

COM-04 estima inventário, coordenação e decisão técnica documentada, não horas de parecer externo nem substituição de dados. COM-09 cobre adequação mínima ao parecer esperado e procedimentos operacionais auditados, não um portal completo de privacidade. Se o parecer proibir o uso central de Places, COM-04 permanece bloqueada e nasce novo escopo P0, fora de 160–288h. COM-12 não pressupõe compra de capacidade nem pool novo sem medição. COM-11 pode preparar UI/contratos antes do backend; só fecha aceite após integrações. COM-03/13/14 também podem preparar casos cedo, mas não fechar antes dos componentes. Essas distinções impedem dependências de aceite de bloquear preparação útil.

