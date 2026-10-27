# Execução paralela, dependências e duração

Reorganização: 23/10/2026. Plano futuro, sem execução de código, branches, commits, mudanças no ambiente, banco ou aplicativo. Complementa os documentos [09](09-BACKLOG-EQUILIBRADO.md) e [11](11-TAREFAS-POR-DESENVOLVEDOR.md). A distribuição antiga de 04/05 é histórica; requisitos e gates de 06/07 permanecem.

## Modelo de planejamento

São 31 fatias dos mesmos 15 pais, não 31 projetos nem 31 PRs obrigatórios. As estimativas por pai foram preservadas; todos programam e escrevem testes. Miqueias define estratégia, critérios e evidências QA; outros três implementam testes automatizados e corrigem seus módulos, com revisão cruzada de segurança.

Capacidade: **6h produtivas por pessoa/dia**, quatro pessoas, 24h-pessoa/dia, sem contar 8h nominais como implementação contínua. Cada pessoa dispõe de 40–72h-base, referência 56h. Total 160–288h, referência 224h. O limite aritmético sem dependências é 6,7–12 dias; isso não é duração executável.

Foi construída uma agenda por precedências e disponibilidade de cada pessoa, com inserção em janelas livres e serialização dos arquivos sensíveis. A referência usa o ponto médio de cada fatia. Foram verificados ausência de ciclos, no máximo uma fatia ativa por pessoa, pré-requisitos e somas. A agenda é viável no modelo, não prova de ótimo global nem medição real de produtividade. Não foi executado teste da aplicação ou carga para produzir essas durações.

## Dependências e contratos

Todas as linhas também dependem de acessos/contexto inicial; o tempo técnico de fechar baseline/contratos está nos primeiros cartões, não numa etapa gratuita. A decisão externa de COM-04-B é uma barreira adicional sem duração conhecida. Os identificadores abaixo são pré-requisitos de execução integrada; preparação de teste/contrato pode ser antecipada sem encerrar aceite.

| Fatia | Pessoa | Horas | Pré-requisitos |
|---|---|---:|---|
| COM-01-A | Fernando | 6–10 | Contexto inicial; primeira onda |
| COM-01-B | Laís | 6–10 | Contexto inicial; primeira onda |
| COM-02-A | Marwin | 4–8 | Contexto inicial; primeira onda |
| COM-02-B | Miqueias | 4–8 | COM-02-A |
| COM-03-A | Miqueias | 8–12 | COM-02-B, COM-05-A |
| COM-03-B | Laís | 4–6 | COM-01-A, COM-01-B, COM-02-B, COM-05-A, COM-05-B |
| COM-03-C | Fernando | 4–6 | COM-03-A, COM-06-B, COM-07-A, COM-07-B |
| COM-04-A | Laís | 4–8 | Contexto inicial; primeira onda |
| COM-04-B | Fernando | 4–8 | COM-04-A |
| COM-05-A | Miqueias | 2–4 | Contexto inicial; primeira onda |
| COM-05-B | Laís | 2–4 | Contexto inicial; primeira onda |
| COM-06-A | Marwin | 6–12 | COM-02-A |
| COM-06-B | Miqueias | 6–12 | COM-06-A, COM-10-A, COM-05-A, COM-07-A |
| COM-07-A | Laís | 4–8 | COM-02-A |
| COM-07-B | Fernando | 4–8 | COM-07-A |
| COM-08-A | Marwin | 4–8 | COM-02-A |
| COM-08-B | Fernando | 4–8 | COM-08-A |
| COM-09-A | Laís | 6–12 | COM-04-B, COM-02-A, COM-06-B |
| COM-09-B | Marwin | 6–12 | COM-04-B, COM-02-A, COM-06-B |
| COM-10-A | Miqueias | 4–8 | COM-02-A, COM-05-A |
| COM-10-B | Fernando | 4–8 | COM-10-A |
| COM-11-A | Laís | 8–14 | COM-07-A, COM-07-B, COM-10-A, COM-06-B, COM-04-B |
| COM-11-B | Fernando | 8–14 | COM-01-A, COM-01-B, COM-06-B, COM-10-A |
| COM-12-A | Marwin | 8–12 | COM-02-A, COM-05-A |
| COM-12-B | Miqueias | 4–8 | COM-12-A, COM-01-A, COM-10-A, COM-06-B |
| COM-13-A | Miqueias | 8–14 | Contexto inicial; primeira onda |
| COM-13-B | Marwin | 8–14 | COM-13-A, COM-12-A, COM-12-B, COM-06-B, COM-10-B, COM-09-A, COM-09-B, COM-07-B |
| COM-14-A | Fernando | 6–10 | COM-03-A, COM-03-B, COM-03-C, COM-11-A, COM-11-B, COM-13-B, COM-08-B, COM-09-B, COM-12-B |
| COM-14-B | Laís | 6–10 | COM-03-A, COM-03-B, COM-03-C, COM-11-A, COM-11-B, COM-09-B, COM-12-B |
| COM-15-A | Marwin | 4–6 | COM-13-B, COM-08-B, COM-09-B |
| COM-15-B | Miqueias | 4–6 | COM-14-A, COM-14-B, COM-15-A, COM-08-B, COM-13-B, COM-09-A |

**Regras transversais de aceite:** COM-01 precisa do Host/runtime de COM-12-B; COM-03 precisa dos negativos e da revisão final do candidato; COM-08 exige restauração+verificador; COM-09 exige restore aprovado antes de liberar exclusão/portabilidade; COM-06/10 precisam dos hooks reais; COM-13 só fecha com candidato/ambiente consistentes; COM-15-B só aceita com todos os pais fechados. Essas são dependências de liberação, não motivos para impedir preparação técnica paralela. Nenhum pai se encerra apenas pelo calendário.

## O que começa junto

- Fernando: COM-01-A, allowlists BFF/contrato de topologia. Não acumula toda a integração de backend.
- Laís: COM-04-A, gerador/inventário sintético; depois COM-05-B e COM-01-B. Tem trabalho técnico antes de a API nova estar pronta.
- Miqueias: COM-05-A, guarda comercial backend; em seguida COM-13-A, harness e estratégia QA. Não espera todos terminarem para começar testes.
- Marwin: COM-02-A, catálogo/autoria em cópia; depois COM-08-A, backup/restore e COM-06-A, núcleo de reserva SQL.

No meio do trabalho: Laís programa settings/retention enquanto Marwin cuida de SQL/conexões; Miqueias integra quota/suspensão/readiness; Fernando implementa prompt, verificadores e UX de prospecção. No fechamento: CI/regressão de Fernando e E2E de Laís ocorrem em paralelo; Marwin prepara pacote operacional e Miqueias valida o manifesto e aceite. Não há uma única pessoa como ponto de integração de todas as camadas.

## Propriedade dos arquivos e prevenção de conflitos

| Área/arquivo | Dono de edição e ordem | Revisão independente |
|---|---|---|
| web/src/lib/api/local-request.ts e proxies de API | Fernando COM-01-A; Laís usa contratos, sem editar esses proxies ao mesmo tempo | Miqueias |
| web/src/proxy.ts e lib/auth | Laís COM-05-B → COM-01-B; não confundir com lib/api/proxy.ts de Fernando | Fernando |
| backend/main.py e config.py | Miqueias COM-05-A; Marwin entrega requisitos; mudanças posteriores só por handoff | Marwin |
| persistence/postgres.py | Marwin COM-02-A → COM-12-A; nenhum outro dev altera o adaptador durante essas fatias | Miqueias/Fernando |
| Ledger/schema de consumo propostos | Marwin COM-06-A; contratos fixados antes dos hooks | Miqueias |
| Entitlements e settings SDR | Miqueias COM-10-A e Laís COM-07-A, módulos/keys distintos; schema compartilhado revisado por Marwin | Marwin/Fernando |
| backend/sdr/service.py | Laís entrega adaptador/configuração COM-07-A; Miqueias integra hooks COM-06-B depois; Fernando muda prompt em core/policy/adaptador puro | Fernando/Marwin |
| persistence/searches.py | Miqueias COM-06-B → handoff para Laís COM-09-A; dependência explícita impede quota e retenção em edição simultânea | Fernando/Miqueias |
| prospecting/jobs.py | Miqueias COM-06-B → Marwin COM-09-B no trecho export/operacional; dependência explícita | Laís/Fernando |
| persistence/runtime.py | Miqueias integra readiness/Host/entitlement COM-12-B depois dos contratos e hooks; Fernando/Marwin não abrem edição concorrente | Fernando/Marwin |
| UI settings/SDR e UI prospecção/sessão | Laís COM-11-A: settings/sdr; Fernando COM-11-B: prospecting-workspace/session-provider/app-shell; contrato visual único | Revisão recíproca + Miqueias |
| Testes SQL, HTTP e jobs/IA | Miqueias COM-03-A; Laís COM-03-B; Fernando COM-03-C; arquivos de suite distintos, fixtures-base com dono Miqueias | Revisor de outra pessoa |
| Carga/coletores, CI e E2E | Miqueias COM-13-A; Marwin COM-13-B; Fernando COM-14-A; Laís COM-14-B | Miqueias define aceite; autores não aprovam sozinhos |
| Release e manifesto | Marwin COM-15-A: scripts/drain/retorno; Miqueias COM-15-B: validador/evidências; não editar os mesmos runbooks ao mesmo tempo | Fernando/Laís |

Arquivos novos são propostas de fatias modulares pequenas, não autorização de refatoração. Reutilizar testes/providers/core existentes. Agrupar PRs por contrato ou camada, com dependência explícita; PR de segurança/banco passa por revisor independente. Se precisar tocar arquivo alheio, combinar handoff e atualizar a agenda antes, não resolver conflito repetidamente no fim. As alterações preexistentes da árvore são baseline a preservar, não trabalho descartável.

## Agenda diária de referência (224h totais)

A tabela abaixo é derivada dos pontos médios. D1 é o primeiro dia de execução futura autorizada, não uma data de calendário. Célula vazia/espera indica falta de pré-requisito, não redução de escopo. A fração de hora é esforço útil, não duração de espera jurídica. Cada coluna soma 56h.

| Dia | Fernando | Laís | Miqueias | Marwin |
|---|---|---|---|---|
| D1 | COM-01-A 6h | COM-04-A 6h | COM-05-A 3h; COM-13-A 3h | COM-02-A 6h |
| D2 | COM-01-A 2h; COM-04-B 4h | COM-05-B 3h; COM-01-B 3h | COM-13-A 6h | COM-08-A 6h |
| D3 | COM-04-B 2h; COM-08-B 4h | COM-01-B 5h; COM-07-A 1h | COM-13-A 2h; COM-10-A 4h | COM-06-A 6h |
| D4 | COM-08-B 2h; COM-10-B 4h | COM-07-A 5h | COM-10-A 2h; COM-02-B 4h | COM-06-A 3h; COM-12-A 3h |
| D5 | COM-10-B 2h; COM-07-B 4h | COM-03-B 4h | COM-02-B 2h; COM-06-B 4h | COM-12-A 6h |
| D6 | COM-07-B 2h; COM-11-B 1h | COM-03-B 1h; COM-09-A 1h | COM-06-B 5h; COM-12-B 1h | COM-12-A 1h; COM-09-B 1h |
| D7 | COM-11-B 6h | COM-09-A 6h | COM-12-B 5h; COM-03-A 1h | COM-09-B 6h |
| D8 | COM-11-B 4h | COM-09-A 2h; COM-11-A 4h | COM-03-A 6h | COM-09-B 2h; COM-13-B 4h |
| D9 | COM-03-C 3h | COM-11-A 6h | COM-03-A 3h | COM-13-B 6h |
| D10 | COM-03-C 2h; COM-14-A 4h | COM-11-A 1h; COM-14-B 4h | Espera / trabalho-base concluído | COM-13-B 1h; COM-15-A 5h |
| D11 | COM-14-A 4h | COM-14-B 4h | COM-15-B 2h | Espera / trabalho-base concluído |
| D12 | Espera / trabalho-base concluído | Espera / trabalho-base concluído | COM-15-B 3h | Espera / trabalho-base concluído |

Primeira onda fecha perfis/contratos/cópia; integração de quota e dados ocorre até aproximadamente D6; instrumentação/readiness e retenção até D8; carga, isolamento e UI convergem até D10; CI/E2E/aceite encerram em D12 na referência. O candidato usado na carga deve corresponder às camadas medidas: se depois houver mudança material de SQL/Auth/quotas/topologia, repetir os cenários afetados antes do manifesto final. Esse retrabalho pode consumir reserva ou exigir replanejamento.

## Agenda auditável em horas úteis globais

h0 é início do D1 e cada seis horas úteis avança um dia. Intervalos [início,fim) permitem verificar precedências e ausência de sobreposição; não representam uma jornada contínua de 69h. Mapeamento: h0–6=D1, h6–12=D2, ..., h66–72=D12.

| Fatia | Pessoa | Início h | Fim h |
|---|---|---:|---:|
| COM-01-A | Fernando | 0 | 8 |
| COM-04-A | Laís | 0 | 6 |
| COM-02-A | Marwin | 0 | 6 |
| COM-05-A | Miqueias | 0 | 3 |
| COM-13-A | Miqueias | 3 | 14 |
| COM-05-B | Laís | 6 | 9 |
| COM-08-A | Marwin | 6 | 12 |
| COM-04-B | Fernando | 8 | 14 |
| COM-01-B | Laís | 9 | 17 |
| COM-06-A | Marwin | 12 | 21 |
| COM-08-B | Fernando | 14 | 20 |
| COM-10-A | Miqueias | 14 | 20 |
| COM-07-A | Laís | 17 | 23 |
| COM-10-B | Fernando | 20 | 26 |
| COM-02-B | Miqueias | 20 | 26 |
| COM-12-A | Marwin | 21 | 31 |
| COM-07-B | Fernando | 26 | 32 |
| COM-03-B | Laís | 26 | 31 |
| COM-06-B | Miqueias | 26 | 35 |
| COM-11-B | Fernando | 35 | 46 |
| COM-09-A | Laís | 35 | 44 |
| COM-09-B | Marwin | 35 | 44 |
| COM-12-B | Miqueias | 35 | 41 |
| COM-03-A | Miqueias | 41 | 51 |
| COM-11-A | Laís | 44 | 55 |
| COM-13-B | Marwin | 44 | 55 |
| COM-03-C | Fernando | 51 | 56 |
| COM-15-A | Marwin | 55 | 60 |
| COM-14-A | Fernando | 56 | 64 |
| COM-14-B | Laís | 56 | 64 |
| COM-15-B | Miqueias | 64 | 69 |

## Caminho crítico com restrição de pessoas

Na agenda de referência, uma cadeia crítica é **COM-05-A → COM-13-A → COM-10-A → COM-02-B → COM-06-B → COM-12-B → COM-03-A → COM-03-C → COM-14-A → COM-15-B**. Ela soma 69h úteis de calendário do projeto (11,5 dias de 6h, arredondado para 12). Parte das setas expressa ordem de ocupação de Miqueias, não dependência funcional entre os módulos; tratá-la como sequência obrigatória de produto seria incorreto. Repriorizar essa pessoa pode alterar o caminho; isso não reduz seus critérios de QA.

Há caminhos concorrentes de **COM-04-A/B → COM-09-A/B → COM-11-A ou COM-13-B → COM-14/15** e **COM-08-A/B → COM-13/15**. Um parecer externo atrasado, restore reprovado ou carga com falha pode dominar o prazo. A redistribuição remove o gargalo exclusivo de Marwin; não elimina a convergência final de segurança e QA. Miqueias pode programar com eficiência e ainda precisa de revisão externa de seu próprio backend.

## Duração recalculada

Mesma ordem de agenda e mesmas precedências, substituindo durações por limites inferior/médio/superior e deslocando slots para cumprir handoffs:

| Cenário | Esforço total | Por pessoa | Duração simulada em horas úteis | Dias úteis-base | Com 20% no esforço/duração técnica |
|---|---:|---:|---:|---:|---:|
| Inferior | 160h | 40h | 50h | 9 dias (8,3 antes de arredondar) | 10 dias |
| Referência | 224h | 56h | 69h | 12 dias (11,5 antes de arredondar) | 14 dias |
| Superior | 288h | 72h | 88h | 15 dias (14,7 antes de arredondar) | 18 dias |

Reserva de 20% totaliza 192–345,6h; é cenário técnico proporcional, não previsão estatística. **Faixa de planejamento: 9–15 dias-base; 10–18 com reserva; referência prudente 14 dias.** Somar espera externa de contratos/acesso/provisionamento e reestimar defeitos grandes ou mudança de escopo. Trabalho de contratos e inventário dos devs já foi contado; somente a espera/resposta externa não tem duração conhecida.

**Cinco dias continuam inviáveis:** capacidade 120h é menor que o mínimo 160h. **Dez dias podem caber apenas no cenário inferior**, dependências destravadas cedo e sem mudança material; não anunciar dez dias como compromisso por ter 25% para cada pessoa. Comparado ao antigo plano prudente 12–22 dias, o novo 10–18 retira concentração, mas é uma nova hipótese de agenda, não melhoria de desempenho demonstrada.

## Marcos e decisão

1. Início: confirmar proficiência Full Stack, baseline, envelope do cliente e contratos entre módulos; rever tarefas se o custo de transferência ultrapassar estimativa.
2. Após COM-02/05: autoria/guards equivalentes aprovados em cópia. Proteger credenciais e rede; nada autoriza aplicar migration real.
3. COM-04-B: decisão externa vinculante para o plano. Se vetada/indefinida, NO-GO, sem substituir fonte por conta própria.
4. Após COM-06/07/09/10/12: integração instrumentada apta a ensaios; QA avalia se o candidato é equivalente ao testado.
5. COM-13/14: carga no volume/pico contratado e regressão completa, incluindo 100 simultâneos se isso tiver sido contratado; 100 cadastros não comprovam esse pico.
6. COM-08/15: restore independente, onboarding/rollback/drain e manifesto completos; GO só com todos os P0/P1 e decisão técnica/comercial. Qualquer requisito obrigatório faltante mantém NO-GO.

Se o trabalho real desbalancear: redistribuir fatias **ainda não iniciadas** e de módulo distinto, com dono/revisor definidos; preservar trabalho em andamento e revisão especializada. Não mover uma alteração RLS crítica no último dia para fazer o percentual fechar. Horas registradas e risco têm precedência sobre igualdade aritmética.

