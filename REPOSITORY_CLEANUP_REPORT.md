# Relatório de execução da limpeza controlada

**Data:** 20/10/2026. **Base:** [REPOSITORY_CLEANUP_PLAN.md](REPOSITORY_CLEANUP_PLAN.md). **Resultado:** lote seguro concluído, sem alteração de funcionalidade, credenciais, dados reais ou migrations Supabase.

## 1. Escopo executado

Foi executado um lote dos arquivos A que ainda existiam, estavam fora de uso e puderam ser revalidados. Antes de excluir, cada arquivo passou por conferência do caminho absoluto dentro do workspace, ausência de junctions/symlinks, tipo de arquivo, ausência no índice Git e SHA-256. Cópias de fontes foram comparadas novamente com a fonte canônica em `web/`.

As exclusões usaram caminhos literais e arquivos individuais, sem exclusão recursiva de árvores. Diretórios foram removidos somente depois de constatar que estavam vazios. Nenhum arquivo rastreado foi excluído. As exceções B/C existentes dentro dos sandboxes permaneceram no lugar.

O Next do usuário estava ativo na porta 3000. Por isso, `web/.next/` foi integralmente preservado e nenhum processo do usuário foi interrompido. As instalações `.venv/`, `backend/.venv/`, `venv/` e `web/node_modules/` não foram removidas ou reinstaladas. Junctions de `node_modules` não foram seguidas nem removidas.

## 2. Arquivos e diretórios removidos

### Lote principal: arquivos preexistentes

| Caminho/grupo | Arquivos removidos | Critério |
| --- | ---: | --- |
| `backend/.phase31-auth-diagnostics/.next/**` | 1.042 | Build antigo de sandbox inativo |
| `temp/phase32-final-web-b0f82aa4b51c48a3812857fa868ab8ea/.next/**` | 459 | Build antigo inativo; quatro arquivos do inventário anterior já não existiam |
| `temp/phase32-web-486f1626f7c24cabb0d2f9875bc88ebc/.next/**` | 460 | Build antigo inativo; três arquivos do inventário anterior já não existiam |
| Cópias idênticas em `backend/.phase31-auth-diagnostics/` | 75 | Hash igual ao arquivo canônico em `web/` |
| Cópias idênticas em `temp/phase32-final-web-b0f82aa4b51c48a3812857fa868ab8ea/` | 93 | Mesma verificação |
| Cópias idênticas em `temp/phase32-web-486f1626f7c24cabb0d2f9875bc88ebc/` | 92 | Mesma verificação |
| Bytecode em `__pycache__` da raiz, `backend/`, `core/`, `ui/` e `tests/` | 148 | Somente `.pyc`/`.pyo`; ambientes virtuais excluídos do lote |
| `backend/.pytest_cache/**` | 5 | Cache pytest |
| `web/tsconfig.tsbuildinfo` | 1 | Cache TypeScript regenerável |
| **Total preexistente** | **2.375** | **754.660.966 bytes lógicos** |

Foram removidos **794 diretórios que ficaram vazios**. Os diretórios pais com arquivos B/C, configurações ou junctions permaneceram.

Dos 3.869 arquivos A previstos no snapshot anterior, 2.375 foram removidos, 1.487 eram do build ativo preservado e sete já estavam ausentes antes desta execução. Os sete não foram contabilizados como removidos nem como espaço recuperado.

### Temporários produzidos pela própria validação

O build pós-limpeza foi executado numa cópia nova, sem `.env` real, em `artifacts/qa/cleanup-validation-20261020/web-build/`. Após o build passar e encerrar, seu cache `.next/` foi descartado pelo mesmo princípio de manifesto, hash, caminhos limitados, ausência de links e exclusão de arquivos individuais.

- **392 arquivos** de cache gerados nesta tarefa: **265.636.357 bytes lógicos**.
- **203 diretórios vazios** removidos nessa cópia de validação.
- A cópia de fontes, os resultados e os bancos sintéticos de teste foram preservados. Esse descarte encerra o ciclo do build temporário, não representa remoção de outros arquivos B/C do projeto.

**Total de operações de exclusão:** **2.767 arquivos e 997 diretórios vazios**, incluindo os temporários gerados nesta tarefa. O total lógico excluído foi **1.020.297.323 bytes**; não deve ser interpretado como ganho líquido de 1 GB, pois parte desses arquivos foi criada durante a validação.

### Evidências detalhadas

Os registros abaixo são locais e ignorados pelo Git. Contêm caminhos, tamanhos, hashes e resultados; não contêm valores de credenciais.

- [Manifesto prévio e hashes de preservação](temp/controlled-cleanup-20261020/manifest.json).
- [Lista individual dos 2.375 arquivos removidos](temp/controlled-cleanup-20261020/deleted-files.ndjson).
- [Resultado e lista dos 794 diretórios vazios removidos](temp/controlled-cleanup-20261020/result.json).
- [Manifesto dos 392 arquivos de cache da validação](temp/controlled-cleanup-20261020/validation-cache-manifest.json).
- [Resultado do descarte do cache de validação](temp/controlled-cleanup-20261020/validation-cache-result.json).
- [Consolidação final](temp/controlled-cleanup-20261020/final-summary.json).

Esses manifestos não são autorização para repetir a limpeza. Reavaliar caminhos, processos e hashes em qualquer execução futura. Preservar os registros até o aceite desta entrega.

## 3. Espaço recuperado

| Medida | Resultado |
| --- | ---: |
| Volume lógico removido do lote preexistente | **754.660.966 bytes ≈ 719,70 MiB** |
| Aumento de espaço livre observado imediatamente após esse lote | **755.802.112 bytes ≈ 720,79 MiB** |
| Ganho líquido observado ao final, após testes e descarte do cache de validação | **749.998.080 bytes ≈ 715,25 MiB** |
| Artefatos novos de validação retidos, sem seguir junctions | **931 arquivos, 19.673.930 bytes ≈ 18,76 MiB** |

A variação de espaço livre no volume também sofre efeitos de alocação, atividade de outros processos e regeneração de caches. Por isso são apresentados separadamente volume lógico excluído e observações de espaço livre. Os artefatos retidos incluem fontes da cópia isolada, relatórios e fixtures sintéticas; não foi mantido o cache `.next` do build de validação.

## 4. Itens preservados por precaução

| Item | Decisão e motivo |
| --- | --- |
| `web/.next/` | Servidor ativo do usuário; preservado para evitar indisponibilidade |
| `venv/` legado | Não apareceu em uso pelos processos inspecionados, mas os quatro critérios de remoção não estão integralmente cumpridos: a `.venv` desktop ainda não possui Groq instalado e não há ambiente desktop autossuficiente validado. Nenhuma dependência foi instalada para contornar essa condição |
| `.venv/`, `backend/.venv/`, `web/node_modules/` | Instalações ativas preservadas integralmente |
| Doze cópias divergentes da categoria B | Preservadas com hashes iguais aos registrados antes da limpeza; não houve tentativa de mesclar ou descartar mudanças exclusivas |
| `assets/fonts`, `config`, `core/logger.py` | Stubs rastreados e condicionais; não removidos |
| `web/scripts/check_auth_diagnostics.py` e capturas de QA | Uso/retention condicionais; preservados |
| SQLite original, backups, demais `.db` preexistentes e exportações | Preservados, inclusive os encontrados em diretórios de testes antigos; nenhuma exclusão por máscara de `.phase*` ou por idade |
| `.env`, `web/.env.local` e demais ambientes/exemplos | Conteúdo preservado. A chave Google conhecida não foi alterada nem impressa |
| Desktop, templates, protótipos e Fase 3.2 | Fontes e trabalho comercial preservados; nenhum arquivo funcional excluído |
| Migrations e relatórios operacionais | Preservados, mesmo quando não rastreados. Nenhuma migration foi aplicada ao Supabase |
| Cópia de build produzida na auditoria anterior e outros temporários fora do manifesto A | Não houve expansão automática da limpeza para pastas inteiras fora do lote aprovado |

A verificação final conferiu **1.190 arquivos protegidos**. As únicas diferenças de conteúdo autorizadas foram `.gitignore` e `web/.gitignore`. Não houve outra mudança, arquivo protegido ausente ou perda de entradas no estado Git inicial. O SQLite original manteve o SHA-256 `1a98fe82146ed3b53d429aab9bc6eab7a137f0f00ce38a50970eb76d1f410915`.

Nenhuma conexão foi feita ao banco Supabase real para importar, alterar ou recontar os 160 leads e 17 interações. A preservação foi garantida pela ausência de operações sobre o destino real, não por um teste de escrita ou por uma nova importação.

## 5. Alterações de `.gitignore`

Foram acrescentadas à raiz:

- `/output/` e `/prototypes/`, para evitar o versionamento de novas saídas comerciais. Arquivos já rastreados continuam rastreados; não houve remoção do índice.
- `.pytest_tmp/`, alinhando a proteção ao comando documentado no README.
- `/artifacts/qa/`, destino ignorado dos novos relatórios e fixtures de validação.
- `*.tsbuildinfo`, para caches TypeScript fora da pasta web.
- `*.dump` e `*.sql.gz`, para dumps locais sem esconder migrations `.sql`.

Em `web/.gitignore`, foi acrescentada a exceção `!/.env.template`; a exceção existente de `.env.example` foi preservada. As regras existentes de ambientes virtuais, logs, SQLite, backups, caches e Next foram mantidas. `backend/.gitignore` foi revisado e não recebeu mudanças nesta execução.

**15 verificações de ignore passaram**, incluindo envs privados, exemplos, templates, fixtures CSV, SQL de migration e relatórios operacionais. Não foram adicionadas regras amplas como `*.json` ou `*.sql`. Nenhum arquivo de credenciais foi editado e nenhum commit ou reescrita de histórico foi criado.

## 6. Testes antes e depois

| Verificação | Snapshot da auditoria | Após a limpeza |
| --- | --- | --- |
| Desktop no ambiente canônico `.venv` | Três erros de coleta por ausência de Groq | Condição preexistente permanece; dependências não foram alteradas |
| Desktop com complemento de `site-packages` backend somente no processo de teste | 1.034 passaram em 73,10 s | **1.034 passaram em 28,98 s**, zero falhas/erros/skips |
| Backend offline | 120 passaram em 26,95 s | **120 passaram em 20,28 s**, zero falhas/erros/skips |
| PostgreSQL/RLS/Fase 3.2 | 22 não reexecutados naquela auditoria | **22 passaram em 10,55 s**, zero falhas/erros/skips, em PostgreSQL efêmero em memória |
| Auth/BFF Node | 8 passaram | **8 passaram** |
| TypeScript | Passou | **Passou**, com `--incremental false` |
| ESLint | Passou | **Passou** |
| Build Next de produção | Passou com webpack, em cópia isolada | **Passou com webpack**, em cópia nova sem `.env` real |
| Entrada Desktop | Desktop preservado no diagnóstico | `main.py --help` e import/dispatch de `main.main([])` passaram; janela mockada, sem abrir a base real |
| Entrada FastAPI | Comando documentado existente | Help do launcher e inicialização real do processo pelo launcher passaram; `/health` respondeu em configuração isolada sem DSN e com escrita desligada |
| Servidor do usuário | `/login` 200; `/api/session` sem cookie 401 | **Mesmos resultados**; não houve login com credenciais reais nem interrupção do serviço |

Total Python confirmado: **1.176 testes**, sendo 1.034 Desktop e **142 backend** (120 offline + 22 PostgreSQL). O complemento de bibliotecas foi limitado ao processo de testes e **não** torna a instalação desktop independente; não utiliza o `venv/` legado.

O PostgreSQL dos testes usa endereço fixo de loopback e marcador `synthetic-memory-only`, sem ler DSNs reais do ambiente. O schema e as migrations foram exercitados somente nesse banco em memória para os testes; nada foi executado no Supabase real. O processo foi encerrado após a validação. O único aviso das suítes backend foi a depreciação Starlette/httpx já conhecida.

### Incidente de preparação da validação, corrigido

A primeira execução Python desta tarefa foi iniciada antes de criar a pasta pai de `--basetemp`. Isso produziu erros `FileNotFoundError` de setup: Desktop 976 passaram/58 erros, backend 42 passaram/78 erros. A limpeza foi interrompida para investigação, sem novas exclusões do projeto. A causa foi o diretório de validação ausente, não mudança nas fontes ou uma asserção funcional.

Foi criada explicitamente a pasta pai e as suítes foram repetidas em **outros diretórios novos**, sem apagar os temporários da tentativa anterior. Os resultados confirmados acima passaram integralmente. Nenhuma funcionalidade foi alterada para fazer os testes passarem.

Resultados locais:

- [Desktop confirmado](artifacts/qa/cleanup-validation-20261020/desktop-confirmed.xml).
- [Backend offline confirmado](artifacts/qa/cleanup-validation-20261020/backend-confirmed.xml).
- [PostgreSQL/RLS confirmado](artifacts/qa/cleanup-validation-20261020/postgres-confirmed.xml).
- [Inicialização Desktop/FastAPI](artifacts/qa/cleanup-validation-20261020/startup-results.json).
- [Verificações de ignore](temp/controlled-cleanup-20261020/ignore-checks.json).

Esses testes não substituem homologação do Supabase hospedado, login de usuários reais, teste visual completo da GUI ou aprovação para habilitar escrita em produção. O teste de entrada GUI foi mockado deliberadamente para não inicializar bancos ou preferências reais.

## 7. Pendências para uma segunda etapa

1. Tornar a instalação desktop reprodutível e completa, incluindo Groq, e validar os 1.034 testes sem complemento de outro ambiente. Só depois reconsiderar `venv/`, atalhos/IDE e versões eventualmente exclusivas.
2. Combinar uma janela de parada caso seja desejável descartar o build ativo `web/.next/`. Não removê-lo durante o serviço.
3. Revisar as doze cópias divergentes, a retenção de capturas, o script diagnóstico solto e os três stubs B antes de qualquer exclusão adicional.
4. Estabelecer retenção para fixtures e artefatos posteriores ao snapshot; manter relatórios suficientes para auditoria. Não apagar bancos/backups em lote.
5. Manter a rotação/restrição da chave Google como pendência de segurança já conhecida, tratada separadamente pelo operador. Credenciais e histórico Git não foram alterados nesta limpeza.
6. Prosseguir com documentação/refatorações D e implantação da Fase 3.2 somente em tarefas separadas e autorizadas. Esta limpeza não habilitou escrita de produção e não aplicou a migration ao Supabase.

**Encerramento:** limpeza comprovadamente segura executada, sem exclusão de itens condicionais, código funcional, dados reais, backups ou trabalho Git não commitado. Os manifestos e a validação permitem conferir cada exclusão e comparar o resultado com o snapshot original.
