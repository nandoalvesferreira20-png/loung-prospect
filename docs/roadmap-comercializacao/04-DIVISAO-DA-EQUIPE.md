# Divisão da equipe e trabalho paralelo

Revisão: 23/10/2026. Design de execução futura; nenhuma branch/issue/implementação iniciada.

| Pessoa | Entregas primárias do piloto | Esforço-base | Primeiro trabalho |
|---|---|---:|---|
| Fernando | COM-01/04/07/10/15 | 44–80h | Contrato de topologia, API e decisões de dados; integrar BFF, sem assumir toda a infra |
| Laís | COM-11 | 16–28h | Jornada e estados de sessão/limite, identidade e org visível; acordar contratos antes de integrar |
| Miqueias | COM-03/13/14 | 44–72h | Matriz A/B e ambiente de teste inequívoco; preparar regressão/carga e revisar evidências |
| Marwin | COM-02/05/06/08/09/12 | 56–108h | Catálogo/correção de autoria em cópia e perfil comercial seguro; inventariar recuperação |

Total 160–288h. Horas incluem testes/documentação do responsável. Não adicionar novamente a mesma revisão/QA. Reserva de 20% deve ser aplicada por pessoa ao planejar: Fernando 53–96h; Laís 19–34h; Miqueias 53–86h; Marwin 67–130h, arredondamentos aproximados. Soma oficial da reserva é calculada sobre o total: 192–346h. Folga de Laís não se converte automaticamente em horas de especialista SQL/infra.

## Responsabilidades e fronteiras de arquivo

**Fernando:** dono de `web/src/lib/api`, auth/proxy Next e integração de topologia; dono do prompt/política SDR e controle mínimo de contrato em COM-10. Coordena jurídico/comercial COM-04, mas não emite parecer. Revisa segurança com Miqueias e banco com Marwin. Não fica responsável por escrever todos os testes, banco, backup e monitoramento.

**Laís:** dona de `web/src/app` de configurações/SDR e componentes de experiência, incluindo estados de erro/limite/sessão. Não edita simultaneamente proxies de Fernando. Configuração comercial SDR usa contrato fornecido por COM-07; preferências no localStorage continuam identificadas como locais. Pode apoiar roteiros de usabilidade e documentação do cliente dentro de COM-11; expansão de escopo precisa estimativa.

**Miqueias:** dono de testes backend/web, matriz negativa, harness e relatório de carga, gates/workflow de validação. Revisa decisões de segurança independentemente. Qualquer ajuste de código detectado por teste é encaminhado ao dono do módulo; não contorna a restrição com mock que torne teste artificialmente verde.

**Marwin:** dono de persistência, schema futuro, configuração backend, quota/consumo, timeouts/conexões, readiness, backup e operação. Cuida do banco descartável e da evidência de catálogo. Mudanças em runtime.py e jobs.py são serializadas entre seus próprios cartões; Fernando não altera esses arquivos diretamente em paralelo.

## Pontos de integração e revisão

| Contrato/entrega | Produtor | Consumidor/revisor | Momento |
|---|---|---|---|
| Host/origem/upstream e erros de sessão | Fernando | Marwin/Miqueias; Laís consome estados | D1, fechar antes de alterar módulos |
| Correção de autoria + identidade transacional | Marwin | Miqueias; Fernando revisa integração | D2–3 no cenário otimista |
| Campos permitidos/retention/attribution | Fernando + responsável externo | Marwin/Laís/Miqueias | Até D2 para caber em dez dias |
| Configuração SDR e contrato ativo/suspenso | Fernando | Marwin implementa leitura/consumo; Laís integra UI | Contrato D1, integração D4–6 |
| Quota/códigos 429/limites por org | Marwin | Laís/Miqueias | D4; UI não implementa retry agressivo |
| Readiness/métricas/conexões | Marwin | Miqueias | D6 para ensaio de carga |
| Retenção/export/restore | Marwin | Miqueias e Fernando | D8–10; dependem de decisão externa |
| Candidato e checklist | Fernando integra | Miqueias valida, Marwin aprova operação, Laís UX | D10 somente com evidências completas |

Dependências são de aceite: QA e UI podem preparar cenários/esqueleto com contratos, sem declarar integração aprovada. Se um contrato mudar, atualizar consumidores no mesmo marco e reexecutar os testes afetados.

## Branches e PRs propostos para futura autorização

Preservar inicialmente a árvore suja: há diversas alterações preexistentes, inclusive arquivos críticos não rastreados. Antes da execução, Fernando e Marwin devem identificar quais fazem parte da baseline candidata; não descartar, resetar ou misturar alterações alheias. Branches/worktrees só após autorização de implementação e baseline acordada; não foram criadas agora.

Proposta: uma branch curta por cartão `feat/com-XX-descricao` ou `fix/com-XX-descricao`, a partir da baseline estável; PRs pequenos por responsabilidade; nenhum push direto à principal. Quando backend e UI dependem de contrato, backend primeiro ou PRs empilhados explicitando base/dependência. Não usar quatro branches longas com cópias divergentes de runtime/proxy.

PR de banco tem owner Marwin e revisão de Fernando/Miqueias; BFF de Fernando revisado por Miqueias; UI de Laís revisada por Fernando e roteiro QA; workflow/harness de Miqueias revisado por Marwin/Fernando. Toda alteração de RLS/Auth exige revisão independente. PR inclui gatilho/problema, comportamento final, teste, risco/retorno e dependências; só mergear com gates relevantes passando. Secret/ambiente jamais entram no PR.

Nenhum deploy automático em merge inicial: a primeira liberação terá decisão explícita de GO, backup e janela autorizada. Depois estabilizar release repetível sem colocar jobs/drafts ativos em risco.
