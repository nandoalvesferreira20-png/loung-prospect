# Requisitos comerciais SaaS

Data: 23/10/2026. Arquitetura proposta, sem implementação de planos, pagamentos ou novos endpoints.

## Separação de responsabilidades

```text
auth.users → profiles                         identidade
organizations → organization_members(role)    tenant e autorização
plan_catalog → plan_versions → limits         oferta versionada
organization → subscription → billing_events contrato/estado financeiro
subscription → invoices / payments           cobrança/recebimento
organization → usage_ledger / reservations    consumo e orçamento
subscription + limits + usage → entitlements  acesso efetivo
operator_identity → admin_actions             administração Loung
```

Preservar Auth, organizations, memberships e RLS. Papel não representa plano; usuário não representa assinatura; pagamento não substitui membership. Organização é unidade de contrato/consumo; claims editáveis do cliente não são fonte financeira de verdade.

## Catálogo preliminar recebido

| Plano | Implantação única | Mensalidade | Limites |
|---|---:|---:|---|
| Starter | R$ 297 | R$ 79 | A definir após medir custo |
| Professional | R$ 497 | R$ 149 | A definir após medir custo |
| Business | R$ 997 | R$ 299 | A definir após medir custo |

Não houve validação de margem nem cadastro desses preços. Versionar moeda, periodicidade, preço e benefícios; contrato referencia a versão adquirida. Implantação deve ser item financeiro distinto da recorrência, com política de aceite/reembolso. Tributação/faturamento dependem de validação comercial/contábil externa.

## Capacidades e lacunas

| Capacidade | Estado observado | Requisito futuro |
|---|---|---|
| Empresas | Organization e slug no schema | Dados de contrato/fiscais necessários, contato e finalidade |
| Usuários/papéis | Owner/admin/member, gestão owner, convite manual | Onboarding auditado, convite seguro, assentos e recuperação de owner |
| Plano/limites | Não identificados | Catálogo versionado; assentos, leads, buscas, IA, export e armazenamento |
| Trial/piloto | Não identificado | Prazo, teto, conversão e encerramento |
| Assinatura | Não identificada | Estado, competência, referência externa e histórico append-only |
| Pagamento | Não identificado | Gateway futuro, implantação separada, renovação e conciliação |
| Suspensão | Flag global de escrita | Estado por org/serviço, motivo, autor, tolerância e reativação |
| Portabilidade | Export da busca | Export completo permitido do tenant; retenção/exclusão pós-contrato |
| Admin Loung | Não identificado | Identidade operacional separada, MFA, ações justificadas/auditadas |

## Ciclo comercial e webhook futuro

Estados propostos: pending_setup → trialing/active → past_due → grace → suspended → canceled. Reativação exige confirmação e política explícita. Guardar datas/motivos; cancelar não deve apagar leads ou remover memberships automaticamente. Separar suspensão financeira, segurança e privacidade; definir leitura/exportação durante carência e encerramento.

Webhook futuro deve validar assinatura, corpo bruto e janela temporal; persistir chave única provider/event_id; processar transação idempotente; tolerar duplicação, replay, atraso e eventos fora de ordem; usar inbox durável, retry e conciliação. Checkout/redirect do navegador não confirma pagamento. Nenhum webhook foi criado nesta fase.

## Medição e entitlement

Ledger por organization, recurso, unidade, competência, origem/idempotency_key, quantidade, estado e custo estimado/real. Reservar orçamento atomicamente antes da chamada e liquidar depois; definir cobrança de falhas/cancelamentos e liberar reservas expiradas. Registrar usage de provider quando disponível. Limite global e por tenant deve funcionar entre réplicas; reinício não pode zerar mensalidade/consumo.

Chamadas caras e novos jobs consultam entitlement no backend. Worker leva organização/ator derivados da origem autenticada e revalida autorização e suspensão antes de executar. Não confiar na organização enviada em payload externo. Cache de entitlement precisa invalidação; upgrade/downgrade no período precisa política documentada.

## Onboarding e administração

Admin Loung não reutiliza owner de cliente como superadmin. Preferir ações operacionais estreitas e segregar credencial de implantação; nunca expor service role no browser. Impersonação não é requisito do piloto; se futura, exigirá motivo, política e auditoria explícitos.

Primeiro cliente: criar org/owner por procedimento idempotente e auditado, conferir convite/recovery e isolamento, registrar contrato/limites/estado e suporte. Cobrança manual pode ser opção de piloto se aprovada comercialmente, conciliada e auditada; não equivale a assinatura automatizada. Controle de acesso, custo e suspensão continua necessário.
