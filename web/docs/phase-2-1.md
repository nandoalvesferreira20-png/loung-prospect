# Fase 2.1 — auditoria e API de leitura

## Auditoria antes da implementação

Foram lidos `web/docs/architecture.md`, os contratos e o adaptador web, a conexão/schema/repositórios SQLite, as regras comerciais, o Meu Dia e a classificação de contato. A implementação desktop permanece em `main.py`, `app.py` e `ui/`. A base padrão é `data/loung_prospect.db`, com caminho absoluto derivado do projeto.

Na consulta de verificação, a base existente tinha **197 leads**. A inspeção de formato foi feita com SQLite `mode=ro`, sem exportar registros, imprimir informações individuais ou executar migrações. Os endpoints de listagem e indicadores responderam 200 e concordaram no total de 197.

### Compatibilidade encontrada

| Desktop / SQLite | Contrato web e tratamento |
| --- | --- |
| `empresa`, `telefone`, `segmento`, `site`, `cidade` | `company`, `phone`, `niche`, `website`, `location`; campos ausentes opcionais continuam `null` |
| `status` em português, aliases antigos e valores personalizados | `stage` normalizado apenas na resposta; `originalStage` mantém o valor salvo |
| `qualification_score` pode estar ausente no legado | `score` opcional; valores não numéricos não quebram ordenação do Meu Dia |
| `proximo_contato`, `proxima_acao` adicionados em migrações posteriores | Campos opcionais; não executar migrações na leitura |
| `lead_contact_preferences.contact_type` | Ajuste manual prevalece sobre a sugestão por `segmento`; tradução explícita para o enum web |
| Todos os status do desktop, incluindo perdas, retornos e restrições | Lista de filtros vem da API, incluindo etapas personalizadas; não limitada às seis colunas do quadro inicial |
| Datas de próximo contato em ISO com fuso | Indicadores reutilizam `build_day`; datas inválidas são sinalizadas, sem inventar agendamentos |

O construtor de `LeadRepository` chama `initialize_database`, que executa `BEGIN IMMEDIATE`, cria tabelas e adiciona colunas. `connect_database` também cria diretórios. Por isso, ambos permanecem inalterados e não são utilizados para abrir a base na API de consulta. A API usa um adaptador próprio com URI SQLite `mode=ro`, `PRAGMA query_only=ON`, conexões por operação e snapshot transacional. Isso permite ler a mesma base sem comprometer a versão desktop.

Reutilizados diretamente: `core.commercial.values.commercial_status` e `STATUSES`, `core.commercial.day.build_day`, `core.sales.contact_routing.classify_contact`. As integrações Google Places/Groq, geração de drafts, importação/exportação e repositórios de escrita continuam disponíveis no desktop para migrações futuras, sem serem importados ou chamados pela API atual.

## Arquitetura implementada

```text
Navegador
  → Next.js: GET /api/leads e /api/overview (BFF de destinos fixos)
    → FastAPI: GET /v1/leads e /v1/overview
      → adaptador SQLite somente leitura + regras puras existentes
```

O FastAPI também oferece `/health` e `/v1/leads/{id}`. Não há rotas de escrita, Supabase, autenticação simulada ou migração do desktop. Configurações são variáveis do processo, sem editar `.env`; o caminho padrão do banco não depende do diretório de execução. O servidor Next conhece o endereço interno da API; o navegador acessa apenas a mesma origem.

A API valida limites de consulta e usa parâmetros SQL. A busca ignora acentos, caixa e pontuação. Paginação e contagem usam o mesmo snapshot, com score decrescente e ID crescente. A leitura não marca contato, não atualiza timestamps e não grava status normalizados. Mudanças feitas pelo desktop aparecem na consulta seguinte, inclusive em modo WAL.

Sem autenticação nesta etapa, os comandos padrão do frontend e backend ficam no loopback. A API restringe Host e rejeita origens de navegador; o BFF rejeita acessos cross-site, aceita apenas destino local e não encaminha cookies, credenciais ou URLs arbitrárias. Essas medidas não tornam a aplicação pronta para publicação ou uso multiempresa.

## Interface conectada

- **Leads:** dados reais, campos não informados explícitos, busca, etapas canônicas/personalizadas, seleção local, paginação no servidor, atualização e estados de carregamento, vazio e erro com nova tentativa.
- **Dashboard:** total de leads, contatos agendados para hoje, atrasados e reuniões. Os rótulos foram alinhados às definições do desktop, em vez de inferir contatos realizados ou oportunidades a partir de drafts. Gráfico mostra distribuição **atual** por etapa; não apresenta uma série histórica inventada.
- **Próximas ações:** seleção do Meu Dia, limitada a oito registros, com referência de data/fuso e aviso sobre datas inválidas.
- Prospecção, edição comercial, SDR integrado, WhatsApp e movimentação do pipeline continuam fora do escopo desta fase. Seus textos indicam essa limitação sem afirmar que a carteira inteira está desconectada.

## Arquivos principais

Criados em `backend/`: `__init__.py`, `config.py`, `models.py`, `repository.py`, `main.py`, `requirements.txt`, `requirements-dev.txt`, `.gitignore`, `README.md`, `tests/test_api.py`, `tests/fixture_server.py`.

Criados no frontend: `src/app/api/leads/route.ts`, `src/app/api/overview/route.ts`, `src/lib/api/proxy.ts`, `src/lib/api/use-read-resource.ts`, `src/components/dashboard-data.tsx`, `src/components/read-status.tsx`, `scripts/check_read_api.py` e este relatório.

Atualizados: contratos/cliente API, tabela de leads, gráfico, páginas Dashboard/Leads, textos de disponibilidade no shell/SDR/aviso compartilhado, scripts locais, `package.json` (bind local), README e decisão arquitetural. Nenhum arquivo Python desktop ou `.env` deve ser alterado por esta implementação.

## Executar e testar

Consulte [backend/README.md](../../backend/README.md) para criação do ambiente separado, instalação, inicialização, endpoints, configuração de outra base e execução com fixture sintética. Frontend: `cd web; npm ci; npm run dev`. Inicie também a API para carregar os dados; sem ela, a página mantém os valores indisponíveis, em vez de mostrar zeros falsos.

### Resultados das verificações

| Verificação | Resultado |
| --- | --- |
| Instalação em `backend/.venv` com requirements separados | Concluída; ambiente desktop preservado |
| `backend/.venv/Scripts/python.exe -m pip check` | Sem dependências incompatíveis |
| `backend/.venv/Scripts/python.exe -m pytest backend/tests -q --basetemp=backend/.test-pytest-final -o cache_dir=backend/.pytest_cache` | **15 testes aprovados** |
| `.venv/Scripts/python.exe -m pytest tests/test_database.py tests/test_commercial.py tests/test_contact_routing.py -q --basetemp=backend/.desktop-test-tmp -o cache_dir=backend/.pytest_cache` | **96 testes existentes aprovados** |
| `npm run lint` | Aprovado, sem erros/avisos |
| `npm run typecheck` | Aprovado |
| `npm run build` | Aprovado: seis páginas, 404 e duas rotas BFF dinâmicas |
| `web/scripts/check_read_api.py` com servidor sintético | Aprovado nos três tamanhos, sem erros JavaScript |
| `web/scripts/check_ui.py` com a fixture | Seis páginas × três resoluções aprovadas; menu, foco, formulário, preferências, cópia e 404 preservados; zero requisições externas |
| BFF com o processo FastAPI efetivamente encerrado | HTTP 503 com código `API_UNAVAILABLE`, sem travamento |
| Consulta somente leitura à base existente | HTTP 200 para listagem e overview; ambos totalizam 197 registros |
| Comparação SHA-256 antes/depois fora de `/web` e `/backend` | **235 arquivos idênticos**, nenhum arquivo adicionado fora dessas pastas |

Os testes da API cobrem mapeamento, preferência manual e classificação por nicho, aliases, busca com acentos/telefone, paginação, filtros parametrizados, contagens, dados incompletos, schema antigo, base vazia/ausente/corrompida/bloqueada, 404/422/405, restrições de Host/origem, proibição de UPDATE, visibilidade de alterações posteriores em WAL e preservação byte a byte da base nas consultas.

O teste de navegador usa o build de produção e uma API real servindo SQLite temporário: **1440×1000**, **1024×768**, **390×844**. Verifica o caminho HTTP completo, indicadores, distribuição por etapa, campos nulos, paginação, filtro por etapa canônica, seleção, busca, ausência de resultados, HTTP 422, restrição de origem e estado de erro/recuperação. O erro de conexão é injetado de forma controlada no navegador; não interrompe nem altera a base real. Capturas e JSON ficam em `web/test-results/`.

A primeira tentativa no servidor de desenvolvimento expirou por recompilações contínuas; a validação final foi feita no servidor de produção. O teste também revelou que o nome acessível do seletor de etapa incluía suas opções; o rótulo foi explicitado e o fluxo repetido com sucesso.

O TestClient emitiu um aviso de depreciação upstream sobre `httpx` na versão instalada do Starlette; os testes passaram. Não foi instalada uma segunda biblioteca HTTP apenas para suprimir o aviso. Nenhuma biblioteca JavaScript adicional foi necessária. Os alertas npm já registrados na Fase 1 não foram alterados por esta etapa.

Nenhuma prospecção, geração Groq ou abertura de WhatsApp foi executada. O backend nunca abriu a base real em modo de escrita, e a verificação de integridade inclui o banco e os arquivos `.env`. As alterações locais anteriores do desktop foram preservadas, sem comparação enganosa com o HEAD do Git.

Os servidores de teste foram encerrados ao final da validação.

## Próxima etapa

Definir autenticação e autorização por organização antes de disponibilizar a aplicação em rede. Depois, conectar o detalhe do lead e evoluir o SDR preservando histórico, revisão humana e proteção de edições. Operações de prospecção e exportação devem continuar separadas dos endpoints de leitura e ser executadas por jobs quando migradas.
