# Prospecção: pesquisa concluída sem lista — 22/10/2026

## Causa e evidências

Foram encontrados dois defeitos na entrega dos resultados:

1. **Deduplicação sequencial no PostgreSQL.** JobManager.results chamava
   PgStore.existing, que herdava SelectionStore.existing. Para cada candidato,
   find_existing podia fazer quatro SELECTs: provider/place_id, Google Maps,
   empresa/endereço e empresa/telefone. Uma página de 20 candidatos novos gerou
   **80 SELECTs** na reprodução. O BFF limita results a 10 segundos. As medições
   anteriores de conexão/metadados já mostravam latência de rede relevante; 80
   round trips podem exceder esse limite mesmo com a pesquisa concluída.
2. **Cancelamento pelo polling.** O efeito que buscava results dependia do objeto
   current. Cada resposta do status criava outro objeto, a cada 1,5 s, disparando
   cleanup/abort de results, mesmo sem mudança nos resultados. Respostas mais
   lentas que esse intervalo eram canceladas enquanto o job continuava ativo.

O usuário informou pesquisa de padaria em São Paulo com estado Concluída, mas
não havia mais o contador nem a resposta original para inspeção. Portanto não
se afirma ter capturado um 503 específico daquele incidente. Os defeitos acima
foram identificados no código e cobertos por regressão isolada.

Uma chamada real, limitada a **uma requisição e um estabelecimento**, usando o
provider existente e a configuração local, retornou um candidato para padaria
em São Paulo. Ela não abriu banco, não persistiu resultado e não imprimiu dados
do estabelecimento ou chave. Isso confirmou que a chave/endpoint/field mask
funcionavam nessa sondagem; não comprova o ambiente do processo FastAPI já em
execução nem quotas futuras. Evidência: google-probe.json no diretório QA.

## Fluxo verificado e correção

Formulário ProspectingWorkspace → POST /api/prospecting/search → BFF com bearer
verificado → POST /v1/prospecting/search → JobManager/PgJobManager → Google Places
Text Search New → qualificação e staging temporário → GET status → GET results
com paginação e alreadySaved → seleção → POST /api/leads/import → importação
transacional e confirmação inserted/duplicates. HTTP 202 só aceita o job;
status completed e a carga de results são verificados separadamente.

- PgStore.existing agora usa uma consulta fixa com jsonb_to_recordset e EXISTS,
  recebendo valores por parâmetros. Preserva as quatro identidades exatas,
  inclusive pares incompletos, nulos, strings vazias, espaços e ordem da página.
  Mantém connection() com revalidação de membership, role restrita, contexto JWT
  transacional e RLS. existing([]) conserva o preflight de autorização do início
  da pesquisa. A deduplicação transacional antes de importar não foi removida.
- results faz uma requisição por vez. Atualizações de status não a cancelam.
  Só trocar pesquisa/página, solicitar retry ou desmontar cancela o fetch. Se a
  requisição começou durante execução, há nova leitura após ela terminar para
  obter o resultado final. Falhas têm tentativas limitadas e retry explícito.
- A interface distingue carregamento, erro de carga e uma pesquisa concluída
  realmente vazia. Seleção/importação continuam explícitas; não há autoimport.
- O BFF preserva autenticação, origem local, validação JSON, IDs, paginação,
  timeout e caminhos fixos. Timeout de results agora tem mensagem específica.
- Falhas Places 400/401/403/429, configuração, transporte e limites recebem
  mensagens fixas apropriadas, sem repassar texto externo. A quota/faturamento
  não é tratada como busca vazia. Resultados parciais são preservados.
- PgJobManager mantém snapshot durável inicial/final; novos metadados de falha
  são opcionais no JSON existente, compatíveis com snapshots antigos. Nenhuma
  alteração de schema ou migration foi necessária.

## Observabilidade

Eventos JSON no logger já configurado pelo Uvicorn: search.running,
search.finished, search.results, search.imported e search.persistence_failed.
Campos: search_id, status, found, duplicates, failure_type, duration_ms;
finalização inclui scanned/requests/pages; results inclui page, page_duplicates
e available; importação inclui inserted/import_duplicates.

duplicates conta repetições internas da pesquisa; page_duplicates conta os
resultados da página já existentes na organização. available é da página,
não um total global inventado. duration_ms é o tempo decorrido desde a criação
do job nesta execução, não somente o tempo do Google. Não são registrados
consulta textual, estabelecimentos, telefone, endereço, chave, token ou DSN.

## Testes

Resultado final: **143 testes backend e 16 testes Node aprovados**, TypeScript,
lint e build Webpack aprovados; roteiro de navegador autenticado aprovado, sem
erros JavaScript. Evidências em artifacts/qa/prospecting-fix-20261022:
backend.xml, browser-report.json, browser.txt e google-probe.json.

- PostgreSQL **em memória (PGlite)**, porta fixa 55432, com marcador obrigatório,
  role sem BYPASSRLS e dados sintéticos: 20 resultados consultados em uma query;
  reprodução antiga de 80 consultas; quatro identidades; ordem; casos vazios e
  inválidos; organizações distintas e usuário sem membership da organização.
  O script cria apenas o schema mínimo da fixture, sem carregar migrations.
- Backend offline: Google mock com resultados, paginação, vazio, 401/403/429,
  andamento, conclusão, falha, cancelamento, parciais, importação selecionada,
  duplicidade, rollback e mensagens/logs sem segredos. A regressão ampliada
  inclui JWT/autorização e as demais funcionalidades locais.
- Node/BFF: aceitação 202, resultados, bearer, paginação, timeout versus vazio,
  sessão expirada, rejeição de origem externa e escalonamento por organizationId.
- Browser: Next compilado, Supabase Auth sintético, cookies e JWT verificado no
  FastAPI da fixture, Google mock e SQLite temporário. Cobre seleção entre
  páginas, importação de dois selecionados, repetição sem inserir duplicado,
  Carteira, retomada, exportação, três viewports, cancelamento e erro sanitizado.
  No caso lento, results demora 2,2 s e a segunda página Google fica bloqueada
  por 8 s: a tabela deve mostrar os novos resultados ainda em Pesquisando.
  Uma busca vazia deve concluir com Nenhum estabelecimento encontrado.
- TypeScript, lint e build Webpack na cópia sem .env real.

As suítes que exigem o antigo cluster PostgreSQL completo em 55431 ficaram
excluídas. O teste PostgreSQL desta alteração exercita a consulta nova e um
modelo RLS mínimo; não é uma nova homologação de todas as policies de produção.
Nenhum servidor real foi reiniciado nem usuário/credencial alterado.
Os processos de QA iniciados para esta tarefa foram encerrados após os testes.

Reprodução de testes:

```powershell
# Terminal 1, a partir de web:
node scripts/prospecting-postgres.mjs
# Terminal 2, na raiz; acesso externo bloqueado pelo runner:
backend/.venv/Scripts/python.exe -m backend.scripts.run_offline_tests backend/tests/test_prospecting_batch.py backend/tests/test_prospecting_api.py -q --basetemp=temp/prospecting-qa -o cache_dir=temp/prospecting-cache
# Na pasta web:
node --use-system-ca --test --test-isolation=none scripts/auth.test.mjs scripts/team.test.mjs scripts/prospecting.test.mjs
npm.cmd run typecheck
npm.cmd run lint
```

QA de interface exige Auth sintético em 8112, create_authenticated_app de
backend.tests.prospecting_fixture_server em 8100 e cópia Next em 3198 sem .env,
apontando apenas para essas fixtures. Não usar o banco real nesse roteiro:

```powershell
.venv/Scripts/python.exe web/scripts/check_prospecting.py http://127.0.0.1:3198 http://127.0.0.1:8100 --auth
```

## Validação manual local

1. Reiniciar Next e FastAPI com os comandos/arquivo de ambiente já usados pelo
   projeto para carregar este código. Preservar credenciais e o valor atual de
   LOUNG_ENABLE_WRITES; não mudar flags como parte desta correção.
2. Entrar como owner e abrir Prospecção. Pesquisar nicho **padaria**, localização
   **São Paulo, SP**, quantidade **5**, inicialmente sem filtro de site/score.
3. Verificar progresso e depois lista. No Network, distinguir POST 202, GET
   status completed e GET results 200 com items/total/page/pageSize. Não exportar
   HAR contendo tokens/cookies. Se houver erro, copiar apenas status, mensagem
   segura e search_id dos logs.
4. Conferir a marcação de já existente e os checkboxes correspondentes. Marcar
   resultados deve alterar apenas a seleção, sem gravação na Carteira.
5. Para homologação de escrita, usar a fixture isolada: selecionar dois itens
   entre páginas, salvar e conferir inserted=2; repetir a mesma seleção deve
   produzir inserted=0 e duplicates correspondente. Não testar gravação sobre
   os 160 leads reais. Em uso normal a importação permanece uma decisão manual
   do operador após revisar os resultados.
6. Se completed vier com found=0 e results.total=0, confirmar mensagem de vazio e
   revisar filtros. Se found>0 e results falhar, usar retry e consultar logs de
   results. Se failed, seguir a mensagem específica de configuração/quota/acesso.

Não foi identificada configuração externa pendente na sondagem Places. Se o
processo ativo tiver variáveis diferentes do .env, isso precisa ser corrigido no
comando de inicialização pelo operador, sem divulgar ou trocar chaves. A API
correta continua sendo [Text Search New](https://developers.google.com/maps/documentation/places/web-service/text-search).

## Arquivos desta tarefa

Produção: backend/persistence/postgres.py, backend/persistence/searches.py,
backend/prospecting/jobs.py, web/src/components/prospecting-workspace.tsx e
web/src/lib/api/prospecting-proxy.ts.

Testes: backend/tests/test_prospecting_api.py, backend/tests/test_prospecting_batch.py,
backend/tests/prospecting_fixture_server.py, web/scripts/check_prospecting.py,
web/scripts/prospecting.test.mjs e web/scripts/prospecting-postgres.mjs.
Relatório: este arquivo e artifacts/qa/prospecting-fix-20261022.
Alterações anteriores existentes no workspace foram preservadas; não há commit.
