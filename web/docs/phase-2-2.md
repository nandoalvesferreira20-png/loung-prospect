# Fase 2.2 — Google Places na aplicação web

## Resultado e estado da gravação

Implementado o fluxo **pesquisar → acompanhar → revisar resultados → selecionar → salvar → consultar Carteira**, com cancelamento e exportação CSV/Excel. A aplicação usa o motor Python já existente; não há uma segunda integração Google Places.

**A gravação real permanece desabilitada por padrão.** Os testes foram aprovados, inclusive a escrita em uma cópia temporária da base de 197 leads. Para habilitar importação na base desejada, configure `LOUNG_ENABLE_WRITES=1` no processo FastAPI e reinicie-o. Não é necessário alterar `.env` nem aprovar outra integração/chave. Pesquisar não grava automaticamente; somente a ação explícita **Salvar selecionados** insere novos registros. O primeiro lote que insere algo cria e valida um backup antes de gravar.

Nenhuma pesquisa real Google foi executada nesta entrega. Nenhum teste utilizou a chave real ou gravou na base original. Os resultados das verificações e a comparação de integridade estão ao final deste documento.

## Auditoria e reaproveitamento

Antes das alterações foram lidos `architecture.md`, `phase-2-1.md`, os contratos/BFF, o schema e os caminhos de escrita SQLite, `core/prospecting/service.py`, os adapters/filtros/limites, o provider Google Places e as regras de normalização.

- **Google Places:** `core/providers/google_places.py` usa Places API New, `places:searchText`, field mask explícito, páginas de até 20, `nextPageToken`, limites de chamadas, sem retries/redirects/enriquecimento automático. O transporte é injetável para testes.
- **Configuração:** `core/providers/environment.load_environment()` reutiliza o `.env` existente sem sobrescrever o ambiente. É chamado apenas no worker de uma pesquisa iniciada explicitamente; a chave nunca vai para o navegador ou respostas HTTP. Testes fornecem chave sintética e transporte mockado.
- **Normalização:** `normalize_place` mantém telefone nacional/endereço formatado do provider; não inventa telefone, endereço ou estrutura da empresa. Nicho/localização vêm do contexto da pesquisa, com espaços externos removidos. Bairro utiliza `normalize_neighborhood`. A normalização internacional de WhatsApp permanece em `core/sales/contact.py`, sem ser aplicada indevidamente ao dado bruto da busca.
- **Motor e qualificação:** reutilizados `prospect`, `candidate_to_record`, `record_to_database`, `qualify_record`, as regras de presença digital, score e os limites existentes. O filtro sem site próprio também aceita presença apenas em redes sociais/plataformas, conforme a política já implementada; ausência de informação não é tratada como prova de ausência de site.
- **Deduplicação:** extraído `LeadRepository.find_existing(connection, data)` sem abrir banco ou migrar schema. A ordem exata permanece: provider + place ID; Maps URI; empresa + endereço; empresa + telefone. Componentes vazios não formam identidade. O método desktop original chama o mesmo helper.
- **Persistência:** reutilizado `LeadRepository._insert` dentro de transação controlada pelo backend. O construtor `LeadRepository`, `initialize_database` e os métodos que criam pastas/migram a base não são chamados pelo caminho web.

Dois arquivos compartilhados foram alterados deliberadamente: `core/prospecting/service.py` ganhou `stream_results=False`, opt-in para consumir o iterador cancelável e preservar páginas parciais; `core/database/lead_repository.py` centralizou a consulta de identidade. O comportamento padrão e os pontos de entrada desktop foram preservados e verificados pelos testes existentes.

## Arquitetura

```text
Prospecção / Next.js
  → BFF com validação Zod e rotas fixas
    → FastAPI com validação Pydantic
      → JobManager / um worker local
        → motor prospect existente + GooglePlacesProvider
        → repositório de staging SQLite :memory:

Salvar selecionados
  → IDs de resultados da pesquisa (sem aceitar dados arbitrários de leads)
    → SelectionStore / lock de escrita
      → BEGIN IMMEDIATE + deduplicação + backup + _insert + COMMIT
```

O staging é isolado por pesquisa. Duplicados dentro da pesquisa são eliminados pelas mesmas identidades do desktop; empresas já existentes na carteira continuam visíveis, marcadas como **Já cadastrado**. A verificação é repetida ao paginar e dentro da transação de salvamento, para cobrir alterações concorrentes do desktop.

O frontend não chama Google diretamente. O BFF não é um proxy genérico: valida IDs, corpo, enum de exportação e paginação, limita os campos encaminhados e aceita somente backend HTTP em loopback. A validação de origem usa o Host efetivo, porque o Next pode normalizar `request.url` para `localhost` mesmo quando o navegador usa `127.0.0.1`; origens externas continuam bloqueadas.

## Endpoints

| FastAPI                                             | BFF Next.js                                          | Comportamento                                                                                          |
| --------------------------------------------------- | ---------------------------------------------------- | ------------------------------------------------------------------------------------------------------ |
| `POST /v1/prospecting/search`                       | `POST /api/prospecting/search`                       | Valida e aceita job; HTTP 202 com ID e estado                                                          |
| `GET /v1/prospecting/search/{id}`                   | `GET /api/prospecting/search/{id}`                   | Estado, critérios, encontrados/analisados, páginas/chamadas, erro seguro e disponibilidade da gravação |
| `GET /v1/prospecting/search/{id}/results`           | `GET /api/prospecting/search/{id}/results`           | Resultados e identificação de cadastro existente; `page`, `pageSize`                                   |
| `POST /v1/prospecting/search/{id}/cancel`           | `POST /api/prospecting/search/{id}/cancel`           | Solicitação cooperativa e idempotente de cancelamento                                                  |
| `POST /v1/leads/import`                             | `POST /api/leads/import`                             | Importa somente `searchId` + `resultIds`, após estado terminal                                         |
| `GET /v1/prospecting/search/{id}/export?format=csv` | `GET /api/prospecting/search/{id}/export?format=csv` | Download de todos os resultados aceitos; também aceita `xlsx`                                          |

Corpo de pesquisa:

```json
{
  "niche": "clínicas odontológicas",
  "location": "São Paulo, SP",
  "quantity": 20,
  "neighborhood": "",
  "onlyWithoutWebsite": false,
  "minScore": 60
}
```

Quantidade inteira de 1 a 100; score inteiro de 0 a 100 (aplicado quando o filtro sem site está ativo); textos limitados; campos desconhecidos rejeitados. IDs de pesquisa são UUIDs hexadecimais. Importação aceita no máximo 100 IDs únicos efetivos, sem dados fornecidos pelo navegador para sobrescrever o lead.

Erros relevantes: 404 para pesquisa expirada/inexistente; 409 para importar/exportar pesquisa ainda em execução; 422 para parâmetros/seleção inválidos; 429 para concorrência/limite de jobs; 503 para gravação desabilitada, base incompatível/bloqueada ou backend indisponível. Erros de Google durante o job tornam o estado `failed`, com mensagem genérica e resultados parciais disponíveis, sem expor exceções, corpo bruto ou chaves.

## Jobs e limites

- `ThreadPoolExecutor(max_workers=1)`, sem Redis/Celery. Estados: `pending`, `running`, `completed`, `failed`, `cancelled`.
- Uma pesquisa ativa por processo; outra tentativa recebe 429. Até 20 pesquisas recentes retidas.
- Até 100 resultados solicitados, 200 candidatos analisados e 10 chamadas externas por pesquisa, respeitando os limites existentes. O Google pode esgotar a fonte antes da meta.
- Timeout de socket do provider de 15 segundos e orçamento cooperativo de 120 segundos para o job. A chamada em andamento não é interrompida à força; o cancelamento/timeout é observado entre chamadas e candidatos. Não há retry automático que consuma quota adicional.
- Resultados terminais disponíveis por 15 minutos. Expiração verificada em acesso e limpeza periódica a cada 30 segundos. São perdidos ao reiniciar o processo; não são cache permanente no disco.
- Pré-validação do schema/base antes de iniciar o worker evita consumir quota para uma carteira indisponível. Nenhuma migração é disparada por essa verificação.
- Polling frontend a cada 1,5 segundo enquanto ativo; em falha de acompanhamento, até três tentativas com intervalo de 5 segundos e retomada manual. Interrompe no estado terminal ou ao sair da página.
- O ID da pesquisa é guardado em `sessionStorage`, sem resultados ou chave, para retomar na mesma aba. Os critérios são restaurados do status. Apenas a pesquisa mais recente é retomada automaticamente.
- Andamento mostra contagens observadas, sem porcentagem artificial. Cancelar preserva resultados já processados e não insere nenhum lead por si só. Importação/exportação ficam disponíveis após estado terminal, inclusive para resultados parciais.

## Escrita, backup e compatibilidade SQLite

A leitura de Carteira/Dashboard continua em `mode=ro`. A seleção usa uma conexão separada `mode=rw`, que **não cria banco ausente**, com busy timeout de 5 segundos e lock por processo. O schema deve conter os campos já usados pelo desktop; incompatibilidade exige atualização explícita pelo desktop, sem `CREATE/ALTER` automático na API.

Cada importação é um lote atômico em `BEGIN IMMEDIATE`. Leads já existentes são contabilizados como duplicados, nunca atualizados. Falhas de validação, inserção, lock ou backup revertem o lote inteiro. A deduplicação é verificada com o lock de escrita adquirido, preservando consistência com o desktop.

Antes da primeira inserção de cada execução do backend, uma conexão somente leitura cria um snapshot pelo SQLite backup API em `<pasta-do-banco>/backups/<nome>-pre-web-<timestamp>-<uuid>.db`. O writer já segura `BEGIN IMMEDIATE`, impedindo outra escrita durante esse snapshot. O backup passa por `PRAGMA quick_check`; falha impede a importação. A marca de backup concluído só é consolidada após o commit. Lotes totalmente duplicados não criam backup nem atualizam registros. Não há limpeza automática desses backups.

CSV e XLSX são gerados em memória e enviados como download, sem abrir Excel ou pastas no servidor. Reutilizam os dados e a infraestrutura Python de planilhas já existente (`openpyxl`); a API não chama `os.startfile`. Valores que poderiam ser interpretados como fórmulas são neutralizados nos arquivos exportados.

## Executar

Na raiz do repositório:

```powershell
backend/.venv/Scripts/python.exe -m pip install -r backend/requirements.txt
backend/.venv/Scripts/python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Em outro terminal:

```powershell
cd web
npm ci
npm run dev
```

Abra http://127.0.0.1:3000/prospeccao. A integração utiliza a chave Google já configurada no servidor; não é necessário cadastrar outra chave. Somente o clique em **Iniciar pesquisa** dispara consulta ao Google e pode consumir quota.

Para validar escrita sem tocar na base original:

```powershell
backend/.venv/Scripts/python.exe -m backend.scripts.check_database_copy
```

Esse comando lê a base configurada em modo somente leitura, testa inserção/deduplicação/backup em cópia temporária, confere a preservação dos registros originais e remove a cópia. Foi executado com a base de 197 leads.

Depois de validar, para habilitar gravação na base escolhida, no terminal do backend **antes de iniciá-lo**:

```powershell
$env:LOUNG_ENABLE_WRITES='1'
backend/.venv/Scripts/python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

`LOUNG_DATABASE_PATH` permite apontar outra base existente; `LOUNG_API_URL` configura o endereço local no processo Next. Não alteramos `.env`. Para voltar ao padrão de leitura: `Remove-Item Env:LOUNG_ENABLE_WRITES -ErrorAction SilentlyContinue` e reinicie o backend.

## Testes sem consultas reais

```powershell
backend/.venv/Scripts/python.exe -m pip install -r backend/requirements-dev.txt
backend/.venv/Scripts/python.exe -m backend.scripts.run_offline_tests backend/tests -q --basetemp=backend/.phase22-release -o cache_dir=backend/.pytest_cache
.venv/Scripts/python.exe -m backend.scripts.run_offline_tests tests/test_prospecting.py tests/test_google_places.py tests/test_places_target.py tests/test_places_target_sprint.py tests/test_places_neighborhood.py tests/test_database.py -q --basetemp=backend/.phase22-legacy -o cache_dir=backend/.pytest_cache
```

O runner bloqueia DNS e conexões não locais. Os testes usam transportes Google simulados, chaves sintéticas e bancos temporários. Cobrem validação, paginação, falhas Google, timeout, limites de concorrência, cancelamento com parciais, deduplicação, importação, rollback, backup, schema incompatível/indisponível, exportação CSV/XLSX e proteção contra fórmulas.

Para testar o BFF e a interface completos, **use a fixture em vez da API real**:

```powershell
backend/.venv/Scripts/python.exe -m uvicorn backend.tests.prospecting_fixture_server:create_app --factory --host 127.0.0.1 --port 8100 --no-access-log
```

Em outro terminal:

```powershell
cd web
$env:LOUNG_API_URL='http://127.0.0.1:8100'
npm run build
npm run start -- --port 3100
```

Na raiz:

```powershell
.venv/Scripts/python.exe web/scripts/check_prospecting.py http://127.0.0.1:3100 http://127.0.0.1:8100
```

O script exige assinatura da fixture, usa Edge instalado/Playwright existente, bloqueia requisições não locais e valida o caminho real Next → FastAPI → motor com transporte Google simulado → SQLite temporário. Nunca o aponte para uma API de produção. Ao terminar, encerre os servidores e remova `LOUNG_API_URL` do terminal antes de iniciar a configuração real.

### Resultados

Validação em 16/10/2026, Windows, Node 24 e ambientes virtuais separados:

| Verificação | Resultado |
| --- | --- |
| Testes backend pelo runner offline | **33 aprovados**, incluindo 18 testes/casos novos da fase e os 15 anteriores |
| Testes existentes do motor/provider/filtros/banco pelo runner offline | **114 aprovados** |
| Cópia temporária da base real | **197 originais preservados**, inserção, repetição deduplicada e backup validados; fonte inalterada |
| `npm run lint` | Aprovado, sem erros/avisos |
| `npm run typecheck` | Aprovado |
| `npm run build` | Aprovado, incluindo todas as rotas dinâmicas de prospecção/importação |
| `pip check` no ambiente backend | Sem dependências incompatíveis |
| `check_prospecting.py`, com fixture + build de produção | Aprovado: BFF, motor com transporte mock, seleção entre páginas, CSV/XLSX, backup/importação, Carteira, retomada, falha sanitizada e cancelamento com parciais |
| `check_ui.py`, com fixture | Seis páginas em três resoluções; navegação, foco, validação sem pesquisa, preferências, cópia e 404 aprovados; zero erros JavaScript/requisições externas |
| Integridade dos arquivos fora de `/web` e `/backend` | Dos 235 arquivos originais, somente os **dois módulos compartilhados intencionalmente alterados** diferem; os outros 233, incluindo banco e `.env`, permanecem idênticos |

As capturas da Prospecção em **1440×1000**, **1024×768** e **390×844**, os arquivos exportados sintéticos e o relatório JSON estão em `web/test-results/` (ignorados pelo Git). Não houve transbordamento horizontal da página; a tabela mantém sua própria rolagem. As capturas desktop e móvel foram inspecionadas. Os servidores de validação foram encerrados ao finalizar.

O teste integrado identificou e levou à correção da comparação de origem localhost/127.0.0.1 no BFF e da restauração dos critérios ao retomar uma pesquisa. O lint também levou ao uso de `useWatch` e à manutenção das referências fora da renderização, sem desabilitar regras.

Permanece apenas o aviso upstream de depreciação do uso de `httpx` pelo TestClient/Starlette já identificado na fase anterior; não houve falha de teste. A configuração/chave real do Google e a resposta do serviço ao vivo não foram testadas, conforme a proibição de pesquisas reais nesta entrega. A integração de produção chama o provider existente, e os testes substituem exclusivamente seu transporte HTTP, sem simular sucesso na aplicação normal.

O runner offline também injeta uma chave sintética no processo de teste, impedindo que a configuração herdada seja usada pelo provider. Nenhuma variável desse processo modifica `.env` ou o ambiente persistente do usuário. A configuração padrão de produção foi conferida: `writes_enabled=False`.

## Arquivos principais

- Compartilhados: `core/prospecting/service.py`, `core/database/lead_repository.py`.
- Backend: `config.py`, `main.py`, requirements e `.gitignore`; novos `prospecting/{models,jobs,storage,routes}.py`, `scripts/{check_database_copy,run_offline_tests}.py`, `tests/test_prospecting_api.py`, `tests/prospecting_fixture_server.py`.
- Frontend: novos contratos/schema, proxy de prospecção, guarda de origem local e seis rotas BFF; `components/prospecting-workspace.tsx`, página `/prospeccao`, cliente/contratos API, estilos de checkbox e textos de disponibilidade; teste `scripts/check_prospecting.py` e ajuste seguro do teste geral da interface.
- Documentação: este relatório, READMEs e referência arquitetural. Nenhum arquivo de configuração de segredo, schema SQLite ou widget desktop foi alterado.

## Políticas Google e limitações de produção

As [políticas de Places](https://developers.google.com/maps/documentation/places/web-service/policies) impõem requisitos de atribuição, armazenamento e uso dos dados; a existência de um botão de salvar/exportar não representa permissão contratual irrestrita. O `place_id` tem exceção de armazenamento, que não se estende automaticamente aos demais campos. Resultados exibem atribuição Google Maps e ficam temporariamente em memória; a operação de importação é explícita e desabilitada por padrão. O operador deve verificar os termos aplicáveis ao seu contrato antes de habilitar armazenamento/exportação no uso real, incluindo requisitos de termos de uso/privacidade antes de disponibilizar o produto. Esta entrega não afirma que o armazenamento permanente de todo conteúdo Places é permitido. Não há pré-busca automática, enriquecimento, coleta de reviews/fotos ou retries silenciosos. Paginação segue o [Text Search New](https://developers.google.com/maps/documentation/places/web-service/text-search) existente.

Esta é uma solução local, **um processo/um worker Uvicorn**, sem login, multiempresa, fila durável ou recuperação de jobs após reinício. Não executar com múltiplos workers: o estado em memória não é compartilhado e os limites são por processo, não por conta Google. Quotas/custos do desktop e de outros clientes não entram no contador deste worker. Para produção, implementar autenticação/autorização, isolamento por organização, jobs duráveis, idempotência de criação de pesquisas, limites globais, auditoria, gestão de retenção e backups, e persistência adequada à escala. Não publicar os endpoints atuais na internet.
