# Dashboard: investigação React e desempenho — 22/10/2026

## Resultado e limites

Foram corrigidas requisições RSC concorrentes no login e a resposta tardia do
SessionGate após desmontagem. Também foram reduzidos os acessos redundantes ao
PostgreSQL. **A causa exata do aviso React informado ainda não foi confirmada**:
o cenário isolado com Webpack passou antes da alteração. Não atribuir o aviso à
corrida corrigida sem a pilha do erro original.

Nenhum dado de negócio foi lido pela sondagem PostgreSQL, nem alterado. Ela usou
loung_web, SET LOCAL ROLE loung_api e BEGIN READ ONLY/ROLLBACK, consultando apenas
information_schema. Nenhuma migration, credencial, flag de escrita, política,
grant ou configuração real foi alterada.

## React, componentes e bibliotecas

- Next 16.4.2; react/react-dom 19.3.1, com o renderer React empacotado pelo Next.
- RootLayout → SessionGate → AppShell → Dashboard. SessionGate, AppShell e Sidebar
  usam usePathname; AuthForm usa useRouter e useSyncExternalStore. Os hooks de dados
  usam useEffect/fetch/AbortController. Não há use(promise) nem Suspense explícito
  no código da aplicação. DashboardData usa ActivityChart/Recharts; AppShell usa
  Radix Dialog. Não foi identificada chamada suspensiva nessas bibliotecas.
- A mensagem é criada em next/dist/compiled/react-dom/cjs/react-dom-client.development.js,
  em trackUsedThenable; finishRenderingHooks a emite quando a fibra que suspendeu
  termina sem consumir um thenable. Isso identifica o detector, não o componente
  culpado no incidente original.
- O Next chama use() em InnerLayoutRouter para conteúdo RSC adiado e em
  usePathname no ramo de instrumentação de desenvolvimento, com
  NavigationPromisesContext. Suas boundaries de loading/Suspense são internas.
- A aplicação disparava replace('/') e refresh() imediatamente após autenticar.
  A reprodução registrou dois GET / consecutivos. Agora há apenas replace; ele
  já inicia a navegação. Removido o refresh concorrente também no redirecionamento
  por 401. SessionGate aborta fetch no cleanup e ignora respostas tardias.
- Strict Mode permanece ativo por padrão no App Router. Em desenvolvimento ele
  repete montagem/cleanup dos efeitos; uma requisição cancelada pode já ter
  chegado ao servidor. Isso não prova um loop nem justifica desativá-lo.
  Durante compilação em dev também houve novas requisições RSC após HMR,
  mesmo sem refresh explícito. O teste de navegação única vale para produção;
  `check_dashboard_react.py --development` permite esse tráfego extra e mantém
  as verificações de erros, sessão, gráficos e navegação.
- Webpack/dev reproduziu login, Dashboard, Leads, Pipeline e reload sem o aviso,
  antes da correção. Turbopack não concluiu a compilação na cópia de QA: inicialmente
  a junction de node_modules estava fora da raiz; ajustar a raiz apenas na cópia
  resolveu o erro de resolução, mas a compilação ficou pendente e foi encerrada.
  Não foi alterado o bundler padrão do projeto.

Para concluir a investigação React, é necessária a pilha do aviso no cenário em
que ele ocorre (componentes/arquivos, sem cookies, tokens ou cabeçalhos privados).
Não foi atualizada biblioteca nem adicionada boundary arbitrária sem essa evidência.

## Evidências de desempenho

Três amostras na conexão restrita real, exclusivamente de metadados:

| Operação | Faixa observada |
| --- | --- |
| Conectar ao PostgreSQL | 1.015–1.259 ms |
| Seis consultas sequenciais de metadados | 1.210–1.995 ms |
| Mesmos metadados agrupados | 178–195 ms |

Dados em artifacts/qa/dashboard-20261022/db-readonly-baseline.json. A consulta
agrupada foi executada depois das seis consultas, portanto cache aquecido pode
influenciar a comparação. A redução de seis round trips para um é determinística;
as faixas não são promessa de latência final.

Uma segunda execução em db-readonly-equivalence.json confirmou igualdade de
colunas e ordem entre a consulta antiga e a agrupada, com a mesma role restrita.

Antes, cada Connection consultava separadamente seis tabelas. Agora usa ANY(%s),
com lista fixa de tabelas, preservando ordinal_position, tabelas ausentes e a
checagem de membership antes dos metadados. Não há cache global de autorização
ou metadados e nenhuma mudança no contexto transacional do RLS.

Commercial metrics abria uma segunda conexão e relia leads ao chamar followups
para obter apenas contagens, incluindo renderização de um card e sua consulta
de última atividade. Agora calcula essas contagens com build_day sobre os mesmos
leads/snapshot autorizado. A equivalência é testada, inclusive datas inválidas.

Outros custos identificados, preservados nesta alteração:

- Cada requisição BFF verifica Supabase getUser no proxy e novamente no BFF;
  getSession só fornece o token depois da verificação. FastAPI valida JWT e
  memberships; cada transação revalida membership. Não foram removidas fronteiras
  de segurança nem substituída a validação por leitura de cookies.
- Dashboard aguarda /api/session antes de montar as três seções. Depois elas
  carregam em paralelo via efeitos independentes. Não é uma cadeia entre
  overview, followups e commercial.
- Followups consulta última atividade por card, até o limite de paginação. Isso
  é um N+1 identificado no código, ainda não otimizado por falta de medição
  específica das consultas de negócio.
- Cada operação abre conexão nova; o custo medido de conexão continua existindo.
  Não foi introduzido pool sem testes de reset de identidade/organização/RLS.
- Em QA/dev houve compilação inicial de login de 44 s e de /api/session de 15 s.
  Esses tempos pertencem à cópia de teste e não medem a instalação original.

## Medir separadamente, sem logs sensíveis

As respostas das quatro rotas têm Server-Timing:

- bff_auth: getUser/getSession no BFF.
- bff_upstream: espera de fetch até os cabeçalhos do FastAPI, incluindo transporte.
- api_jwt: validação JWT/JWKS; api_membership: seleção autorizada da organização.
- api_db_connect: estabelecimento de conexões; api_db_open inclui connect e
  configuração transacional de role/claims.
- api_db_metadata: consulta agrupada de metadados; api_db_query: operações do
  adaptador (não inclui as consultas de setup/membership).
- api_handler: endpoint, fila do threadpool e serialização inicial.
- api_fastapi: processamento da requisição no backend até os cabeçalhos.

X-Loung-Proxy-Auth-Ms mede a autenticação do proxy separadamente do BFF.
Os tempos são aninhados: **não somar todas as métricas**. db_connect está contido
em db_open; membership e handler incluem seus respectivos acessos ao banco.
A diferença entre bff_upstream e api_fastapi aproxima transporte/fila até
cabeçalhos; o restante do total Next inclui compilação, roteamento e serialização.
Falhas anteriores ao fetch podem não ter as métricas do BFF. Somente nomes fixos
e valores numéricos são encaminhados; nenhum SQL, UUID, token ou parâmetro.

Para medir o caso real após reiniciar os serviços com este código, no Network
do navegador autenticado registrar duração total e Response Headers das quatro
rotas, distinguindo primeira compilação, repetição aquecida e produção. Não usar
HAR contendo cookies ou Authorization. Os tempos históricos de 6–11,5 s não
permitem atribuição exata por camada retroativamente. Não foi utilizado JWT real
para reproduzir esses requests nesta sessão.

## Validação reproduzível

Teste de banco sem dados de negócio (somente leitura):

```powershell
backend/.venv/Scripts/python.exe -m backend.scripts.profile_dashboard_db --env-file .env
```

Regressão sintética:

```powershell
backend/.venv/Scripts/python.exe -m pytest backend/tests -q --basetemp=temp/dashboard-tests -o cache_dir=temp/dashboard-cache --ignore=backend/tests/test_phase31_postgres.py --ignore=backend/tests/test_phase32_team.py --ignore=backend/tests/test_phase32_writes.py --ignore=backend/tests/test_auth_schema_acl.py --ignore=backend/tests/test_stamp_claims_migration.py
cd web
node --use-system-ca --test --test-isolation=none scripts/auth.test.mjs scripts/team.test.mjs
npm.cmd run typecheck
npm.cmd run lint
```

check_dashboard_react.py exige a fixture auth-session-no-database em 8112 e uma
cópia Next sem .env, apontando exclusivamente para ela em 3198. Cobre navegação,
reload, métricas, 503 sem logout e 401 com redirecionamento, capturando pageerror
e mensagens de suspensão/hidratação. check_auth_session.py cobre login inválido,
cookies, logout e indisponibilidade. O build usa a mesma cópia isolada com
`npm.cmd run build -- --webpack`; não interrompe o servidor real.

Referências: [React use](https://react.dev/reference/react/use),
[Next useRouter](https://nextjs.org/docs/app/api-reference/functions/use-router),
[Next Strict Mode](https://nextjs.org/docs/app/api-reference/config/next-config-js/reactStrictMode).
As instruções locais da versão instalada em node_modules/next/dist/docs também
foram consultadas antes das alterações.

Resultado da regressão local: 126 testes backend passaram, excluindo explicitamente
test_phase31_postgres.py, test_phase32_team.py, test_phase32_writes.py,
test_auth_schema_acl.py e test_stamp_claims_migration.py, que dependem do PostgreSQL
isolado não iniciado nesta sessão. A tentativa de suite completa foi interrompida
ao aguardar esse serviço ausente. Não é uma aprovação dos testes RLS de integração.
Os 13 testes Node passaram; TypeScript, lint e build Webpack passaram.
O warning de depreciação Starlette/httpx já existente não impediu os testes.
QA no Edge contra produção passou: uma navegação RSC após login; gráfico
Recharts com dados sintéticos; diálogo Radix; Dashboard/Leads/Pipeline/reload;
cabeçalhos de tempo; 503 sem redirecionamento e 401 com redirecionamento.
Também passou o roteiro de login inválido, cookies por host, logout e falhas
Auth/API. Evidências browser-dashboard.txt e browser-auth.txt no diretório QA.
A repetição final em dev/Webpack não concluiu: após a primeira tentativa exigir
indevidamente uma única requisição RSC durante HMR, o roteiro foi ajustado com
`--development`; a segunda tentativa excedeu 90 s compilando login. Essa execução
não está aprovada. O teste dev inicial passou antes das alterações, sem gráfico
preenchido; a cobertura final de Recharts/Radix foi aprovada em produção.
Os servidores sintéticos iniciados para a tarefa foram encerrados.

Arquivos desta correção: components/auth-form.tsx e session-provider.tsx;
proxy.ts; lib/api/dashboard-timing.ts, proxy.ts e crm-proxy.ts;
app/api/session/route.ts; backend/crm/service.py; backend/persistence/postgres.py,
session_queries.py, runtime.py e timing.py; scripts/auth.test.mjs e
check_dashboard_react.py; backend/tests/test_dashboard_performance.py;
backend/scripts/profile_dashboard_db.py; este relatório e os resultados em
artifacts/qa/dashboard-20261022. A fixture backend/tests/auth_session_fixture.py
agora inclui contagens sintéticas para exercitar o gráfico. O repositório já tinha outras alterações antes
desta tarefa, que foram preservadas.
