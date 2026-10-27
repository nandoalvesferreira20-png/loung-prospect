# Plano de auditoria e limpeza técnica — Loung Prospect

**Data:** 20/10/2026. **Estado:** diagnóstico e proposta; limpeza NÃO executada. A migration da Fase 3.2 permanece fora desta auditoria e não foi executada.

## 1. Diagnóstico geral

A evolução desktop → web reutiliza regras de negócio reais, não apenas código abandonado. `core/` atende desktop e backend; `main.py` continua oferecendo GUI e CLI; `app.py` instancia a interface; o Prototype Studio usa `core/prototype/` e descobre `templates/` pelo filesystem. A aplicação web mantém o fluxo Next BFF → FastAPI → PostgreSQL/Supabase Auth. A estratégia recomendada é preservar esses limites e eliminar primeiro artefatos comprovadamente regeneráveis, sem reorganizar todo o monorepositório.

Os maiores volumes dispensáveis são builds Next, caches Python e cópias de QA. O maior candidato condicionado é o ambiente `venv/` antigo. Não foi comprovada dependência de produção sem uso que justifique remover pacotes. Os poucos arquivos de código aparentemente mortos são stubs vazios; merecem validação, não exclusão automática.

Há uma prioridade de segurança independente da limpeza: **uma chave Google Places histórica em `.env.example` coincide com a chave configurada localmente hoje**. Sua validade não foi testada. Ela deve ser tratada como exposta, com rotação/restrição por um operador. Nenhum valor de credencial consta deste documento.

### Escopo e método

- Inventário físico de arquivos regulares, sem seguir junctions, excluindo os metadados internos de `.git` da contagem de arquivos de trabalho. Caminhos longos foram reenumerados com suporte Win32 estendido; não restaram erros de enumeração no inventário.
- Leitura de 390 arquivos de texto de projeto, com inspeção de AST/importações Python, importações relativas e dinâmicas literais, pontos de entrada CLI, configuração, referências documentais e convenções de entrada Next/pytest. A contagem textual inclui também arquivos de dados de protótipos; não significa 390 módulos de código.
- Comparação de duplicados por SHA-256. As 260 cópias de fontes classificadas em A foram comparadas byte a byte por hash com os arquivos canônicos em `web/`.
- Inspeção do índice Git, regras de ignore, 24 commits locais, 536 blobs alcançáveis por refs/reflogs e 28 blobs identificados como inalcançáveis pelo `git fsck`. A varredura de segredos reportou somente tipo, localização e comparação em memória; não imprimiu nem persistiu valores encontrados.
- Testes offline e build em diretório temporário novo, sem copiar `.env`, sem acessar Supabase e sem interromper o Next do usuário. Testes criaram apenas fixtures sintéticas descartáveis; nenhum banco existente foi aberto para escrita. Não foram iniciados fixtures PostgreSQL nem executadas migrations.

**Limites:** uma análise estática não prova ausência absoluta de referências calculadas, execução externa de scripts ou segredos em formatos desconhecidos. Não foram consultados remotes, branches não obtidas, configuração hospedada do Supabase, permissões de acesso ao repositório remoto nem validade de chaves. Pacotes instalados e bundles gerados não receberam auditoria integral de código de terceiros ou análise forense de conteúdo. Não há garantia de que um cache esteja livre de dados sensíveis.

### Quantidades e unidade de contagem

O snapshot inicial contém **60.920 arquivos regulares**, dos quais **323 rastreados**. O estado de trabalho tinha **26 arquivos rastreados modificados e 69 arquivos não rastreados não ignorados**. Estes últimos incluem implementação essencial das Fases 3.1/3.2; `untracked` não significa descartável.

As categorias são mutuamente exclusivas no snapshot. D significa preservar o arquivo e considerar refatoração futura. Arquivos criados depois do inventário pelos testes/build desta auditoria, este plano e os helpers de auditoria não entram nessas contagens. Diretórios vazios e três junctions não são contados como arquivos.

| Categoria | Arquivos | Volume lógico aproximado | Decisão |
| --- | ---: | ---: | --- |
| A — remoção segura de artefatos | **3.869** | **1,18 GiB** | Somente após aprovação e parada dos processos que os utilizem |
| B — remoção condicionada | **6.985** | **237,75 MiB** | Confirmar uso, diferenças, ambiente e retenção |
| C — preservar | **50.032** | **949,19 MiB** | Sem exclusão neste plano |
| D — refatoração recomendada | **34** | **174,38 KiB** | Preservar; mudanças separadas, cobertas por testes |
| **Total** | **60.920** | **2,33 GiB** | Nenhuma limpeza executada |

Dos arquivos C, **48.896** pertencem às instalações ativas `.venv/`, `backend/.venv/` e `web/node_modules/`. Dos arquivos B, **6.966** pertencem ao `venv/` antigo. Para evitar inflar a impressão de código descartável, excluindo essas instalações há **5.058 arquivos: A 3.869, B 19, C 1.136, D 34**. A não contém nenhum arquivo rastreado; B contém apenas três arquivos rastreados, todos vazios: `assets/fonts`, `config` e `core/logger.py`.

## 2. Estrutura atual

```text
loung-prospect/
├── main.py, app.py                 # CLI/GUI desktop; ainda utilizados
├── LoungLeads.spec                 # Configuração de empacotamento desktop
├── core/                          # 63 fontes/arquivos; regras compartilhadas
│   ├── database/                   # SQLite e repositórios usados por serviços
│   ├── commercial/, qualification/ # Regras reutilizadas na API
│   ├── providers/, prospecting/    # Google Places e coleta
│   ├── sales/, outreach/           # SDR, Groq/OpenAI/Ollama e contatos
│   └── prototype/                  # Geração e registro de protótipos desktop
├── ui/                            # 29 arquivos desktop, além dos caches
├── templates/                     # 16 arquivos, quatro templates carregados dinamicamente
├── prototypes/                    # 8 arquivos gerados, dois conjuntos comerciais rastreados
├── assets/fonts                   # Arquivo vazio, não diretório de fontes
├── config                         # Arquivo vazio, não diretório de configuração
├── scripts/                       # 5 scripts CLI/QA desktop
├── tests/                         # 54 arquivos; suíte desktop/core
├── backend/                       # 62 arquivos fora de ambientes/caches/artefatos
│   ├── main.py, config.py, authorization.py
│   ├── persistence/               # PostgreSQL, contexto de identidade e rotas 3.2
│   ├── crm/, prospecting/, sdr/    # Serviços e contratos existentes
│   ├── scripts/                   # Inicialização, diagnósticos e migração SQLite
│   ├── tests/                     # Unitários, integração e servidores sintéticos
│   ├── migration-report.json, phase31-dry-run.json
│   └── .phase31-*/, .phase32-*/    # Artefatos misturados com cópias de bancos
├── web/                           # 127 arquivos fora de node_modules/.next
│   ├── src/app/                   # Páginas, autenticação, equipe e rotas BFF
│   ├── src/components/, src/lib/   # UI, contratos, clientes e proxies
│   ├── scripts/                   # QA Playwright, testes Node e PostgreSQL sintético
│   ├── docs/                      # Relatórios de fases e runbooks
│   ├── package.json, package-lock.json, configurações
│   └── .next/, node_modules/      # Build/cache e dependências locais
├── supabase/                      # 3 migrations SQL + validation/session_access.sql
├── docs/                          # 15 documentos do desktop/negócio
├── data/                          # 8 SQLite, incluindo base e backups
├── output/                        # 9 exportações Excel comerciais
├── .venv/, backend/.venv/, venv/   # Três ambientes com conteúdo diferente
└── temp/                          # Cópias isoladas de QA/build, ignoradas
```

## 3. Segurança e integridade

| Achado | Evidência sem segredo | Risco | Ação recomendada, não executada |
| --- | --- | --- | --- |
| Chave Google Places no histórico | Blob `648887a0bea4fe66a3fc40749b566879b3a118a4`, caminho `.env.example`; transições localizadas nos commits `79e1ff9` e `1ef98e9`. Comparação em memória confirmou igualdade com a chave local atual | **Alto**: possível consumo de quota/custos e uso indevido; validade e exposição remota não verificadas | Operador deve restringir/revogar/substituir a chave e revisar uso/quota. Depois, atualizar ambientes autorizados e confirmar que exemplos contêm somente placeholders. Eventual saneamento de histórico exige decisão separada; remover do HEAD não remove o passado |
| Credenciais de backend em `web/.env.local` | Há variáveis Google/Groq e `LOUNG_POSTGRES_DSN`, além de variáveis públicas Supabase | **Médio/alto**: duplicação aumenta superfície de acesso e chance de inclusão em logs/configuração futura | Planejar separação: arquivo web com configurações estritamente necessárias ao Next; credenciais operacionais no backend. Não apagar nem trocar valores durante limpeza. A presença de uma variável sem `NEXT_PUBLIC_` não prova que ela foi publicada no bundle do navegador |
| `.env` e `web/.env.local` | Não rastreados e efetivamente ignorados. Somente `.env.example` está rastreado atualmente | Proteção atual adequada, sem apagar exposição histórica | Preservar; testar exceções de templates e checagem de segredos antes de futuras publicações |
| Login operacional | Inspeção local do identificador da DSN confirma o login esperado `loung_web`, sem imprimir a conexão; flag de escrita continua desligada | Sem verificação online de grants nesta auditoria | Preservar configuração. Não testar escrita real, trocar usuário ou ampliar permissões para facilitar manutenção |
| Protótipos comerciais rastreados | `prototypes/*/{index.html,prototype.json,css/style.css,js/script.js}`: 8 arquivos; dois manifests com nome comercial e dois HTML com links de telefone/WhatsApp | **Médio**: divulgação de dados comerciais por versionamento/distribuição | Preservar e conferir titularidade, consentimento de distribuição e retenção. Futuramente gerar fora do conteúdo versionado e usar somente exemplos sintéticos em fixtures. Não excluir agora nem reescrever histórico |
| Dados locais | 8 bancos em `data/`, 9 Excel em `output/`, 752 bancos/cópias sob artefatos de backend | **Alto em caso de exclusão ou publicação** | Preservar todos. Separar inventário e política de retenção de dados da limpeza de caches. Não concluir que um `.db` é descartável apenas pelo diretório |
| Cópias de ambiente de teste | 11 arquivos `server.env`/`synthetic.env` sob `.phase*`, além dos cinco arquivos de ambiente/exemplo principais | Conteúdo de teste não justifica uma exclusão por máscara ampla | C por precaução; eventual descarte só após confirmar origem sintética e aprovação específica |
| DSN literal detectada em teste | `backend/tests/test_access_diagnostics.py`, função `test_session_probe_refuses_administrative_login_before_connect` | Falso positivo de formato: fixture sintética para impedir conexão administrativa | Preservar teste; não registrar a string nem classificá-lo como credencial real |

Nenhum `.db`, `.sqlite`, `.xlsx`, `.csv`, `.bak` ou `.log` foi encontrado no índice atual. Na revisão dos objetos alcançáveis, os artefatos comerciais identificados foram os protótipos; não foram localizados dumps/bancos por nome de arquivo. Além da chave Google confirmada, os padrões examinados não identificaram outro segredo real no histórico. Isso não equivale a uma certificação de ausência de segredos, especialmente em formatos binários, conteúdo compactado e remotes não obtidas.

Não foram alterados credenciais, arquivos `.env`, refs, commits ou reflogs. Não houve `git clean`, `reset`, `stash`, remoção do índice, commit ou reescrita de histórico.

## 4. Classificação dos arquivos

Os caminhos abaixo são relativos à raiz. `**` descreve um grupo de arquivos do snapshot, não uma autorização para exclusão recursiva. Em particular, **não apagar o diretório `temp/` ou `.phase*` inteiro**: ele pode conter exceções B/C e junctions.

### A — remoção segura após aprovação

“Segura” significa regenerável e sem trabalho exclusivo identificado; não significa remover enquanto um processo estiver usando o artefato. Excluir `.next` de um servidor aberto pode interromper a aplicação.

| Caminho/grupo | Arquivos | Motivo e dependências | Risco | Ação sugerida |
| --- | ---: | --- | --- | --- |
| `web/.next/**` | 1.487 | Build/cache Next; depende dos fontes, lockfile, configuração e ambiente de build | Baixo após parar a instância correspondente; alto para disponibilidade se estiver em uso | Regenerar por build/dev depois de autorização; preservar o servidor atual até combinar a parada |
| `backend/.phase31-auth-diagnostics/.next/**` | 1.042 | Build do sandbox de diagnóstico, não fonte operacional | Baixo, depois de confirmar que o sandbox não está ativo | Descartar somente arquivos gerados; não atravessar a junction `node_modules` |
| `temp/phase32-final-web-b0f82aa4b51c48a3812857fa868ab8ea/.next/**` | 463 | Build da cópia final de QA, reprodutível | Baixo, condicionado à ausência de processo de QA | Descartar somente o build aprovado |
| `temp/phase32-web-486f1626f7c24cabb0d2f9875bc88ebc/.next/**` | 463 | Build da cópia anterior de QA | Baixo, mesma condição | Descartar somente o build aprovado |
| `__pycache__/**` nas raízes e módulos de `backend/`, `core/`, `ui/`, `tests/` | 148 | Bytecode gerado pelo Python; não inclui caches internos dos ambientes preservados | Baixo | Regenerar automaticamente pelos imports/testes |
| `backend/.pytest_cache/**` | 5 | Histórico/cache pytest, sem função de aplicação | Baixo | Descartar cache após registrar este baseline |
| `web/tsconfig.tsbuildinfo` | 1 | Cache incremental TypeScript | Baixo | Regenerar por typecheck/build |
| Cópias de fontes idênticas em `backend/.phase31-auth-diagnostics/` | 75 | SHA-256 igual ao equivalente canônico `web/<caminho relativo>` | Baixo apenas para os arquivos comparados | Confirmar hash novamente no momento da limpeza e remover pelo manifesto individual |
| Cópias de fontes idênticas em `temp/phase32-final-web-b0f82aa4b51c48a3812857fa868ab8ea/` | 93 | Mesma comparação com `web/` | Baixo, sem alterações exclusivas | Mesmo procedimento; respeitar a exceção B de `next-env.d.ts` |
| Cópias de fontes idênticas em `temp/phase32-web-486f1626f7c24cabb0d2f9875bc88ebc/` | 92 | Mesma comparação com `web/` | Baixo, sem alterações exclusivas | Mesmo procedimento; respeitar as duas exceções B |
| **Total A** | **3.869** | Nenhum arquivo rastreado | | |

As três junctions de `node_modules` dos sandboxes foram identificadas e não seguidas. Não são arquivos da contagem A. O alvo compartilhado `web/node_modules/` é C; uma rotina futura de limpeza deve usar caminhos absolutos conferidos e nunca seguir essas junctions para excluir conteúdo.

### B — remoção após validação

| Caminho | Arquivos | Motivo | Dependências a validar | Risco / ação sugerida |
| --- | ---: | --- | --- | --- |
| `venv/**` | 6.966 | Ambiente antigo diferente de `.venv` e `backend/.venv`; não é o ambiente indicado nos comandos atuais | Processos, atalhos, IDE, pacote de distribuição e versões instaladas. Ele tem bibliotecas desktop, mas não pytest/Groq | **Médio**. Não remover antes de existir ambiente desktop completo e reprodutível, nem presumir que bibliotecas instaladas não tenham valor de diagnóstico |
| `core/logger.py` | 1 | Arquivo vazio, sem importação/referência identificada | Possíveis consumidores externos não presentes no repositório | **Baixo**, após confirmação de ausência de contrato externo; não confundir com `core/diagnostics.py` ou os loggers funcionais |
| `config` | 1 | Arquivo vazio na raiz, sem papel identificado; não é `backend/config.py` nem `core/sales/config.py` | Scripts externos e intenção de diretório futuro | **Baixo**, validar intenção e remover só esse arquivo se aprovado |
| `assets/fonts` | 1 | Arquivo vazio; tema desktop declara não depender de fontes externas | Empacotamento/atalhos externos | **Baixo**, confirmar empacotamento. Não remover `assets/` por uma máscara geral |
| `web/scripts/check_auth_diagnostics.py` | 1 | Script executável por Python com porta fixa 3199 e `sys.argv`; sem referência identificada em código/docs atuais | Verificação de configuração ausente e zero requisições de Auth; não é totalmente substituída só por teste unitário | **Médio**. Documentar e manter, ou incorporar a cobertura ao QA atual antes de remover |
| `backend/.phase31-visual/authenticated-profile.png` | 1 | Evidência de validação já realizada | Relatórios de release e política de retenção | **Baixo para runtime**, mas conferir se é necessário manter evidência e se há dados sensíveis antes de descartar |
| `backend/.phase32-visual/activities-desktop.png` e `team-mobile.png` | 2 | Capturas sintéticas de QA 3.2 | Evidências da release ainda não implantada | **Baixo para runtime**; manter até aceite/retention definidos |
| Cópias divergentes detalhadas abaixo | 12 | Diferença de hash em relação à fonte canônica ou configuração específica do sandbox | Diff e intenção da cópia; diferença não prova que a cópia seja obsoleta | **Médio**. Comparar sem expor credenciais; incorporar qualquer correção exclusiva antes de descartar |
| **Total B** | **6.985** | **19 fora do ambiente `venv/`** | | |

**Doze exceções de cópias de QA, não autorizadas como A:**

| Raiz | Caminhos relativos divergentes |
| --- | --- |
| `backend/.phase31-auth-diagnostics/` | `AGENTS.md`; `next-env.d.ts`; `next.config.mjs`; `src/app/api/leads/route.ts`; `src/app/api/leads/[leadId]/route.ts`; `src/app/configuracoes/page.tsx`; `src/app/leads/page.tsx`; `src/components/crm/lead-profile.tsx`; `src/components/session-provider.tsx` |
| `temp/phase32-final-web-b0f82aa4b51c48a3812857fa868ab8ea/` | `next-env.d.ts` |
| `temp/phase32-web-486f1626f7c24cabb0d2f9875bc88ebc/` | `next-env.d.ts`; `src/app/configuracoes/atividades/page.tsx` |

### C — preservar

| Grupo de caminhos | Arquivos | Motivo e dependências | Risco / ação sugerida |
| --- | ---: | --- | --- |
| `.venv/**`, `backend/.venv/**`, `web/node_modules/**` | 48.896 | Instalações usadas pelos comandos desktop, API e Next. Não são fonte, mas a aplicação e a validação dependem delas | **Médio/alto** se removidas em uso. Preservar; só discutir reconstrução depois de locks e ambiente reprodutível. Não contabilizar como “código morto” |
| `data/**/*.db` e `backend/.phase*/**/*.db`, além de eventuais extensões/sidecars de banco do inventário | 760 | 8 bancos sob `data/` e 752 arquivos de banco sob artefatos de backend; podem incluir snapshots importantes ou dados reais | **Alto**. Preservar todos nesta proposta; validar proveniência individual em iniciativa de retenção separada. Nenhuma exclusão por idade ou caminho |
| `.env`, `.env.example`, `backend/.env.example`, `web/.env.example`, `web/.env.local` e 11 ambientes de teste sob `.phase*` | 16 | Configuração operacional, exemplos e evidências de testes | **Alto** para configurações reais. Preservar valores; separar risco de segredo da decisão de exclusão |
| `output/**/*.xlsx` e `prototypes/**` | 17 | 9 exportações e 8 arquivos de protótipos; podem representar trabalho comercial exclusivo | **Alto** para perda de dados; conferir retenção/distribuição, sem apagar ou publicar |
| Demais fontes, testes, templates, migrations, configurações e documentos, excluídos os 34 itens D | 343 | Componentes funcionais, convencionais ou de uso ainda não descartado | **Médio/alto**. Preservar; não inferir inutilidade por falta de import explícito |
| **Total C** | **50.032** | | |

Preservações importantes dentro do último grupo:

- `app.py`, `ui/**`, `core/**` e entradas de `main.py`: desktop ainda referenciado pela GUI, CLI, testes e empacotamento. `main.py` é D por duplicação de coleta, mas continua preservado.
- `core/sales/ollama.py` e os providers OpenAI/Groq: seleção dinâmica em `core/sales/provider.py` e testes específicos. Usar Groq no fluxo web não torna os outros adapters mortos.
- `core/prototype/**` e `templates/**`: `TemplateRegistry` enumera diretórios; CSS/JS de templates são usados pelo gerador e não precisam aparecer como import Python.
- `core/__init__.py`, `ui/__init__.py` e demais `__init__.py`: mesmo vazios, participam do empacotamento/importação. Não agrupar com stubs vazios removíveis.
- `LoungLeads.spec`: configuração de empacotamento, não build descartável. A inclusão de templates no pacote merece validação separada; não apagar o spec por ser desktop.
- `web/next-env.d.ts`, `package-lock.json`, `components.json`, configs Next/PostCSS/TypeScript e `web/AGENTS.md`: geração, CLI ou convenção de framework não significam inutilidade.
- Entradas Next `page.tsx`, `layout.tsx`, `route.ts`, `error.tsx`, `loading.tsx`, `not-found.tsx`, `proxy.ts`: descobertas pelo framework; não precisam de import de outro módulo para serem utilizadas.
- `tests/test_*.py`, `backend/tests/test_*.py` e `conftest.py`: descoberta pelo pytest. Os servidores `*_fixture_server.py` são entradas do uvicorn documentadas; ausência de import estático não é código morto.
- `scripts/check_*.py`, `scripts/test_google_places_real.py`, `backend/scripts/check_*database_copy.py`, `check_access.py`, `check_session_access.py`, `check_migration_target.py`, `run_api.py`, `run_offline_tests.py`, `migrate_sqlite.py`: comandos operacionais e de QA. O teste Google real consome quota e não foi executado. Scripts de cópia SQLite continuam documentados; não foram rodados nesta auditoria.
- `supabase/migrations/202610190001_phase31.sql`, `202610200001_repair_auth_schema_usage.sql`, `202610200002_team_operations.sql` e `supabase/validation/session_access.sql`: preservar, inclusive se não rastreados. Histórico de schema não é um conjunto de scripts temporários.
- `backend/migration-report.json`, `backend/phase31-dry-run.json`, `web/docs/phase-3-1-audit.json`, `phase-3-2-audit.json`, runbooks de Auth/ACL/migração e relatórios `phase-2-*.md`: evidências operacionais/históricas. O relatório antigo com `applied: false` não deve ser confundido com estado atual do destino, nem apagado para eliminar a divergência; falta vincular o comprovante da importação concluída informado pelo usuário.

### D — refatoração recomendada, mantendo comportamento

Esta tabela cobre os **34 arquivos D**, sem contabilizá-los novamente em C. Prioridade significa ordem de análise, não autorização para editar.

| Caminho(s) | Nº | Problema / dependências | Risco | Ação sugerida e validação |
| --- | ---: | --- | --- | --- |
| `README.md` | 1 | Apresentação exclusiva de desktop/SQLite omite o produto web atual | Baixo | Criar visão geral dos dois pontos de entrada e links para runbooks; preservar instruções desktop úteis |
| `web/README.md` | 1 | Afirma Fase 2.4 sem autenticação e sem necessidade de `.env`, incompatível com configuração atual | **Alto operacional** | Atualizar início rápido para Auth/PostgreSQL e distinguir histórico/local opt-in; testar comandos sem credenciais no documento |
| `backend/README.md` | 1 | Aviso 3.1 no topo, mas corpo ainda sugere SQLite padrão e inicialização sem ambiente | **Alto operacional** | Separar caminho atual `run_api`/ambiente explícito do legado; validar health/login em homologação autorizada |
| `web/docs/architecture.md` | 1 | Arquitetura descrita até Fase 2.4, com decisões históricas apresentadas como atuais | Médio | Registrar arquitetura vigente, links por fase e limites de implantação; não apagar histórico |
| `tests/README.md` | 1 | Cobertura e limitações desatualizadas diante de testes CLI/GUI/core adicionados | Baixo | Atualizar comandos, quantidade/requisitos e distinguir testes mocked de smoke real |
| `.gitignore`, `backend/.gitignore`, `web/.gitignore` | 3 | Regras por fase e lacunas para saídas comerciais/novos artefatos | Médio | Usar proposta da seção 6; validar ignore em fixtures, env templates e arquivos rastreados |
| `pytest.ini` | 1 | `testpaths=tests` não inclui backend; execução completa do backend requer PostgreSQL e pode executar migrations no fixture | Médio | Definir jobs/markers e opt-in de integração explícitos antes de ampliar descoberta automática; não simplesmente adicionar backend ao default |
| `requirements.txt`, `requirements-dev.txt`, `backend/requirements.txt`, `backend/requirements-dev.txt` | 4 | Ambientes divergentes, pouca fixação no desktop; dependências compartilhadas repetidas; `groq` declarado mas ausente no desktop | Médio | Documentar ambientes, gerar constraints/locks por runtime, conferir dependências diretas como Pydantic e executar `pip check`; não fundir ambientes nem remover pacotes por dedução |
| `web/package.json` | 1 | Testes Node/QA não estão expostos em scripts npm; `npm test` não representa a cobertura existente | Baixo | Adicionar comandos explícitos de unitário/BFF e QA opt-in, sem iniciar serviços ou migrations implicitamente |
| `web/eslint.config.mjs` | 1 | Exceções de artefatos espalhadas; futura pasta única de QA precisará alinhar lint/TypeScript/ignore | Baixo | Ajustar apenas quando o destino de artefatos estiver aprovado; verificar lint sem suprimir fontes |
| `backend/persistence/postgres.py` | 1 | Tradução de SQL SQLite por substituições/regex, wrapper Row/Cursor e ciclo de conexão concentrados | **Alto** | Separar fronteiras gradualmente, fortalecer testes de SQL e fechamento de conexão, manter RLS, claims e preservação do erro original. Não substituir o adapter inteiro durante limpeza |
| `backend/persistence/runtime.py` | 1 | Middleware, erros, registro multi-org, sessão, lifespan e rotas no mesmo módulo | Alto | Extrair responsabilidades pequenas preservando ordem de autorização e flag de escrita; testes de sessão expirada, membership revogada, leitura e escrita desligada |
| `backend/persistence/team.py`, `backend/persistence/leads.py` | 2 | Rotas também contêm transações/SQL e regras de domínio | Alto | Extrair serviços/modelos somente após teste PostgreSQL autorizado; manter owner efetivo no SQL, transações, revisão e rollback de auditoria |
| `backend/scripts/migrate_sqlite.py` | 1 | Validação de origem, backup, transformação, aplicação e apresentação concentrados | **Alto** | Considerar separação interna com testes de idempotência/source-id; manter CLI e nunca usar migração real como teste de refatoração |
| `backend/prospecting/jobs.py`, `backend/sdr/service.py` | 2 | Estado, concorrência, expiração, providers e apresentação de falhas se misturam | Alto | Isolar ciclo de vida/estado e contratos existentes; preservar cancelamento, limites, deduplicação e ausência de chamadas reais nos testes |
| `main.py` | 1 | Coletor monolítico antigo e fluxo modular coexistem; CLI ainda usa o antigo sem flags especiais | Alto | Futuramente convergir por contrato, sem eliminar `run`, extração ou CLI apenas por semelhança com `core/scraper.py`; testes de roteamento e exportação primeiro |
| `ui/sales_workspace.py` | 1 | Módulo grande concentra widgets, estado e callbacks | Médio | Extrair helpers puros mantendo compatibilidade de UI e thread/Tk; smoke desktop antes e depois |
| `web/src/lib/api/proxy.ts`, `crm-proxy.ts`, `prospecting-proxy.ts`, `sdr-proxy.ts`, `team-proxy.ts` | 5 | Repetem origem, URL loopback, sessão, fetch, timeout e tradução de erro; proxy de equipe também trata leads | **Alto** | Extrair transporte `server-only` com rotas/verbos permitidos por domínio. Não criar proxy que aceite URL arbitrária ou repasse cookies/organização do navegador |
| `web/src/app/api/session/route.ts` | 1 | Validação de backend e tradução de falhas duplicadas dos proxies, com códigos próprios relevantes | Alto | Compartilhar somente transporte seguro; preservar códigos específicos de configuração, Auth e membership |
| `web/src/components/session-provider.tsx` | 1 | Refresh, navegação, logout e estado de falha no mesmo componente | Médio | Extrair hook de sessão se houver benefício demonstrado; manter expiração, bloqueio sem organização e cancelamento de consultas |
| `web/src/components/lead-editor.tsx`, `web/src/app/configuracoes/equipe/page.tsx`, `web/src/app/configuracoes/atividades/page.tsx` | 3 | JSX e operações densos em linhas longas; contratos/respostas e estados repetidos | Médio | Formatação legível, contratos tipados e hooks pequenos; preservar confirmação, revisão, campos digitados e bloqueio de escrita. Validar teclado/mobile |
| **Total D** | **34** | | | |

## 5. Duplicação, código morto e dependências

### Duplicados confirmados não são automaticamente removíveis

- Os cinco arquivos vazios `assets/fonts`, `config`, `core/logger.py`, `core/__init__.py`, `ui/__init__.py` têm o mesmo conteúdo, mas somente os três primeiros são B; os dois inicializadores de pacote são C.
- Há CSS/JS idênticos entre templates e protótipos gerados, e JS idêntico entre três templates. O gerador copia o template para um pacote autônomo de protótipo. A duplicação é funcional; trocar por links compartilhados quebraria a autonomia do resultado. Preservar.
- As 260 cópias byte-idênticas de QA não participam do runtime canônico e são A; as doze diferenças foram preservadas em B. Reconferir hashes e processos no momento de uma futura limpeza.
- Similaridade entre `main.py` e módulos de scraping, ou entre backend SQLite/PostgreSQL, não comprova código morto. As entradas legadas e adaptação de serviços estão ativas.

### Dependências

Não foi identificada remoção segura de dependência declarada:

| Dependência/grupo | Uso identificado |
| --- | --- |
| CustomTkinter e Playwright Python | GUI desktop, CLI/coleta e scripts de QA; não removíveis porque a web usa FastAPI |
| Pandas/OpenPyXL | Importação/exportação desktop e exports da API |
| python-dotenv | Providers, inicialização e diagnósticos com carregamento explícito |
| Groq | Providers SDR e testes; ausência na `.venv` desktop é falha de instalação, não prova de desuso |
| FastAPI/Uvicorn/Psycopg/PyJWT[crypto] | API, execução, PostgreSQL e assinatura/verificação de sessão |
| pytest/httpx | Suíte e TestClient; dependências de desenvolvimento, não runtime desktop obrigatório |
| react-hook-form e @hookform/resolvers | `web/src/components/prospecting-workspace.tsx` |
| Radix Dialog/Slot, CVA, clsx, tailwind-merge | Shell, diálogos de edição, botão e composição de estilos |
| Recharts/Lucide | Gráfico e ícones de UI |
| Supabase JS/SSR | Auth de navegador, cookies SSR e validação de sessão no BFF |
| Tailwind/PostCSS, Next/React/ReactDOM | Build, estilos e convenções de runtime |
| PGlite e pglite-socket | `web/scripts/phase31-postgres.mjs`, infraestrutura PostgreSQL sintética; são devDependencies necessárias |
| TypeScript, @types/*, ESLint e eslint-config-next | Typecheck, tipos implícitos e configuração de qualidade; não exigir import de aplicação como prova de uso |

Antes de propor remoções, distinguir dependência direta, transitiva, CLI e tipos. Comparar os ambientes e confirmar instalação limpa com lock/constraints em local isolado. Não rodar `npm uninstall`, reinstalação ou atualização de versões como parte desta auditoria.

## 6. Gitignore e manutenção recomendados

As regras atuais já cobrem ambientes virtuais, bytecode, Next, node_modules, caches comuns, logs, `.env`, bancos, backups e estado de navegador em `playwright/.auth/`. As exceções de `.env.example`/`.env.template` e fixtures CSV/XLSX são importantes. Preservar a decisão explícita de versionar `.spec`.

Propostas para uma etapa posterior, sujeitas a revisão:

| Ajuste | Benefício / cuidado |
| --- | --- |
| Ignorar `/output/` e futuros resultados em `/prototypes/` | Hoje `.xlsx` é ignorado globalmente, mas HTML/JSON/novos formatos podem entrar no Git. Ignorar não remove os oito protótipos já rastreados nem saneia histórico; essa decisão precisa de revisão de dados separada |
| Adotar uma pasta única ignorada para novos artefatos, por exemplo `/artifacts/qa/` | Evita novos diretórios `.phase33-*` e cópias no backend. Não mover saídas existentes nesta etapa; primeiro atualizar escritores, docs e validações |
| Revisar se ainda é necessária regra para `.pytest_tmp/` documentada no README | Comando documentado não deve gerar diretório inesperado não ignorado; verificar por `git check-ignore` |
| Preservar regras gerais de bancos e adicionar, se realmente usados, sidecars `.sqlite3-wal`/`.sqlite3-shm` e dumps `.dump`/`.sql.gz` | Evitar exposição de formatos não cobertos; não adicionar `*.sql`, pois esconderia migrations/validações essenciais |
| Considerar `*.pem`, `*.key`, `*.p12`, `*.pfx` com exceções explícitas para fixtures sintéticas quando necessárias | Camada preventiva; não substitui secret scanning nem autoriza apagar chaves reais |
| Alinhar os três `.gitignore` sem consolidar cegamente | Regras locais são legítimas; manter exceções e verificar precedência com `git check-ignore -v` |
| Verificar antes de ignorar relatórios JSON | Não ignorar todos os `*.json` ou todos os relatórios de release. Runbooks, auditorias e comprovantes de migração têm retenção diferente de log temporário |
| Documentar comandos de teste no npm e separar jobs Python | Evitar que ausência de `npm test` ou descoberta limitada pelo pytest seja confundida com ausência de cobertura |

Não usar `git clean -fdx`, `git reset --hard`, `git checkout -- .` ou `git rm` em massa: há mudanças e fontes essenciais ainda não rastreadas. Acrescentar uma regra de ignore não torna seguro apagar o que ela cobre.

## 7. Estrutura sugerida

Proposta conservadora: manter os diretórios de runtime e acrescentar clareza documental/operacional. Não mover `core`, `ui`, backend ou frontend só para padronizar nomes.

```text
main.py, app.py, LoungLeads.spec     # Entradas desktop preservadas
core/                              # Domínio compartilhado e adapters existentes
ui/                                # Desktop
backend/                           # FastAPI, módulos de domínio e persistence
  scripts/                         # Comandos operacionais documentados
  tests/                           # Unitários e integração com markers explícitos
web/
  src/                             # Next e BFF
  scripts/                         # QA até uma reorganização justificada
  docs/                            # Relatórios históricos web, com índice atualizado
supabase/
  migrations/                      # Histórico incremental imutável após aplicação
  validation/                      # Consultas/diagnósticos revisados
docs/
  README.md                        # Futuro índice: arquitetura vigente, desktop, web e operação
  operations/                      # Futuro destino lógico de runbooks, sem mover agora
tests/                             # Caracterização desktop/core preservada
templates/                         # Assets de geração, versionados
data/, output/, prototypes/        # Dados/saídas com retenção e acesso próprios
artifacts/qa/                      # Futuras saídas sintéticas, ignoradas e sem dados reais
```

Criar um índice e atualizar os três READMEs traz benefício imediato maior que uma reorganização de imports. Eventual mudança de runbooks ou helpers deve atualizar referências e ser feita separadamente, com caminho compatível se houver uso CLI externo. Não se propõe converter o repositório inteiro para `apps/`/`packages/` neste momento.

## 8. Baseline de validação desta auditoria

| Verificação | Resultado inicial | Limite |
| --- | --- | --- |
| Desktop: `.venv/Scripts/python.exe -B -m pytest tests -q ...` | **Falha de coleta em 3 módulos** por `ModuleNotFoundError: groq` | Nenhum pacote foi instalado para esconder o problema; requirements já declara Groq |
| Desktop completo, com `site.addsitedir` do site-packages backend apenas no processo de teste | **1.034 passaram, 73,10 s** | Execução complementar em ambiente composto, não baseline de ambiente desktop autossuficiente; nenhuma instalação ou alteração persistente |
| Backend offline, excluindo três módulos de integração PostgreSQL | **120 passaram, 26,95 s** | Um aviso existente de depreciação Starlette/httpx |
| Backend PostgreSQL/RLS/3.2 | **22 testes não reexecutados** | `test_phase31_postgres.py`, `test_auth_schema_acl.py`, `test_phase32_team.py` exigem banco e/ou migrations. Não executados por restrição desta auditoria. O relatório 3.2 registra execução anterior de 142 testes, mas isso não é resultado novo |
| Testes Node Auth/BFF | **8 passaram** | Stubs de Auth/fetch; sem Supabase real |
| TypeScript | **Passou** | `npm.cmd run typecheck -- --incremental false`, sem regravar cache incremental |
| ESLint | **Passou** | `npm.cmd run lint` |
| Build de produção | **Passou** | `npm.cmd run build -- --webpack` em cópia temporária sem `.env` real, com configurações públicas sintéticas; não valida produção hospedada nem o caminho Turbopack |
| Smoke Playwright/GUI e APIs reais | **Não executado nesta auditoria** | Evita interação com aplicação/dados reais e configuração de banco. QA sintético anterior está nos relatórios de fase |
| Integridade Git | **Inspeção e fsck concluídos** | Objetos inalcançáveis foram apenas inspecionados, não removidos; histórico não alterado |

O SQLite original foi apenas lido para SHA-256, mantido em `1a98fe82146ed3b53d429aab9bc6eab7a137f0f00ce38a50970eb76d1f410915` entre o início e a verificação final da auditoria. Nenhuma importação foi repetida; a quantidade real de leads/interações no Supabase não foi consultada, e a informação de 160/17 foi preservada como contexto informado pelo usuário.

### Comandos reproduzíveis sem migrations

Usar um `--basetemp` **novo** a cada execução; pytest pode limpar um diretório previamente existente. Não reutilizar diretórios com dados importantes.

```powershell
# Baseline canônico do desktop — hoje expõe a ausência de Groq:
.venv/Scripts/python.exe -B -m pytest tests -q -p no:cacheprovider --basetemp=temp/AUDIT_DESKTOP_NOVO

# Backend offline, sem iniciar PostgreSQL ou executar migrations:
backend/.venv/Scripts/python.exe -B -m backend.scripts.run_offline_tests backend/tests -q -p no:cacheprovider --basetemp=temp/AUDIT_BACKEND_NOVO --ignore=backend/tests/test_phase31_postgres.py --ignore=backend/tests/test_auth_schema_acl.py --ignore=backend/tests/test_phase32_team.py

# No diretório web:
npm.cmd run typecheck -- --incremental false
npm.cmd run lint
node --test scripts/auth.test.mjs scripts/team.test.mjs
```

Para reproduzir a verificação complementar desktop sem instalar pacotes, executar `.venv/Scripts/python.exe -B -` com o seguinte Python, somente em diretório temporário novo:

```python
import os, site
from pathlib import Path
site.addsitedir(str(Path('backend/.venv/Lib/site-packages').resolve()))
os.environ['GOOGLE_PLACES_API_KEY'] = 'offline-synthetic-key-not-real'
os.environ['GROQ_API_KEY'] = 'offline-synthetic-key-not-real'
import pytest
raise SystemExit(pytest.main(['tests', '-q', '-p', 'no:cacheprovider',
                             '--basetemp=temp/AUDIT_DESKTOP_COMPLEMENTAR_NOVO']))
```

A fixture `tests/conftest.py` bloqueia rede/navegador reais. O runner backend bloqueia rede externa. Não reutilizar esse ajuste de `site-packages` como configuração de produção: resolver a instalação reprodutível é a ação correta de manutenção.

## 9. Plano de execução em etapas e critérios de aceite

**Nenhuma etapa abaixo está autorizada para execução por este documento. A aprovação do usuário deve especificar as categorias/itens.** Segurança de credenciais, limpeza física, refatoração e aplicação da migration são decisões distintas.

| Etapa | Trabalho proposto | Validação necessária antes/depois | Critério de parada |
| --- | --- | --- | --- |
| 0 — proteger trabalho e estado | Conferir diff, fontes não rastreadas, processos e dados; preparar cópia/referência privada do trabalho sem publicar segredos; manter escrita de produção desligada | Comparar lista de fontes, hash do SQLite e três migrations; atualizar manifesto por arquivo e detectar junctions | Mudança inesperada, arquivo sem dono ou dados sem proveniência: preservar e interromper aquele item |
| 1 — tratar exposição | Operador rotaciona/restringe a chave Google e revisa duplicação de configuração web/backend; nenhuma reescrita de histórico implícita | Inspeção sanitizada dos exemplos e da configuração, confirmação operacional de quota/uso; validação Auth/leitura em ambiente autorizado | Não remover configuração antes de mapear os processos que a carregam |
| 2 — higiene Git e documentação urgente | Ajustar ignores aprovados e atualizar READMEs/índice, mantendo documentos históricos | `git check-ignore -v` para env, exemplos, fixtures, SQL e artefatos; revisar diff e links; testes Node/TS/lint | Fonte, fixture ou migration passa a ser ignorada indevidamente: corrigir antes de avançar |
| 3 — limpeza A | Aprovar manifesto atualizado, combinar parada apenas dos processos que usam os builds, eliminar arquivos A individualmente, sem seguir links | Regenerar Next em ambiente isolado; 8 Node, TS, lint, build, 120 backend offline e suíte desktop canônica após corrigir ambiente; hash SQLite/migrations deve permanecer igual | Arquivo A mudou de hash, processo está usando o caminho ou encontra `.db`/backup/env: reclassificar, não excluir |
| 4 — validação e limpeza B | Primeiro tornar desktop reprodutível; só depois confirmar `venv/`, stubs, diagnóstico solto, diferenças e retenção de capturas | Comparar dependências/processos/atalhos; 1.034 desktop em ambiente próprio completo; smoke desktop/CLI mockado e template/protótipo sintético; diff das 12 cópias | Ambiente principal incompleto, correção exclusiva em cópia, evidência ainda necessária ou uso externo: manter |
| 5 — organização sem migração ampla | Destino de novos artefatos e comandos de teste consistentes, sem mover módulos por estética | Scripts produzem somente no destino aprovado; documentação e fixtures atualizadas; testes offline e Next repetidos | Necessidade de alterar contrato CLI/import sem teste de compatibilidade: separar a mudança |
| 6 — refatorações D pequenas | Uma responsabilidade por alteração: transporte BFF, legibilidade/contratos, lifecycle, serviços; SQL adapter por último | Suítes anteriores mais os 22 testes PostgreSQL/RLS em banco **isolado**, somente com autorização específica para preparar seu schema; testes de rollback, owner, membership, sessão, idempotência/source-id e concorrência | Qualquer mudança de regra de acesso, persistência ou resultado comercial deve virar tarefa funcional separada, não “limpeza” |
| 7 — aceite e operação | Revisar diff e manifesto final, deixar ao usuário decisões de versionamento/publicação | Confirmar aplicação web funcionando, fontes e dados preservados, zero segredo novo no Git, relatórios de testes e pendências explícitos | Não aplicar migration 3.2 nem habilitar escrita real como consequência automática da limpeza |

Não executar testes de escrita contra os 160 leads. Não usar remoção de dados, nova importação, novo `source-id`, mudança de grants ou desativação de RLS como forma de validar manutenção. A implantação da migration 3.2 deve seguir seu runbook e aprovação próprios depois desta revisão.

## 10. Resumo para aprovação futura

- **Remoção segura proposta: 3.869 arquivos**, todos ignorados/gerados, sem fonte rastreada; depende da parada dos processos correspondentes e reconferência do manifesto.
- **Remoção condicionada: 6.985 arquivos**, sendo 6.966 de um ambiente virtual antigo e apenas 19 outros itens.
- **Preservação: 50.032 arquivos C + 34 arquivos D = 50.066 arquivos**. Inclui desktop, regras compartilhadas, dados, backups, migrations, configurações, dependências ativas e fontes que só podem receber refatorações separadas.
- Prioridades: credencial Google exposta no histórico; documentação operacional atualizada; ambiente desktop reprodutível; depois caches e organização.

**Aguardando aprovação. Nenhum arquivo preexistente foi excluído, movido ou renomeado. Nenhuma funcionalidade, credencial, configuração de produção, banco ou migration foi alterada.** Foram criados apenas este plano e artefatos auxiliares ignorados de auditoria/teste/build, preservados conforme a restrição de não excluir arquivos nesta etapa.
