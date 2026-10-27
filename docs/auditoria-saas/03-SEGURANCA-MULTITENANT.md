# Segurança multi-tenant

Data: 23/10/2026. Inspeção estática; sem exploração contra produção.

**Não foi demonstrado vazamento entre organizações.** Há controles reais no código, mas a garantia depende do schema/ACL efetivamente implantado e de testes negativos integrados ainda não executados nesta sessão.

## Fronteiras verificadas no código

1. `backend/authorization.py:TokenVerifier.verify`: TLS/JWKS, algoritmo ES256/RS256, assinatura, issuer, audience, claims exp/iat/sub/iss/aud obrigatórias, expiração e role authenticated; sub normalizado UUID. Não aceita somente decode sem assinatura.
2. `backend/persistence/runtime.py:authorize`: verifica JWT e consulta memberships; x-organization-id só é aceito com associação; ausência de header escolhe primeira membership ordenada por slug. Papel comercial vem do banco.
3. `backend/persistence/postgres.py:Database.open` e `session_queries.py:STATEMENTS`: SET LOCAL ROLE loung_api, claims mínimas e app.organization_id locais à transação. Credencial SQL é confiável e exclusiva do servidor; seu comprometimento permitiria definir contexto SQL. RLS não substitui proteção dessa credencial.
4. `Connection.__init__`: revalida membership por conexão; escrita obtém advisory lock por org. Parâmetros são vinculados; nomes de campos variáveis vêm de modelos/constantes do servidor.
5. `202610190001_phase31.sql`: tabelas comerciais com ENABLE/FORCE RLS e organização ativa + is_member para leitura e escrita; FKs compostas preservam tenant dos filhos. Identidade tem políticas próprias, sem FORCE; migration_map é reservado à operação.
6. `202610200002_team_operations.sql`: funções SECURITY DEFINER com search_path vazio, ACL estreita, checagem de grants e revalidação de owner; proteção do último owner e auditoria. Não foi encontrado uso de service role no fluxo HTTP revisado; não foram examinadas credenciais reais.

## Matriz de acesso

| Recurso | Leitura | Mutação/execução | Proteção de ID/tenant |
|---|---|---|---|
| Leads/pipeline | Membro da org ativa | Membro + flag; revisão em edição | Reader/writer sob RLS |
| Interações/follow-ups | Membro; lead autorizado | Membro + flag/transação/revision | RLS e FK org/lead |
| SDR/histórico | Lead/histórico RLS | Geração/cache por org; salvar com flag | Registry org e draft associado ao lead |
| Busca/resultados | Manager por org; fallback SQL RLS | Um job por manager; checkpoint sob Identity | Cache org e SELECT payload RLS |
| Export CSV/XLSX | Mesmo manager/get da busca | GET de resultado terminado | ID de B não está no manager A; fallback RLS |
| Equipe | team_roster verifica org/membership, inclui e-mail | Owner; sem autoalteração; flag | SQL revalida owner/org e último owner |
| Auditoria org | Endpoint owner/admin e RLS | Triggers; runtime sem escrita direta | Funções/grants restritos |
| Perfis | Próprio e compartilhados conforme policy | Sem edição pública identificada | Membership compartilhada |
| Administração Loung | Não identificada | Não implementada | Fronteira futura separada |

Consultas SQL de CRM/SDR por ID frequentemente não repetem organization_id. Isso é aceitável somente com a conexão transacional e RLS corretas; não classificá-las isoladamente como IDOR comprovado. Não foi encontrado caminho HTTP PostgreSQL sem middleware (exceto health) ou fallback silencioso local.

## Jobs e caches

`PgJobManager.start` usa copy_context; Registry é indexado por org. SDR guarda requestIds/drafts por org, compartilhados entre membros, não por usuário. Middleware revalida membership a cada requisição. Revogação durante chamada externa já iniciada não cancela a chamada; checkpoint revalida membership e pode falhar. Não foi constatada mistura A/B, mas falta teste determinístico concorrente e de revogação.

Registry não elimina organizações inativas e limita 32 entradas: a 33ª pode receber 503 até reinício. Limites/cancelamento/cache são locais ao processo, não coordenados entre réplicas. Isso afeta disponibilidade e custo, não prova acesso cruzado.

## Menor privilégio e auditoria

O endpoint de atividades restringe owner/admin e omite old_value/new_value. Contudo, RLS SELECT de audit_events para loung_api verifica membership, não role comercial. O fluxo atual aplica a restrição na API; o banco não replica esse RBAC. Triggers de filhos podem guardar mensagem/descrição nos JSON de auditoria. Revisar autorização e retenção antes de novos consumidores SQL (SAAS-16).

Authenticated tem grants SELECT delimitados pelas policies; nas tabelas comerciais também exige active_org, não definido automaticamente no PostgREST. Não recebe escrita comercial direta. Organizations/profiles/memberships têm políticas de associação distintas. Funções definer precisam de revisão de owner/ACL em ambiente real: SQL local não comprova grants herdados efetivos.

## Riscos priorizados

| ID | Severidade | Evidência/natureza | Recomendação |
|---|---|---|---|
| SAAS-03 | P0 | Catálogo real/matriz negativa não verificados; gap de garantia | Catálogo sanitizado read-only e testes A/B nativos isolados |
| SAAS-05 | P0 condicional | SQLite em main.py não aplica JWT/membership | Perfil comercial deve recusar modo legado e auth local |
| SAAS-02 | P0 | Histórico registra trigger/autoria incompatível e flag zero | Homologar correção existente numa fase autorizada |
| SAAS-07 | P1 | Locks/TTL não são orçamento/limite distribuído | Quotas, ledger e reservas atômicas por org |
| SAAS-12 | P1 | Cookies delegados SDK; HTTPS/headers não homologados | Verificar sessão, origem/CSRF e headers na topologia escolhida |
| SAAS-16 | P2 | Policy de auditoria não distingue owner/admin; payload sensível | Decidir menor privilégio e retenção no banco |

Impacto, dependências, aceite e complexidade completos no [backlog](07-BACKLOG-PRIORIZADO.md). P0 não significa exploit confirmado em todos os casos.

## Testes mínimos e evidência existente

| Cenário | Cobertura identificada | Pendência |
|---|---|---|
| A não lê leads de B | test_phase31_postgres:test_isolation_and_no_privilege_escalation | Reexecutar isolado com configuração equivalente |
| A não altera B | test_phase32_team:test_lead_create_edit_isolation_revision_and_audit | Cobrir todos verbos de CRM/import/SDR |
| A não exporta B | Caminho estático manager org + RLS | Teste HTTP explícito export/status/results/import/cancel com searchId de B |
| Jobs não misturam orgs | copy_context; manager por org | Concorrência A/B, reinício, revogação e checkpoints |
| IA não recebe contexto de B | Lead RLS e evidence allowlist | Provider spy captura contexto exato A/B; mesmos requestId/draftId |
| Sem membership é negado | test_phase31_security:test_nonmember_and_connection_failure | Não executado nesta sessão |
| Member não administra | test_phase32_team:test_roster_and_owner_permissions | Todos verbos e grants SQL efetivos |
| Header org não concede acesso | test_phase31_security:test_requested_org_requires_membership | Reexecutar e incluir seleção multi-org legítima |

Apenas oito casos JWT foram executados agora. Presença dos outros testes evidencia intenção/cobertura escrita, não uma aprovação nova.
