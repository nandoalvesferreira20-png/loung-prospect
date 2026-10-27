# Resumo executivo — comercialização do Loung Prospect

Revisão: 23/10/2026, America/Sao_Paulo. **Recomendação atual: NO-GO.** A base existente deve ser aproveitada; não há justificativa demonstrada para reconstruir o produto ou trocar a stack.

## 1. Qual o percentual de prontidão?

**Aproximadamente 45%, como indicador de evidência para o piloto; interpretar como faixa de 40–50%.** Não é percentual de código concluído, cobertura de testes ou probabilidade de sucesso. Há funcionalidades avançadas, mas a aceitação comercial depende de produção, isolamento e operação ainda não comprovados.

Método transparente: vinte critérios com o mesmo peso, 0=ausente/bloqueado/sem evidência mínima de aceite, 1=implementação ou controle parcial sem validação integrada, 2=validação local concluída **no escopo delimitado**. O nível 2 local não substitui homologação do ambiente. Soma 18/40=45%, arredondada como ordem de grandeza; uma classificação diferente pode deslocar a faixa. Gates P0 não são compensados pela pontuação.

| Critério | Pontos |
|---|---:|
| Sessão/login integrados | 1 |
| Validador JWT unitário | 2 |
| Contratos/origem BFF no escopo local | 2 |
| Organizações/equipe | 1 |
| RLS/isolamento efetivo | 1 |
| Leitura de leads | 1 |
| Escrita real homologada | 0 |
| Pipeline/follow-ups | 1 |
| Dashboard | 1 |
| Prospecção | 1 |
| Exportação | 1 |
| SDR por cliente | 1 |
| WhatsApp manual | 1 |
| Histórico/auditoria | 1 |
| Onboarding/configuração | 1 |
| Produção centralizada | 0 |
| Consumo financeiro/limites por org | 0 |
| Restore demonstrado | 0 |
| Monitoramento/diagnóstico | 1 |
| Release/regressão | 1 |
| **Total** | **18/40** |

Não usar essa pontuação como promessa comercial. Nem 90% liberaria cliente com P0 aberto. A matriz de estados funcionais está no [documento 01](01-ESTADO-ATUAL.md).

## 2. O que impede comercializar hoje?

Host público é recusado; escrita/autoria tem pendência histórica sem prova atual; isolamento efetivo precisa de catálogo e negativos A/B; retenção/export Places não tem adequação demonstrada; modo legado precisa ser impedido no perfil comercial. Além disso faltam quotas/custos, identidade SDR por cliente, recuperação, privacidade, operação e release homologados. Não foi demonstrado vazamento; desconhecimento não é aprovação.

O código não mudou em relação ao snapshot anterior de 418 arquivos comparados. A releitura confirmou bloqueios e aprofundou escala: a mesma org aceita uma busca e uma geração de IA por vez, rejeitando concorrentes com 429. O limite Registry=32 refere-se a organizações, não usuários.

## 3. Quantas tarefas?

**5 P0 + 10 P1 = 15 para o piloto**, mais **3 P2 pós-piloto**. Decomposição completa pronta para copiar ao Projects no [backlog](03-BACKLOG-TECNICO.md). Nenhuma issue foi criada no GitHub. Dependências externas e eventuais novos defeitos podem gerar cartões adicionais; a contagem não é garantia de escopo fechado.

## 4. Quem faz o quê?

| Pessoa | Entregas | Horas-base |
|---|---|---:|
| Fernando | Domínio/BFF/sessão, decisão de dados, SDR por cliente, contrato/suspensão, integração/entrega | 44–80 |
| Laís | Contexto visível e UX dos limites/sessão/SDR, configuração e atribuição conforme contrato | 16–28 |
| Miqueias | Isolamento/RBAC, carga, regressão/E2E e gates | 44–72 |
| Marwin | Escrita/perfil seguro, quota, retenção/portabilidade, conexões/alertas e restore | 56–108 |

Marwin/Miqueias assumem entregas críticas próprias; Fernando não centraliza banco, operação e toda a validação. [Divisão e contratos de integração](04-DIVISAO-DA-EQUIPE.md).

## 5. Qual o esforço?

**160–288 horas-pessoa**, sendo 116–216 de desenvolvimento/infra/UX/integração e 44–72 de QA. Com reserva de 20%: **192–346h**. Intervalos incluem testes/documentação do dono; QA integrado e revisão transversal já estão nos cartões próprios. Não somar uma segunda equipe de QA às mesmas horas.

Premissas: correção de autoria existente reutilizável, uma instância persistente, limites explícitos, carteira compartilhada e cobrança manual aceitas, sem substituir fonte de dados. Parecer externo, espera de acesso e mudanças significativas de escopo não têm duração conhecida. P2 de billing/fila/otimização soma 64–144h fora do piloto; correção necessária para passar carga deve ser promovida e reestimada.

## 6. É viável em 5–10 dias úteis?

**Cinco dias não cabem no mínimo atual. Dez dias são um cenário otimista condicionado, não compromisso.** Quatro pessoas × 6h produtivas/dia dão 120h em cinco e 240h em dez. Marwin tem 56–108h, cerca de 9,3–18 dias antes da reserva. Plano prudente: **12–22 dias úteis com reserva**, além de esperas externas. [Cronograma diário](05-CRONOGRAMA-ACELERADO.md) explicita como o caso mínimo chega a D10 sem esconder dependências.

Veto/indefinição Places, exigência de carteira privada por vendedor ou 100 buscas/gerações simultâneas invalidam a hipótese acelerada. Não reduzir segurança para cumprir a data.

## 7. Qual o caminho crítico?

Baseline e decisão de dados → autoria/perfil seguro → quota/estado → operação/conexões → carga e correções → regressão/candidato. Retenção e restore concorrem pelo tempo de Marwin e também bloqueiam saída. Em paralelo: identidade SDR/contrato → UX → E2E. Decisão contratual externa pode ser o maior caminho crítico sem prazo estimável.

## 8. O que fica para depois?

Billing/gateway e webhooks completos, fila distribuída se o piloto de instância única satisfizer o envelope, e otimizações SQL/constraints sem falha demonstrada. Não adiar adequação mínima de dados, quota, restore ou segurança. Onboarding e cobrança podem começar com procedimento controlado auditado em vez de portais administrativos completos, se aprovados.

## 9. Quais testes devem passar?

Matriz A/B de leitura/escrita/export/jobs/IA; membership/roles/header forjado; autoria e rollback; CRM/revision/histórico; quota/suspensão; retenção/fallback/export; sessão TLS/recovery; E2E; build/lint/typecheck; restore; carga no pico/volume contratados. Metas propostas incluem P95 leitura/CRM<=2s, erros inesperados<1%, zero corrupção/leak, <=80% do orçamento de conexões, estabilidade no soak e RPO/RTO aceitos. Os números são metas futuras, não medições.

Nesta revisão passaram **14 testes Python selecionados e 16 Node**; TypeScript/lint concluíram sem diagnósticos. Sete casos adicionais ficaram bloqueados no setup por permissão da pasta temporária, não falha funcional demonstrada; integração SQL, build, carga e restore não foram executados. Cem contas cadastradas e cem simultâneos permanecem capacidades distintas e não atestadas. [Plano de teste detalhado](06-TESTES-E-ESCALABILIDADE.md).

## 10. GO, GO CONDICIONAL ou NO-GO?

**NO-GO agora.** Evoluir para GO somente com P0/P1 mínimos aceitos e evidências do [checklist](07-CHECKLIST-GO-LIVE.md). GO CONDICIONAL admite restrições operacionais mensuráveis e capacidade menor aceita por escrito; não admite risco de vazamento, licença indefinida ou ausência de recuperação como condições toleráveis.

Foram criados apenas oito documentos novos em docs/roadmap-comercializacao/. Código, dados, ambientes e auditoria anterior foram preservados. Não houve implementação, branch, commit, issue, alteração no GitHub, migration real ou deploy. **Aguardar autorização explícita para executar o roadmap.**
