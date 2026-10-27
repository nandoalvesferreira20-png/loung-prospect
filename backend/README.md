O padrão atual é SQLite local sem login. Veja [execução local](../docs/local/README.md). As seções abaixo preservam o histórico das fases anteriores. Para o modo SaaS, veja [diagnóstico de autenticação](../web/docs/post-login-access.md).

# Loung Prospect API — Fase 2.4

CRM disponível: pipeline, atividades, perfil comercial, follow-ups e indicadores.
Reutiliza schema/status/Meu Dia desktop, sem migrações. Alterações exigem revisão
do registro e `LOUNG_ENABLE_WRITES=1`, com backup e transação. Consulte
[Fase 2.4](../web/docs/phase-2-4.md) para endpoints, testes e ativação segura.

Backend FastAPI local com leitura de leads, prospecção Google Places e geração SDR pela integração Groq existente. Não importa a interface desktop nem inicializa/migra SQLite. Importação e salvamento explícito de mensagens revisadas exigem `LOUNG_ENABLE_WRITES=1`, com backup antes da primeira escrita. Gerar não grava; WhatsApp abre pelo navegador após revisão humana, sem envio automático.

Veja [Fase 2.3](../web/docs/phase-2-3.md) para os endpoints SDR, configuração Groq, histórico, validação offline e limites. A chave/modelo existentes são carregados no servidor somente ao gerar, pelo helper do desktop. Nenhum segredo vai para o navegador.

Veja [o relatório da Fase 2.2](../web/docs/phase-2-2.md) para endpoints de jobs, limites, escrita, exportação e testes. A descrição dos endpoints de leitura abaixo continua válida.

## Executar

A partir da raiz do repositório, com Python 3.10 ou superior:

```powershell
python -m venv backend/.venv
backend/.venv/Scripts/python.exe -m pip install -r backend/requirements.txt
backend/.venv/Scripts/python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Em outro terminal:

```powershell
cd web
npm ci
npm run dev
```

Frontend: http://127.0.0.1:3000. OpenAPI: http://127.0.0.1:8000/docs. Não é necessário iniciar o desktop ou editar `.env`. A pesquisa usa `GOOGLE_PLACES_API_KEY` do ambiente ou o `.env` existente, carregado pelo helper desktop somente após uma ação explícita de pesquisa. A chave nunca é enviada ao navegador. O ambiente virtual é separado das dependências desktop.

Por padrão, usa `data/loung_prospect.db`, resolvido pela localização do repositório, independentemente do diretório atual. Para outra base, configure **somente no processo** antes de iniciar o backend:

```powershell
$env:LOUNG_DATABASE_PATH='C:\caminho\base.db'
```

Um caminho relativo é resolvido contra a raiz do repositório. A API não cria arquivos, pastas ou tabelas se a base não existir. Nesse caso, as consultas retornam HTTP 503 e a interface mostra o erro com opção de tentar novamente.

Se mudar a porta da API, configure `$env:LOUNG_API_URL='http://127.0.0.1:8001'` no terminal do Next.js antes de iniciá-lo. Essa configuração é exclusiva do servidor Next e aceita apenas destinos HTTP locais nesta fase. Nunca use `NEXT_PUBLIC_*` para credenciais. A configuração Google é carregada apenas no servidor ao pesquisar.

## Endpoints

| Método | Rota | Resultado |
| --- | --- | --- |
| GET | `/health` | Disponibilidade do processo e modo read-only; não testa o banco |
| GET | `/v1/leads?q=&stage=&page=1&pageSize=20` | Registros, total filtrado, paginação e opções de etapa |
| GET | `/v1/leads/{id}` | Lead mapeado; 404 quando inexistente |
| GET | `/v1/overview` | Total, agendamentos para hoje, atrasados, reuniões, distribuição por etapa e até oito próximas ações |

`page >= 1`, `1 <= pageSize <= 100`; consultas inválidas retornam 422. Ordenação estável por score decrescente e ID crescente, como no desktop. A busca ignora acentos, caixa e pontuação em empresa, telefone, segmento e cidade. Filtros são parametrizados; `%` não é um curinga. O filtro de etapa considera aliases legados e etapas personalizadas. Uma página além do total retorna lista vazia sem alterar o total.

O Next expõe as duas consultas de leitura e rotas explícitas de prospecção/importação descritas no relatório 2.2. O navegador não recebe o endereço interno como configuração pública. Não há proxy genérico nem CORS aberto. Respostas de dados usam `Cache-Control: no-store`.

## Dados e compatibilidade

`empresa → company`, `telefone → phone`, `segmento → niche`, `site → website`, `cidade → location`, `status → stage`, `qualification_score → score`, `proximo_contato → nextContact`, `proxima_acao → nextAction`.

`stage` é normalizado por `core.commercial.values.commercial_status`. `originalStage` preserva o valor armazenado, inclusive quando a API retorna `Reunião agendada` para `Reunião marcada`. Valores personalizados não são apagados nem convertidos para uma etapa padrão.

`contactRole` traduz `recepcao_equipe/contato_direto/indefinido` para o contrato web `reception/direct/unknown`. Preferências manuais em `lead_contact_preferences` prevalecem; sem elas, usa a classificação pura por nicho existente. Não cria preferências na leitura.

Colunas opcionais ausentes em schemas antigos produzem `null`; a ausência da tabela de preferências também é aceita. A tabela `leads` e as colunas `id`, `empresa`, `status` são obrigatórias. Uma base ausente, bloqueada, corrompida ou incompatível gera 503 sem expor caminhos internos. O adaptador não instancia `LeadRepository`, cujo construtor executaria migrações.

Indicadores reutilizam `core.commercial.day.build_day`: reuniões significam leads na etapa de reunião agendada (incluindo aliases), não eventos históricos; hoje/atrasados usam `proximo_contato` e o fuso local do processo, como no desktop. Etapas encerradas são excluídas de atrasados. Datas inválidas são contadas em `invalidDates`, sem inventar agendamentos. As próximas ações seguem a seleção do Meu Dia, incluindo novos leads e reuniões. A distribuição é uma fotografia atual, não uma série histórica.

## Testes sem dados reais

```powershell
backend/.venv/Scripts/python.exe -m pip install -r backend/requirements-dev.txt
backend/.venv/Scripts/python.exe -m pytest backend/tests -q --basetemp=backend/.test-tmp -o cache_dir=backend/.pytest_cache
```

Os testes criam bancos temporários. Para validar o caminho completo no navegador, inicie o servidor sintético **em vez da API real**:

```powershell
backend/.venv/Scripts/python.exe -m uvicorn backend.tests.fixture_server:create_app --factory --host 127.0.0.1 --port 8100 --no-access-log
```

Em outro terminal:

```powershell
cd web
$env:LOUNG_API_URL='http://127.0.0.1:8100'
npm run dev -- --port 3100
```

Na raiz, usando o Playwright Python já existente:

```powershell
.venv/Scripts/python.exe web/scripts/check_read_api.py http://127.0.0.1:3100
```

Essa fixture tem 24 registros com prefixo `Teste empresa`, separados da base real. O script verifica a assinatura da fixture antes de testar. Capturas e relatório ficam em `web/test-results/` e não são versionados. Encerre os servidores de teste antes de usar a configuração real.

No terminal usado para o Next, remova a configuração de teste antes de reiniciar com a API real: `Remove-Item Env:LOUNG_API_URL -ErrorAction SilentlyContinue`. Para testar o build de produção, execute `npm run build` e use `npm run start -- --port 3100` com a mesma variável de processo apontando para a fixture.

## Limites desta fase

Sem autenticação, multiempresa ou Supabase. A escrita é selecionada e desabilitada por padrão. Backend e frontend devem permanecer vinculados a `127.0.0.1`. Hosts externos e origens de navegador são rejeitados na API; o BFF rejeita acessos cross-site e não encaminha cookies ou credenciais. Essas medidas locais não substituem autenticação e autorização para publicação ou acesso em rede.

O dashboard lê os registros da carteira em um snapshot para reutilizar as regras existentes; essa consulta é adequada à fase interna. Para escala SaaS, evoluir para agregações/índices e autorização por organização antes de expor a API. Nenhum identificador de organização recebido do cliente é tratado como autorização.

Referências: [FastAPI — primeiros passos](https://fastapi.tiangolo.com/tutorial/first-steps/) e [testes](https://fastapi.tiangolo.com/tutorial/testing/).
