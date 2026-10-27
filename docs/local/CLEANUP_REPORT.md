# Limpeza controlada do repositório — 26/10/2026

## Resultado

Limpeza de artefatos gerados, atualização do README para a arquitetura local e centralização das regras de ignore. Nenhum módulo de negócio, teste, migration, banco real, backup importante ou ambiente privado foi removido ou alterado. Nenhum commit, branch ou reescrita de histórico foi realizado.

O repositório já tinha 456 arquivos de projeto presentes entre rastreados e não rastreados, com numerosas alterações pendentes. O baseline de hashes foi registrado antes das edições. Todos esses arquivos físicos permanecem presentes; as únicas edições da limpeza em arquivos preexistentes foram `README.md` e os três `.gitignore`. Os oito protótipos retirados do índice continuam no disco com os mesmos hashes.

## Arquivos removidos fisicamente

| Grupo preexistente | Arquivos | Bytes lógicos |
| --- | ---: | ---: |
| Bytecode Python em `__pycache__`, fora dos ambientes instalados | 211 | 3.076.890 |
| `temp/auth-tls-qa/web/.next/cache/**` | 24 | 288.589.672 |
| `temp/repository-audit-build-cde96768a43b4b3b80cb548c71f8ef9c/.next/cache/**` | 9 | 258.883.687 |
| Cache pytest conhecido (`.pytest_cache/**`) | 5 | 4.194 |
| **Total preexistente** | **249** | **550.554.443 — aproximadamente 525 MiB** |

Foram removidos 37 diretórios que ficaram vazios no primeiro lote e os diretórios pytest conhecidos vazios. A exclusão de arquivos individuais conferiu caminho absoluto dentro do workspace, ausência de reparse points, ausência no índice, regra de ignore e SHA256 imediatamente antes da remoção. Nenhum candidato mudou ou precisou ser descartado por conflito nesse lote.

Também foram limpos artefatos criados exclusivamente pela validação desta tarefa: 451 arquivos do sandbox de build (266.494.330 bytes), 525 arquivos temporários da suíte (13.253.314 bytes), e 199 bytecodes regenerados (2.783.069 bytes). Esses volumes **não são somados ao espaço recuperado de arquivos preexistentes**. A junction de dependências do sandbox foi removida como link, preservando `web/node_modules`.

Os manifestos detalhados, hashes e resultados ficam localmente em `artifacts/qa/local-cleanup-20261026/`, ignorados pelo Git. Eles não contêm valores de credenciais. Os relatórios de arquitetura/homologação anteriores foram preservados como evidência histórica; não foram considerados lixo apenas por terem extensão JSON ou Markdown.

## Arquivos preservados

- Código de `core/`, `backend/`, `web/src/`, CLI, interface desktop, templates, testes e lockfiles.
- Implementação SaaS, migrations SQL, RLS, organização/equipe, convites, autenticação, fixtures PostgreSQL e documentação histórica.
- `.env`, demais ambientes privados, `data/` e backups: os 13 arquivos monitorados tiveram hashes comparados antes/depois e permaneceram intactos.
- `.venv/`, `backend/.venv/`, `venv/` e `web/node_modules/`: dependências instaladas, preservadas.
- `web/.next/`: existe sessão dev ativa; não foi usado como alvo de limpeza nem substituído pelo build de validação.
- Partes `server/`, `static/`, fontes e configurações das cópias antigas de QA: só os caches de compilação explicitamente auditados foram removidos.
- Diretórios de QA antigos inacessíveis ou sem proveniência suficientemente clara, bancos de testes anteriores e backups não classificados: mantidos. Não houve exclusão recursiva cega de `temp/`, `artifacts/` ou diretórios `.phase*`.

## Classificação e recuperação SaaS

O [inventário arquivo a arquivo](CLEANUP_INVENTORY.json) registra os 456 arquivos de projeto inspecionados: **8 A**, **91 B**, **357 C**. Os artefatos gerados adicionais da categoria A estão nos manifestos de exclusão, separados dos arquivos de projeto. Não foi comprovado código de categoria D que pudesse ser excluído com segurança.

| Categoria | Exemplos e decisão |
| --- | --- |
| A — gerado/descartável | Caches apagados; oito saídas comerciais geradas retiradas apenas do índice. |
| B — legado SaaS | `backend/authorization.py`, módulos PostgreSQL em `backend/persistence/`, migrations `supabase/`, login/recuperação/convite, APIs de equipe, fixtures e diagnósticos SaaS. Preservar. |
| C — local/compartilhado | `core/`, CRM/SDR/prospecção, BFF, frontend local, scripts/testes e documentação de uso atual. Preservar. |
| D — obsoleto comprovado | Nenhuma exclusão. Stubs vazios e scripts antigos sem proveniência suficiente continuam preservados. |

Há imports indiretos importantes: `backend/local_routes.py` usa os modelos de `backend/persistence/leads.py`; o BFF usa `web/src/lib/auth/server.ts`; `SessionGate` importa o cliente de autenticação; o proxy ainda possui o ramo SaaS. A ausência de login em runtime não torna esses módulos, nem seus pacotes, removíveis nesta limpeza.

As refs locais `main`, `origin` e `origin/main` apontavam para `0276f57`. A consulta ao histórico alcançável dos módulos SaaS e migrations atuais não encontrou commits; eles estão fora do índice. Portanto, **não há ponto Git seguro para remover a versão SaaS atual**. Antes de um lote futuro, o operador deve revisar e criar manualmente um commit/ponto de recuperação que inclua fontes, migrations, testes e documentação. Depois disso, uma eventual retirada da árvore ativa deve ser planejada separadamente e cobrir os imports compartilhados. Nenhum lote de remoção SaaS foi executado.

## Ignore e índice

As regras foram centralizadas no `.gitignore` da raiz; os arquivos de `backend/` e `web/` apontam para ele. Categorias cobertas: ambientes Python, bytecode, pytest/cobertura, Next/Node, testes de frontend, build/distribuição, ambientes privados, certificados privados, SQLite/WAL/SHM, dumps/backups, exportações comerciais, QA temporário, ferramentas SaaS geradas e arquivos do sistema operacional.

Exemplos de ambiente e fixtures sintéticas explícitas continuam versionáveis. Não há regras para ignorar `backend/persistence`, `web/src/lib/auth`, `supabase/migrations`, documentação de arquitetura ou testes. Foram verificadas 32 combinações de caminhos; não restaram arquivos do índice abrangidos pelas regras de ignore, nem regras textuais duplicadas.

Foi usado `git rm --cached` somente nos oito arquivos dos dois protótipos gerados que estavam em `prototypes/` (quatro por protótipo: `css/style.css`, `index.html`, `js/script.js`, `prototype.json`). Cada caminho estava sem alterações pendentes e foi conferido individualmente. Os arquivos físicos continuam intactos e ignorados. `templates/` e o gerador de protótipos permanecem versionáveis. Os `D` correspondentes no `git status` indicam **remoção do índice**, não perda dos arquivos no disco. Essa mudança está staged; nenhum outro arquivo foi adicionado ao índice pela tarefa.

## Validação

| Verificação | Resultado |
| --- | --- |
| Python: núcleo/desktop e backend local/unitário | **1.197 passaram** |
| Node: contratos, BFF, autenticação legada, modo local e WhatsApp manual | **22 passaram** |
| TypeScript | Passou |
| ESLint | Passou, zero avisos |
| Build Next.js de produção | Passou, cópia isolada sem `.env` |
| Navegador / Edge headless | Passou, zero erros JavaScript |
| Regras de ignore | 32 verificações passaram |
| Integridade de fontes e dados privados | Sem alterações inesperadas |

O navegador verificou Dashboard direto sem login, criação de lead, Pipeline, Meu Dia, SDR, preferências SQLite e Google Places simulado com CSV/XLSX. A suíte Python cobriu também follow-ups, histórico, geração Groq simulada, revisão/regeneração, persistência após reinício e TLS. Não houve chamada real ao Google, Groq ou Supabase nesta limpeza.

O build foi executado com `next build --webpack` em `temp/local-cleanup-build-20261026`, sem copiar ambientes privados. Webpack permite reutilizar dependências por junction sem que Turbopack rejeite a resolução fora da cópia; o build ativo do usuário foi preservado. Os processos de teste em 127.0.0.1:8142/3142 foram encerrados após a validação.

Seis suítes de integração dependentes do PostgreSQL efêmero foram excluídas: `test_auth_schema_acl`, `test_phase31_postgres`, `test_phase32_writes`, `test_phase32_team`, `test_prospecting_batch` e `test_stamp_claims_migration`. Não foi iniciado PostgreSQL nem executada migration. Os testes Python usaram o harness offline com bloqueio de sockets/DNS externos, dependências dos ambientes virtuais existentes e ajuste de ACL apenas nos temporários do pytest. macOS teve seus comandos revisados, sem execução em máquina macOS.

## Riscos e pendências

1. **Credencial histórica:** uma chave Google Places foi encontrada em `.env.example` no commit `79e1ff9953` e coincide com a configuração local atual. Nenhum valor foi exibido ou alterado. A chave deve ser tratada como exposta e revisada/rotacionada pelo operador. A limpeza não remove segredos do histórico e não reescreveu commits. Não foi encontrada credencial privada configurada nos arquivos atualmente rastreados da árvore de trabalho; isso não substitui uma auditoria forense de todo o histórico.
2. Saídas comerciais retiradas do índice ainda existem em commits anteriores. A remoção do índice evita novos snapshots, sem apagar o histórico.
3. Criar manualmente um ponto de recuperação do trabalho SaaS e local pendente antes de qualquer remoção de código.
4. Builds ativos, ambientes instalados e artefatos antigos ambíguos permanecem como candidatos para uma limpeza futura com proveniência/uso comprovados.
5. O aviso de depreciação Starlette/httpx da suíte continua informativo e não causou falhas.

Nenhuma funcionalidade de negócio foi refatorada. O [README principal](../../README.md) documenta requisitos, clonagem, dependências, ambientes, execução, SQLite, integrações e problemas comuns; a documentação desktop antiga permanece identificada como histórica.
