# Checklist de aprovação do piloto

Data: 23/10/2026. Estado atual **NO-GO**. Caixas vazias são pendências; nenhum item é aprovado apenas por este documento. Evidência deve identificar revisão candidata, ambiente e responsável. Implementar/aplicar/deployar exige autorização futura.

## Escopo comercial e dados

- [ ] Fernando: cliente aceita carteira compartilhada, papéis e envelope de simultaneidade medido; 100 contas não são promessa de 100 buscas simultâneas.
- [ ] Fernando/externo: COM-04 aprovada por responsável jurídico/comercial para campos Places, retenção, atribuição e export. Veto ou parecer pendente mantém NO-GO.
- [ ] Fernando: proposta registra preço/assentos/limites, implantação, mensalidade, cobrança manual se escolhida, cancelamento, carência e suporte. Margem baseada em medição, sem uso ilimitado implícito.
- [ ] Fernando/Marwin: finalidade, papéis de tratamento, terceiros/Groq/WhatsApp, avisos, opt-out, retenção, export/exclusão e encerramento têm procedimento aprovado e praticável.
- [ ] Marwin/Miqueias: snapshots expirados não reaparecem; export/exclusão respeitam org e política, incluindo filhos/audit/backups conforme retenção.

## Segurança e funcionalidades

- [ ] Fernando/Miqueias: domínio HTTPS, origens/Host/upstream e cookies/sessões homologados, recovery/logout/refresh exercitados.
- [ ] Marwin/Miqueias: perfil comercial recusa sqlite/auth local e credenciais administrativas; JWT/membership obrigatórios em todos recursos privados.
- [ ] Marwin: catálogo/owner/ACL/RLS/triggers efetivos documentados; correção de autoria validada em cópia e procedimento de aplicação/retorno revisado.
- [ ] Miqueias: A não lê/altera/importa/exporta/cancela/acessa status de B; jobs e IA não usam contexto alheio; header trocado, sem membership e member em admin negados.
- [ ] Miqueias: owner/admin/member, último owner, revogação concorrente, autoria e falha de auditoria têm resultado correto em PostgreSQL nativo.
- [ ] Laís/Miqueias: Dashboard/leads/pipeline/follow-ups apresentam dados e estados verdadeiros; revisão 409 não perde alterações; 401/403/429/503 têm orientação útil.
- [ ] Fernando/Laís: SDR usa identidade/oferta da organização e contexto permitido; mantém edição/revisão humana e histórico; WhatsApp envia somente por ação humana externa, sem inferir contato pelo clique.
- [ ] Marwin/Miqueias: quota/reserva/custo por org sobrevive a restart e impede chamada cara após teto/suspensão; falha/cancel/retry têm política testada.

## Operação e qualidade

- [ ] Marwin/Miqueias: backup/restore isolado aprovado, integridade conferida, RPO/RTO medidos e aceitos; nenhum ensaio sobrepõe produção.
- [ ] Miqueias: carga atende o pico e volume contratados no documento 06; relatório separa erros de 409/429 esperados; sem corrupção/leak; margem de conexões/recursos comprovada.
- [ ] Marwin: readiness, supervisão, timeouts SQL/lock, métricas sanitizadas e alerta <=5min exercitados; responsável de plantão e runbook definidos.
- [ ] Miqueias: build de produção em ambiente descartável, lint/typecheck, regressão web/backend/desktop e E2E relevantes passam; testes bloqueados/faltantes explicitados e resolvidos antes do aceite obrigatório.
- [ ] Fernando/Marwin: baseline inclui conscientemente arquivos preexistentes necessários; segredos ausentes dos artefatos; revisão candidata rastreável; PRs revisados e gates satisfeitos.
- [ ] Fernando/Laís/Marwin: atualização prevê jobs/drafts locais, aviso, drain/manutenção e retorno. Não prometer zero downtime com estado apenas em memória.
- [ ] Fernando: onboarding idempotente de org/owner e até 100 convites/contas controlados, recuperação e suporte ensaiados; sem criar usuários nesta auditoria.
- [ ] Responsável autorizado: aprova separadamente eventual aplicação de banco, flags e deploy. Este checklist não concede essa autorização.

## Decisão registrada

| Decisão | Regra |
|---|---|
| NO-GO | Qualquer P0 aberto; ausência de evidência obrigatória de isolamento/restore; fonte vetada; carga fora do contrato; estado atual |
| GO CONDICIONAL | P0 e requisitos mínimos de segurança/recuperação resolvidos; restrições remanescentes operacionais e mensuráveis aceitas por escrito, com dono/prazo e capacidade reduzida comprovada; nunca aceitar vazamento ou licença indefinida como condição |
| GO | P0 e P1 do piloto concluídos e evidenciados, escopo/capacidade aceitos, decisão técnica/comercial e autorização de liberação registradas |

Campos do termo futuro: candidato/commit, ambiente, data, cliente, contas/pico/volume, limites, restrições, evidências, responsáveis, suporte e rollback. Miqueias aprova QA/segurança, Marwin operação/banco, Laís experiência e Fernando integração/comercial com o responsável externo. Divergência em critério obrigatório mantém NO-GO; cronograma vencido não altera a regra.
