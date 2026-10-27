# Roadmap de implementação proposto

Data: 23/10/2026. **Este documento não autoriza executar nenhuma fase.** Implementação depende de autorização explícita posterior.

| Ordem | Objetivo | Dependências | Critério de conclusão |
|---|---|---|---|
| 0 | Evidência atual e decisão contratual Places | Responsáveis técnico/jurídico/comercial | Catálogo read-only sanitizado e decisão sobre uso/retenção/export/atribuição; SAAS-03/04 encaminhados |
| 1 | Isolamento e escrita em ambiente descartável | Banco/schema equivalente, sem credencial real | Testes A/B nativos, autoria, último owner, rollback e migração idempotente passam; SAAS-02/03/05 |
| 2 | Preparar operação centralizada | Fase 1 e topologia escolhida | Domínio HTTPS, upstream/origem restritos, sessões e segredo segregado; SAAS-01/12 |
| 3 | Recuperação, release e custo | Fases 1/2, métricas sintéticas | Restore e RPO/RTO; build/lint/testes no pipeline; quotas/ledger/alertas; SAAS-07/09/13/14 |
| 4 | Preparar primeiro cliente | Fases 0–3 aprovadas | Identidade SDR por tenant, contrato/entitlement, onboarding e privacidade; SAAS-08/10/11/15 |
| 5 | Piloto controlado | Todos P0 fechados; P1 relevantes comprovados | Número de orgs/carga limitado por escrito; suporte, custo/erros e revisão humana acompanhados |
| 6 | Lançamento pago repetível | Revisão dos resultados do piloto | Margem, capacidade, recuperação e onboarding reproduzíveis; P1 concluídos; aceite técnico/comercial |
| 7 | Escala e automação | Modelo validado e operação estável | Fila durável entre réplicas, desempenho e gateway/webhooks conforme necessidade |

Fila distribuída pode ser diferida num piloto de instância única somente com limites de capacidade/restart explicitamente aceitos. Não diferir para múltiplas réplicas com promessa de continuidade. Cobrança manual pode ser decisão comercial do piloto, mas exige conciliação, contrato, suspensão e limites. P3 do gateway significa automação posterior, não ausência de controle financeiro.

## Sequência segura de mudança futura

Inventário/backup → teste em cópia descartável → proposta mínima revisável → autorização de implantação → aplicação controlada → verificação → observação/rollback previsto. Não usar desktop para atualizar banco real SaaS, reaplicar migrations antigas indiscriminadamente ou habilitar flags antes da homologação. Avaliar a correção de autoria já existente antes de criar solução paralela.

Não estimar data de lançamento sem decidir licença dos dados, operação e capacidade. Complexidades no backlog são relativas, não cronograma contratado.

## Testes existentes por domínio

| Domínio | Arquivos identificados | Cobertura escrita / limites |
|---|---|---|
| Auth | backend/tests/test_phase31_security.py, test_auth_tls.py; web/scripts/auth.test.mjs | Claims/assinatura, falha segura, middleware/config; só oito casos JWT executados agora |
| Multiempresa/banco | test_phase31_postgres.py, test_phase32_team.py, test_auth_schema_acl.py, test_stamp_claims_migration.py | RLS, IDOR negativo, autoria, ACL, último owner e SQL; fixtures aplicam migrations, não executadas |
| Leads/CRM/pipeline | test_crm_api.py, test_phase32_writes.py, test_phase32_team.py | Revisão, transação, histórico, follow-ups, métricas e falha de audit |
| Prospecção | test_prospecting_api.py, test_prospecting_batch.py; tests/test_google_places.py e test_prospecting.py | Budget, cancel, parcial, dedup, export, rollback e providers simulados |
| SDR | test_sdr_api.py; tests/test_sales_groq.py e test_sales.py | Allowlist, idempotência local, falhas, recusa/telefone, salvar/aprovar e providers simulados |
| UI/contratos | web/scripts/auth.test.mjs, prospecting.test.mjs, team.test.mjs e check_*.py | Testes de código/fixtures e checks específicos; não equivalem a E2E comercial completo |
| Comercial financeiro | Nenhum módulo correspondente identificado | Testes de assinatura/entitlement/webhook a criar quando houver implementação |

`pytest.ini` padrão aponta apenas tests/: backend/tests deve ser incluído explicitamente no pipeline. `tests/conftest.py` bloqueia rede/browser em caracterização; `backend/scripts/run_offline_tests.py` restringe rede a loopback, o que isoladamente não prova que banco local é descartável.

## Lacunas e testes futuros prioritários

- A/B: leitura/mutação/export/import/cancel/status com IDs alheios; jobs e IA simultâneos; mesmo requestId/draftId e revogação durante processamento.
- Sessão: refresh/expiração, JWKS indisponível, recovery/convite, logout e cookies no domínio TLS real homologado.
- SQL: grants herdados/owners efetivos, FKs, rollback integral e concorrência nativa com snapshots; restore e migração sintética idempotente.
- Prospecção: consumo real contado em fake provider, TTL persistente conforme contrato, reinício/checkpoint e cancelamento entre réplicas.
- SDR: provider spy no contexto exato, identidade/oferta por org, falha de provedor, idempotência durável e revisão humana sem envio automático.
- Comercial futuro: quota/reserva concorrente, upgrade/downgrade, vencimento/carência/suspensão/reativação; webhook duplicado, fora de ordem e replay.

Não executar suites SQL contra localhost apenas por ser local. Validar marcador de banco descartável e isolamento antes de fixtures que contêm DDL, GRANT/REVOKE e dados. Nenhuma dessas suites foi executada nesta auditoria.
