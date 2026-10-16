# Fase 2.4 — Pipeline comercial e CRM

## Resultado e auditoria

Implementados Kanban, perfil comercial `/leads/[id]`, atividades, observações, agendamento/reagendamento/conclusão de retornos, `/meu-dia` e indicadores no Dashboard. Nenhuma migration, tabela ou coluna foi adicionada. Nenhum arquivo desktop, `.env`, provider Google/Groq ou dado da base original foi alterado.

Foram consultadas as documentações das fases 2.1–2.3, o schema/repositórios SQLite, `core/commercial/values.py`, `day.py`, o Meu Dia desktop, contratos/BFF, indicadores e fluxo SDR. A inspeção somente leitura encontrou 217 leads em `Novo`, com `lead_interactions`, `outreach`, `outreach_revisions` e os campos comerciais necessários já presentes. O construtor dos repositórios desktop migra schema: a API não o chama.

## Status e regras do Kanban

Reutilizados `STATUSES`, `commercial_status` e `STATUS_ALIASES`. O quadro mantém as 12 etapas reais do desktop e acrescenta colunas para status personalizados encontrados no banco. A proposta inicial de sete etapas não foi aplicada porque apagaria distinções comerciais importantes, como reunião, proposta, retorno, ausência de resposta e restrição de contato.

| Registro legado | Coluna visual |
| --- | --- |
| Novo Lead, Mensagem gerada, Revisado | Novo |
| Contatado | Contato realizado |
| Respondeu | Em conversa |
| Reunião, Reunião marcada | Reunião agendada |
| Não interessado | Sem interesse |
| Demais status personalizados | Mesmo nome, em coluna própria |

Ler ou escolher a coluna canônica em que o lead já aparece **não regrava o alias**. Mover explicitamente para outra etapa atualiza `leads.status` e `updated_at`, com evento contendo o valor anterior literal e o novo. Não há segundo campo de status. Contato realizado, Fechado e Perdido pedem confirmação adicional na interface e `confirmed:true` na API; contato confirmado também registra `ultimo_contato`. `Fechado` representa conversão declarada manualmente pelo operador, sem confirmação por integração. Não é possível inventar novos status pela API; destinos personalizados precisam existir na base. A edição/criação de categorias fica fora desta fase.

Não foi criada uma etapa automática “Abordagem preparada”: gerar rascunho continua sem alterar status. As abordagens salvas aparecem na última atividade e na linha do tempo, identificadas como rascunho, sem comprovar contato.

O Kanban carrega até oito cards por coluna inicialmente, com contagem total filtrada e Carregar mais por coluna. Há busca por empresa sem distinção de acentos/caixa e filtro de nicho, contagem real, seleção de destino por teclado e drag-and-drop nativo de mouse. Em telas pequenas a rolagem horizontal pertence ao quadro, não à página. O seletor permite alcançar etapas fora da área visível sem arraste. A movimentação visual é otimista, com rollback e aviso em falha; respostas antigas de leitura não substituem uma movimentação em andamento. Dados são recarregados após confirmação.

## Escrita, concorrência e backup

`backend/crm` usa a **mesma instância `SelectionStore`** que prospecção e SDR: flag, lock, `mode=rw`, `BEGIN IMMEDIATE`, backup SQLite validado antes da primeira mutação por processo e commit único. Conexões de consulta são `mode=ro`, com snapshot e `query_only`. Não cria base ausente, tabelas ou colunas na importação/inicialização da API.

Toda mutação recebe `revision`, um SHA-256 do registro atual completo. Dentro da transação, compara novamente com o lead no banco. Uma alteração feita por outra tela, aba, SDR ou desktop gera HTTP 409 e exige atualização antes de repetir. Isso protege status e retornos contra perda de edição, mesmo que um escritor desktop reutilize a resolução do timestamp. A alteração do lead e a inserção da atividade são atômicas: se o histórico falha, status/campos/timestamp voltam ao estado anterior. Repetir uma requisição já confirmada com a revisão antiga não duplica o evento; retorna conflito. Na dúvida após falha de transporte, consultar o perfil/histórico antes de tentar de novo.

Flag desabilitada retorna 403; schema incompleto desabilita a edição e explica a incompatibilidade. Inputs são validados por Pydantic no FastAPI e Zod no BFF; descrições até 4000 caracteres, próxima ação até 240, nomes de etapa até 200, IDs positivos, filtros e paginação limitados. Datas novas precisam de fuso explícito e são convertidas para UTC. O BFF tem destinos fixos, timeout, `no-store`, valida origem local e não encaminha cookies/segredos. Erros não expõem SQL, caminhos ou conteúdo de exceções. Não foram adicionadas dependências.

## Histórico e observações

Reutilizada `lead_interactions` através de `InteractionRepository._insert`, sem instanciar seu construtor. Novos eventos têm tipo `CRM · ...` e são identificados como manuais. Os registros desktop anteriores permanecem íntegros e aparecem como registros existentes, sem atribuir uma origem que a base não comprova.

A linha do tempo combina, com paginação de 20 registros:

- Data de criação que já existe na ficha.
- Observações atuais da coluna legada `observacoes`, sem apagá-las.
- Interações do desktop e eventos CRM.
- Abordagens salvas em `outreach` e versões arquivadas em `outreach_revisions`.

Uma nova observação é **acrescentada ao histórico**, sem sobrescrever o texto antigo da ficha. Alterações de etapa incluem os dois valores; retornos incluem ação/data anteriores e novos. A última atividade considera interações e rascunhos salvos. Ordenação das atividades interpreta os offsets ISO com `julianday`, com desempate estável; datas inválidas da origem ficam sinalizadas na interface.

Contato realizado, resposta recebida, reunião agendada e proposta enviada exigem descrição e confirmação explícita de que ocorreram. Contato confirmado preenche `ultimo_contato` no instante UTC do registro; o operador pode explicar data anterior na descrição. Nenhum desses eventos muda etapa automaticamente. Gerar/copiar/abrir WhatsApp não cria contato, resposta ou conversão. Concluir um follow-up também não comprova contato. Leads bloqueados não recebem novas ações de contato pela API; os campos de recusa/revogação não são limpos por mudança de etapa.

O perfil mostra empresa, nicho, telefone, site, localização, etapa original, última atividade, último contato, retorno, observações e timeline. Permite gerar no SDR com o lead já selecionado por `?leadId=`, além de revisar/copiar uma abordagem salva ou texto manual e abrir o WhatsApp pelo link seguro existente. A edição desse texto é local; persistência e aprovação continuam no SDR. Há aviso de saída para formulários/textos não salvos; atualizações bem-sucedidas de um formulário preservam os outros. O histórico e os dados podem ser atualizados explicitamente em caso de conflito.

## Follow-ups e Meu Dia

Reutilizados `leads.proximo_contato` e `proxima_acao`. O modelo mantém **um próximo retorno pendente por lead**, como no desktop, em vez de criar uma agenda concorrente que o desktop não enxergaria. Nos endpoints de retorno, o ID é o próprio ID do lead, não uma nova entidade em tabela separada.

Agendar/reagendar atualiza esses dois campos e arquiva a situação anterior no histórico. Data e horário podem ficar vazios se houver uma descrição da próxima ação. Concluir limpa somente o ponteiro de próximo retorno e registra a conclusão; preserva histórico, observações, etapa e último contato. Uma revisão desatualizada impede concluir ou sobrescrever um retorno reagendado por outra tela. Para múltiplos compromissos independentes por lead, uma próxima fase precisará de modelo e migration explícitos; não foram introduzidos nesta entrega.

`core.commercial.day.build_day` continua sendo a única regra da seleção Meu Dia: atrasados, hoje, novos, reuniões e propostas; união deduplicada e ordenação por prioridade/data/score. Atraso significa data local anterior ao dia de referência, não apenas horário anterior de hoje. Etapas encerradas são excluídas apenas de atrasados, preservando a regra existente de hoje. Há também visualização Todos os retornos pendentes, incluindo futuros e ações sem data. Datas legadas inválidas não são corrigidas silenciosamente e recebem aviso.

O navegador informa seu fuso IANA; a API usa `ZoneInfo` e armazena novas datas em UTC. Campos `datetime-local` são convertidos no navegador, e a exibição usa o fuso local. O endpoint de overview existente agora aceita `tz` opcional, mantendo o comportamento anterior quando omitido e alinhando os indicadores antigos do Dashboard ao mesmo dia local do Meu Dia.

## Indicadores e significado

| Indicador | Fonte real, sem inferência de envio |
| --- | --- |
| Total | Registros existentes em leads |
| Contato registrado | Leads distintos com evento CRM de contato/Primeiro contato desktop, `ultimo_contato` válido ou status explícito Contatado/Contato realizado, inclusive valor anterior preservado em movimentação CRM |
| Resposta confirmada | Leads distintos com evento CRM de resposta ou status legado literal Respondeu, inclusive valor anterior preservado em movimentação CRM |
| Conversas / propostas | Etapa atual Em conversa, Interessado ou Proposta enviada |
| Convertidos | Etapa atual Fechado |
| Retornos pendentes | Leads com próximo contato ou próxima ação |
| Retornos atrasados | Contagem `atrasados` do `build_day` no fuso informado |

São métricas com definições diferentes, não fatias somáveis do mesmo funil. Dentro de cada métrica o lead é contado uma vez. Sem campos/tabelas suficientes retorna `null` e a interface mostra “—”, não zero inventado. Uma categoria pode ter zero registros confirmados sem comprovar ausência de contatos históricos fora da base. Rascunhos gerados, copiados ou abertos não contam como contato/resposta.

## Endpoints

FastAPI usa `/v1`; o BFF publica as rotas correspondentes sob `/api`.

| Método e rota FastAPI | Uso |
| --- | --- |
| `GET /v1/pipeline?q=&niche=&stage=&offset=0&limit=8` | Colunas, totais, cards e capacidade de edição |
| `GET /v1/crm/leads/{id}` | Perfil, etapas disponíveis, revisão; BFF `GET /api/leads/{id}` |
| `PATCH /v1/leads/{id}/stage` | `{revision,stage,confirmed}`; confirmação obrigatória para contato/conversão/perda |
| `GET /v1/leads/{id}/activities?offset=0&limit=20` | Timeline paginada |
| `POST /v1/leads/{id}/activities` | `{revision,kind,description,confirmed,channel}` |
| `GET /v1/followups?scope=day|pending&tz=America/Sao_Paulo&offset=0&limit=20` | Meu Dia e retornos pendentes |
| `POST /v1/leads/{id}/followups` | `{revision,action:"schedule",dueAt,note}` |
| `PATCH /v1/followups/{id}` | `{revision,action:"complete"}` ou reagendamento `schedule` |
| `GET /v1/dashboard/commercial?tz=...` | Métricas comerciais reais |
| `GET /v1/overview?tz=...` | Consulta existente, com fuso opcional compatível |

`dueAt` é ISO com offset ou `null`. `kind`: Observação, Contato realizado, Resposta recebida, Reunião agendada ou Proposta enviada. Nenhum endpoint de listagem existente foi duplicado ou removido; os paths de perfil enriquecido são separados no FastAPI para preservar `/v1/leads/{id}` e seus consumidores.

## Schema e ativação segura

**Sem alterações de schema e sem migrations propostas/aplicadas.** Reutilizados status, campos comerciais, interações e histórico SDR já existentes. Schemas antigos incompletos permitem as consultas compatíveis e exibem a limitação de escrita/agenda. Não chamar `initialize_database` via API para “corrigir” a base.

1. Criar uma cópia validada da base desejada e testar nela primeiro.
2. No terminal backend, definir o caminho da cópia e habilitar escrita explicitamente.
3. Iniciar a API em loopback; o primeiro salvamento cria/valida backup com a proteção já existente.
4. Somente após revisão do resultado, o operador pode decidir apontar o processo para sua base de trabalho. Esta implementação não habilitou escrita nem aplicou qualquer alteração na base original.

```powershell
# Na raiz; use uma cópia existente, não o banco original para validar.
$env:LOUNG_DATABASE_PATH='C:\caminho\copia-validada.db'
$env:LOUNG_ENABLE_WRITES='1'
backend/.venv/Scripts/python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Sem as variáveis acima, a API usa a base configurada/padrão e mantém escrita desabilitada. Não editar `.env`. Para desligar escrita, remover a variável do terminal e reiniciar a API. Em outro terminal: `cd web`, `npm run dev`; abrir `/pipeline`, `/leads`, `/meu-dia`. A API e o frontend devem permanecer locais enquanto não houver autenticação/isolamento por organização.

## Validação

```powershell
$env:PYTHONPATH='.'
backend/.venv/Scripts/python.exe backend/scripts/run_offline_tests.py backend/tests -q --basetemp=backend/.phase24-all-tests
backend/.venv/Scripts/python.exe backend/scripts/check_crm_database_copy.py
.venv/Scripts/python.exe backend/scripts/run_offline_tests.py tests/test_commercial.py tests/test_database.py tests/test_priority_ux.py -q --basetemp=backend/.phase24-desktop-tests
cd web
npm run lint
npm run typecheck
npm run build
```

Os testes CRM cobrem aliases/customizados, leitura sem escrita, paginação, destinos inválidos, atividades e confirmação, notas anteriores preservadas, simultaneidade, retornos sem data, offset UTC, reagendamento/conclusão, revisão antiga, indicadores distintos, timezone e schema legado sem migração. Trigger de falha verifica rollback de status/timestamp/histórico. A regressão inclui API, prospecção e SDR, com rede externa bloqueada pelo runner. O teste de cópia da base existente verifica 217 leads, todas as tabelas/linhas anteriores, schema idêntico e backup íntegro. A base original é aberta apenas em `mode=ro` e tem checksum comparado antes/depois.

Resultados: 95 testes de backend e 72 testes existentes do desktop aprovados; lint, TypeScript e build aprovados. O TestClient emite apenas o aviso conhecido de depreciação Starlette/httpx. Não foram executadas chamadas reais Google, Groq ou WhatsApp.

Para validar no navegador sem dados reais:

```powershell
# Raiz, terminal 1
$env:PYTHONPATH='.'
backend/.venv/Scripts/python.exe -m uvicorn backend.tests.crm_fixture_server:create_app --factory --host 127.0.0.1 --port 8100
# web, terminal 2 (após npm run build)
$env:LOUNG_API_URL='http://127.0.0.1:8100'
npm run start -- --port 3100
# Raiz, terminal 3
.venv/Scripts/python.exe web/scripts/check_crm.py
.venv/Scripts/python.exe web/scripts/check_ui.py http://127.0.0.1:3100
```

A fixture cria banco sintético temporário em pasta ignorada; seus endpoints `__test/*` existem exclusivamente nessa factory de teste. O script confere a assinatura antes de agir. Destinos externos são bloqueados no browser. Fluxo validado: carregar mais, filtros, seletor por teclado, drag-and-drop, conflito/rollback, perfil e observação, confirmação de contato, preservação de edição entre formulários, retorno/reagendamento/conclusão, deep link SDR, Meu Dia e indicadores. Capturas em `backend/.phase24-visual/`, com Kanban em 1440/1024/390 px e perfil/Meu Dia no mobile.

A navegação geral foi validada nas sete páginas em três resoluções, sem erros JavaScript nem requisições externas. A comparação SHA-256 de 236 arquivos fora de `/web` e `/backend` não encontrou alterações, incluindo desktop, `.env`, providers e banco original. Observações legadas não recebem uma data presumida; datas sem offset são exibidas como registros sem fuso informado.

## Arquivos

- API: `backend/crm/{__init__,models,routes,service}.py`; ajustes em `backend/main.py`, `repository.py` e `.gitignore`.
- Testes: `backend/tests/test_crm_api.py`, `crm_fixture_server.py`, `backend/scripts/check_crm_database_copy.py`, `web/scripts/check_crm.py` e atualização da navegação geral de teste.
- Contratos/BFF: `web/src/lib/api/crm-contracts.ts`, `crm-proxy.ts`, handlers de pipeline, perfil, atividades, etapa, follow-ups e métricas; `proxy.ts` encaminha o fuso do overview.
- UI: `/pipeline`, `/leads/[id]`, `/meu-dia`; componentes em `src/components/crm/`; links na carteira, navegação e Dashboard; SDR aceita seleção via parâmetro. Avisos e documentação atualizados.

## Limites

Uma próxima ação pendente por lead; não há agenda com múltiplos compromissos, recorrência ou notificações. Atividades confirmadas registram o instante de inclusão, com eventual data anterior explicada na descrição. Colunas personalizadas são preservadas, mas não há editor para criar novas etapas. Não há agregação de receita, estimativas de conversão ou dados fictícios.

Não existe sincronização em tempo real entre abas/processos; usar Atualizar quando necessário. A revisão transacional impede sobrescrita silenciosa. Paginação por offset pode exigir atualização se outro operador mover itens entre páginas durante a consulta. Histórico SPA Voltar/Avançar não tem proteção universal de formulário; salvar/copiar antes de sair. Os limites locais das fases anteriores continuam válidos, incluindo ausência de autenticação e rascunhos SDR temporários. Próxima etapa: autenticação/organização, contratos de permissões e sincronização antes de expor em rede.
