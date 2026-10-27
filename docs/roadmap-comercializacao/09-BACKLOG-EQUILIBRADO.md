# Backlog equilibrado — piloto Loung Prospect

Reorganização: 23/10/2026. Escopo exclusivamente documental. Este plano substitui a atribuição de execução dos documentos 03/04/05/08, preservados como histórico; critérios técnicos, fontes, checklist 07 e plano de teste 06 continuam obrigatórios. Não se alterou a prontidão NO-GO nem se autorizou implementação.

## Resultado e premissas

As **15 tarefas-pai (5 P0 e 10 P1)** foram decompostas em **31 subtarefas**, sem criar requisito novo para preencher carga. A soma de cada pai continua exatamente igual ao intervalo original. Total: **160–288h-pessoa**; cada desenvolvedor **40–72h**, ponto médio **56h**, ou **25%** dos 224h de referência. Igualdade é de esforço estimado, não de quantidade de cartões, especialidade ou resultado real.

Os limites são envelopes de incerteza, não blocos de tempo artificialmente garantidos. Os 25% valem no orçamento mínimo conjunto, no ponto médio e no máximo conjunto; se tarefas reais variarem independentemente, os percentuais realizados mudarão. Não perseguir 25% em tempo apontado adiando entrega ou transferindo controle crítico a alguém sem preparo.

Premissas: capacidade Full Stack para Laís no adaptador de persistência/retention e para Miqueias em Python/backend, revisões independentes por pessoas experientes e contratos pequenos. Essa proficiência não foi medida nesta reorganização. Confirmá-la no início por revisão de uma fatia pequena; se exigir formação/retrabalho além do envelope, usar reserva e reestimar, sem diminuir segurança. Não é necessário tornar todos especialistas de toda a stack: núcleo SQL transacional e conexões continua com Marwin; superfície de BFF/prompt e verificação independente com Fernando; settings/retention e UI com Laís; entitlements/hooks/readiness e estratégia QA com Miqueias.

Os intervalos incluem programação, testes do componente, correções locais esperadas, documentação e participação técnica nas integrações/revisões planejadas. Registrar o tempo uma única vez, na subtarefa de quem o executa; participação do revisor é coberta por sua própria frente de testes/integração e pela reserva quando extrapolar. Não transformar cada subtarefa em um PR isolado obrigatório: agrupar por contrato para evitar 31 handoffs. Falha importante, substituição da fonte Places, fila distribuída ou novo requisito comercial exige nova estimativa.

## Distribuição

| Pessoa | Antes | Agora | Referência | Participação planejada |
|---|---:|---:|---:|---:|
| Fernando | 44–80h | 40–72h | 56h | 25% |
| Laís | 16–28h | 40–72h | 56h | 25% |
| Miqueias | 44–72h | 40–72h | 56h | 25% |
| Marwin | 56–108h | 40–72h | 56h | 25% |
| Total | 160–288h | 160–288h | 224h | 100% |

Reserva de 20%: **192–345,6h totais** (aproximadamente 192–346h); **48–86,4h por pessoa**, referência 67,2h. A meta 40–72h é base, não teto de execução incluindo contingência. Não há nova promessa de reduzir esforço; o ganho esperado é retirar concentração por recurso.

## Base real conferida e limites desta revisão

Relidos backlog 03, divisão 04, cronograma 05 e checklist 07; conferidos config.py, main/runtime, postgres, searches, jobs, sdr/service, local-request e inventários de testes/persistência. Permanecem no código restrições localhost, JWT/membership e RLS transacional, executor/locks locais e ausência de ciclo persistente de retenção no caminho atual. A correção de autoria já existe e deve ser reutilizada/homologada. Não foi conectado banco, lido valor de ambiente, reexecutado teste de aplicação nem medida carga nesta tarefa de planejamento.

Caminhos marcados **propostos** abaixo e no documento 11 são locais futuros de implementação, não arquivos que já existem nem instrução para criá-los agora. Não implementar broker, framework novo ou refatoração estética para obter o equilíbrio.

## Matriz de preservação dos pais e de seus critérios

### COM-01 — Habilitar topologia comercial e sessão segura

**P0; intervalo original preservado: 12–20h.**

| Subtarefa | Dono | Horas | Entrega |
|---|---|---:|---|
| COM-01-A | Fernando | 6–10 | Topologia e BFF com allowlists explícitas |
| COM-01-B | Laís | 6–10 | Sessão SSR, cookies e fluxos Auth no domínio |

**Aceite integral mantido:** Domínio HTTPS autorizado opera login/leitura/mutação; origem/Host/upstream hostis negados; refresh/logout/recovery homologados.

**Testes do pai mantidos:** BFF local e remoto permitido; cross-origin e SSRF negativos; cookies e expiração no staging.

**Fechamento:** requer todas as subtarefas do pai e suas integrações, evidências ligadas ao candidato e revisão independente. Um componente isolado ou teste mock não encerra o pai.

### COM-02 — Homologar escrita e autoria com correção existente

**P0; intervalo original preservado: 8–16h.**

| Subtarefa | Dono | Horas | Entrega |
|---|---|---:|---|
| COM-02-A | Marwin | 4–8 | Catálogo, correção existente e transações de autoria |
| COM-02-B | Miqueias | 4–8 | Automatizar homologação de autoria e rollback |

**Aceite integral mantido:** Criação/edição/import/SDR sintéticos persistem ator correto; erro em trigger não deixa linhas parciais; catálogo compatível documentado.

**Testes do pai mantidos:** test_phase32_writes; test_stamp_claims_migration; falha de auditoria e revisão 409.

**Fechamento:** requer todas as subtarefas do pai e suas integrações, evidências ligadas ao candidato e revisão independente. Um componente isolado ou teste mock não encerra o pai.

### COM-03 — Provar isolamento multiempresa e papéis ponta a ponta

**P0; intervalo original preservado: 16–24h.**

| Subtarefa | Dono | Horas | Entrega |
|---|---|---:|---|
| COM-03-A | Miqueias | 8–12 | Estratégia QA e testes SQL/RBAC multiempresa |
| COM-03-B | Laís | 4–6 | Testes HTTP de IDOR e exportação por tenant |
| COM-03-C | Fernando | 4–6 | Programar provas de contexto isolado nos jobs e IA |

**Aceite integral mantido:** Zero leitura/escrita/exportação/contexto entre A/B; sem membership negado; member sem admin; revogação e header forjado negados.

**Testes do pai mantidos:** A/B HTTP e SQL; provider spy; jobs simultâneos; ACL/owners; concorrência nativa do último owner.

**Fechamento:** requer todas as subtarefas do pai e suas integrações, evidências ligadas ao candidato e revisão independente. Um componente isolado ou teste mock não encerra o pai.

### COM-04 — Fechar decisão de uso comercial dos dados e APIs

**P0; intervalo original preservado: 8–16h.**

| Subtarefa | Dono | Horas | Entrega |
|---|---|---:|---|
| COM-04-A | Laís | 4–8 | Inventário técnico de dados e rastreamento por campo |
| COM-04-B | Fernando | 4–8 | Decisão contratual e especificação técnica rastreável |

**Aceite integral mantido:** Decisão escrita aprova ou veta campos, retenção, export e atribuição; COM-09/11 recebem requisitos; veto mantém NO-GO.

**Testes do pai mantidos:** Rastrear campos reais em captura sintética; revisão do inventário e dos requisitos com QA; sem chamada real nesta auditoria.

**Fechamento:** requer todas as subtarefas do pai e suas integrações, evidências ligadas ao candidato e revisão independente. Um componente isolado ou teste mock não encerra o pai.

### COM-05 — Impedir modos legados e privilégios administrativos em perfil comercial

**P0; intervalo original preservado: 4–8h.**

| Subtarefa | Dono | Horas | Entrega |
|---|---|---:|---|
| COM-05-A | Miqueias | 2–4 | Implementar guarda de perfil comercial no backend |
| COM-05-B | Laís | 2–4 | Implementar guarda de modo local no Next |

**Aceite integral mantido:** Startup comercial recusa sqlite/auth local/login administrativo; rotas privadas exigem JWT mesmo sem Origin e com Host válido.

**Testes do pai mantidos:** Matriz de configurações inválidas e acesso HTTP direto; leitura de ACL efetiva sem imprimir credenciais.

**Fechamento:** requer todas as subtarefas do pai e suas integrações, evidências ligadas ao candidato e revisão independente. Um componente isolado ou teste mock não encerra o pai.

### COM-06 — Aplicar quota, reserva e limite de chamadas caras por organização

**P1; intervalo original preservado: 12–24h.**

| Subtarefa | Dono | Horas | Entrega |
|---|---|---:|---|
| COM-06-A | Marwin | 6–12 | Programar quota/reserva persistente e atômica |
| COM-06-B | Miqueias | 6–12 | Integrar quota e estado antes de chamar providers |

**Aceite integral mantido:** Chamadas paralelas/repetidas não ultrapassam teto; falhas/retries/cancel têm política; suspensão bloqueia antes do provider; contador sobrevive a restart.

**Testes do pai mantidos:** Reservas concorrentes, expiração de reserva, idempotência, rate limit e falhas fake 429/5xx; custo/usage reconciliado.

**Fechamento:** requer todas as subtarefas do pai e suas integrações, evidências ligadas ao candidato e revisão independente. Um componente isolado ou teste mock não encerra o pai.

### COM-07 — Configurar identidade e oferta SDR por organização

**P1; intervalo original preservado: 8–16h.**

| Subtarefa | Dono | Horas | Entrega |
|---|---|---:|---|
| COM-07-A | Laís | 4–8 | Programar configuração SDR por organização |
| COM-07-B | Fernando | 4–8 | Aplicar identidade e oferta ao prompt seguro |

**Aceite integral mantido:** Duas organizações geram identidade/oferta próprias; contexto não cruza tenants; configuração ausente tem erro explícito; revisão humana mantida.

**Testes do pai mantidos:** Provider fake captura prompts A/B; validação de configuração e instrução hostil; histórico e WhatsApp manuais.

**Fechamento:** requer todas as subtarefas do pai e suas integrações, evidências ligadas ao candidato e revisão independente. Um componente isolado ou teste mock não encerra o pai.

### COM-08 — Demonstrar backup e restauração com RPO/RTO

**P1; intervalo original preservado: 8–16h.**

| Subtarefa | Dono | Horas | Entrega |
|---|---|---:|---|
| COM-08-A | Marwin | 4–8 | Programar/definir backup e restauração isolada |
| COM-08-B | Fernando | 4–8 | Programar verificador independente de restore |

**Aceite integral mantido:** Proposta de RPO<=24h e RTO<=4h aceita ou renegociada; restore medido, íntegro e sem tocar produção; responsável e runbook definidos.

**Testes do pai mantidos:** Contagens/checksums/relacionamentos e RLS após restore; medir tempo; provar procedimento de retorno.

**Fechamento:** requer todas as subtarefas do pai e suas integrações, evidências ligadas ao candidato e revisão independente. Um componente isolado ou teste mock não encerra o pai.

### COM-09 — Aplicar ciclo mínimo de retenção e portabilidade aprovado

**P1; intervalo original preservado: 12–24h.**

| Subtarefa | Dono | Horas | Entrega |
|---|---|---:|---|
| COM-09-A | Laís | 6–12 | Programar retenção e impedir reidratação expirada |
| COM-09-B | Marwin | 6–12 | Programar portabilidade e exclusão operacional auditada |

**Aceite integral mantido:** TTL persistente verificável; dados expirados não reaparecem via fallback; export permitido completo e exclusão por org testados incluindo auditoria/backups conforme política.

**Testes do pai mantidos:** Relógio controlado e reidratação de snapshot expirado; export A/B; integridade dos filhos e execução operacional registrada.

**Fechamento:** requer todas as subtarefas do pai e suas integrações, evidências ligadas ao candidato e revisão independente. Um componente isolado ou teste mock não encerra o pai.

### COM-10 — Controlar contrato e suspensão mínima sem billing completo

**P1; intervalo original preservado: 8–16h.**

| Subtarefa | Dono | Horas | Entrega |
|---|---|---:|---|
| COM-10-A | Miqueias | 4–8 | Programar entitlement e suspensão por organização |
| COM-10-B | Fernando | 4–8 | Programar operação restrita de contrato e conciliação |

**Aceite integral mantido:** Suspensão por org bloqueia nova execução cara e não apaga dados; leitura/export conforme política; implantação/mensalidade conciliadas manualmente.

**Testes do pai mantidos:** A/B ativo/suspenso; alteração sem privilégio negada; auditoria; reativação e cache invalidados.

**Fechamento:** requer todas as subtarefas do pai e suas integrações, evidências ligadas ao candidato e revisão independente. Um componente isolado ou teste mock não encerra o pai.

### COM-11 — Concluir experiência mínima de cliente e limites compartilhados

**P1; intervalo original preservado: 16–28h.**

| Subtarefa | Dono | Horas | Entrega |
|---|---|---:|---|
| COM-11-A | Laís | 8–14 | Programar UI de configuração, SDR e atribuição |
| COM-11-B | Fernando | 8–14 | Programar UX de prospecção, sessão e contexto |

**Aceite integral mantido:** Org/papel visíveis; identidade SDR aprovada ou erro; 429 por uso compartilhado compreensível sem retry agressivo; atribuição/aviso conforme política; recuperação de draft e sessão sem perda silenciosa.

**Testes do pai mantidos:** UX de 401/403/409/429/503, teclado/mobile, origem de dados, revisão humana e link WhatsApp; nenhuma promessa falsa de integração.

**Fechamento:** requer todas as subtarefas do pai e suas integrações, evidências ligadas ao candidato e revisão independente. Um componente isolado ou teste mock não encerra o pai.

### COM-12 — Preparar operação limitada, conexões e alertas

**P1; intervalo original preservado: 12–20h.**

| Subtarefa | Dono | Horas | Entrega |
|---|---|---:|---|
| COM-12-A | Marwin | 8–12 | Programar limites SQL e orçamento de conexões |
| COM-12-B | Miqueias | 4–8 | Programar readiness, Host e alertas sanitizados |

**Aceite integral mantido:** Orçamento de conexões aprovado, sem leak; timeouts; readiness detecta falha sem PII; alerta chega ao responsável; uma instância persistente supervisionada no piloto.

**Testes do pai mantidos:** Falha SQL/Auth/provider, timeout/lock, conexões pós-carga, restart/drain e alerta exercitado; pool só se medição justificar.

**Fechamento:** requer todas as subtarefas do pai e suas integrações, evidências ligadas ao candidato e revisão independente. Um componente isolado ou teste mock não encerra o pai.

### COM-13 — Medir capacidade de 100 contas e concorrência acordada

**P1; intervalo original preservado: 16–28h.**

| Subtarefa | Dono | Horas | Entrega |
|---|---|---:|---|
| COM-13-A | Miqueias | 8–14 | Programar harness e estratégia mensurável de carga |
| COM-13-B | Marwin | 8–14 | Executar carga e programar coleta/análise operacional |

**Aceite integral mantido:** Relatório inclui VUs/RPS/volumes/P95/erros/conexões/locks/custos; atende envelope contratado; zero mistura/corrupção; 429 contabilizado separadamente.

**Testes do pai mantidos:** Degraus 5/20/50/100; duas orgs; soak; concorrência de escrita; refresh; falhas/restart; ver critérios do documento 06.

**Fechamento:** requer todas as subtarefas do pai e suas integrações, evidências ligadas ao candidato e revisão independente. Um componente isolado ou teste mock não encerra o pai.

### COM-14 — Fechar regressão, gates de CI e aceite do piloto

**P1; intervalo original preservado: 12–20h.**

| Subtarefa | Dono | Horas | Entrega |
|---|---|---:|---|
| COM-14-A | Fernando | 6–10 | Programar gates CI e regressão integrada |
| COM-14-B | Laís | 6–10 | Programar E2E de jornadas e revisão humana |

**Aceite integral mantido:** Build/lint/typecheck, regressão e A/B obrigatórios passam; teste bloqueado não vira verde; evidências ligadas à revisão candidata; pipeline impede merge em falha.

**Testes do pai mantidos:** Fluxos completos login→busca→import→CRM→SDR→aprovação→WhatsApp manual/export; usuários owner/admin/member; recuperação e revisão de segurança.

**Fechamento:** requer todas as subtarefas do pai e suas integrações, evidências ligadas ao candidato e revisão independente. Um componente isolado ou teste mock não encerra o pai.

### COM-15 — Integrar release e handover com atualização segura

**P1; intervalo original preservado: 8–12h.**

| Subtarefa | Dono | Horas | Entrega |
|---|---|---:|---|
| COM-15-A | Marwin | 4–6 | Programar atualização segura e pacote operacional |
| COM-15-B | Miqueias | 4–6 | Programar agregação de evidências e coordenar aceite QA |

**Aceite integral mantido:** Commit candidato e evidências aprovados; onboarding controlado, suporte/drain/rollback documentados; nenhum deploy sem autorização futura; decisão GO registrada.

**Testes do pai mantidos:** Smoke de staging, manutenção com drafts/jobs, rollback ensaiado e dois responsáveis assinando checklist.

**Fechamento:** requer todas as subtarefas do pai e suas integrações, evidências ligadas ao candidato e revisão independente. Um componente isolado ou teste mock não encerra o pai.

## Condições de fechamento que atravessam pais

- COM-01 só fecha após Host/topologia de COM-12-B, guarda COM-05, cookies COM-01-B e jornada final COM-14-B. Contratos podem ser preparados antes; isso não é aceite antecipado de produção.
- COM-03 só fecha com seus três negativos, COM-02/05, rota/banco equivalente e checagem do candidato em COM-14/15. Miqueias mantém a estratégia e o veto QA, mas não é o único autor dos testes.
- COM-04 depende da decisão externa escrita. Seu esforço técnico não estima espera nem parecer jurídico. Veto ou indefinição mantém NO-GO; adequações de COM-09/11 continuam necessárias mesmo se houver aprovação.
- COM-06/10 exigem hooks reais de COM-06-B/12-B, estado e reservas persistentes; uma API ou ledger isolado não prova bloqueio de consumo. Não aumentar réplicas para contornar lock/429.
- COM-08 só fecha após restauração e verificador independente; COM-09 exige essa evidência para liberar portabilidade/exclusão. Nenhum teste de recuperação sobrepõe dados reais.
- COM-12/13 são iterativos: instrumentar antes, medir depois, corrigir falhas demonstradas e repetir. A preparação do harness não equivale a teste de carga concluído.
- COM-14/15 exigem revisão candidata consistente, build e regressão completos, onboarding controlado, manutenção/drain/retorno e aceite técnico/comercial. Não existe autorização implícita de deploy ou migration.

O [checklist 07](07-CHECKLIST-GO-LIVE.md) continua sem exceções. As pessoas antigas nele são histórico: para execução, usar donos de subtarefa e revisores do [documento 11](11-TAREFAS-POR-DESENVOLVEDOR.md), mantendo Miqueias em QA, Marwin em banco/operação, Laís em experiência e Fernando em integração/comercial, sem dono aprovar sozinho sua mudança crítica.

P2 COM-16/17/18 não entra em 160–288h. Se carga ou contrato exigir fila distribuída/otimização específica ou outro modelo de dados, promover a exigência e reequilibrar o orçamento; não prometer o mesmo prazo ocultando esse escopo.

Agenda, dependências exatas e edição de arquivos: [10-EXECUCAO-PARALELA.md](10-EXECUCAO-PARALELA.md). Fichas individuais completas: [11-TAREFAS-POR-DESENVOLVEDOR.md](11-TAREFAS-POR-DESENVOLVEDOR.md).

