# Remoção definitiva do Desktop — 2026-11-03

O produto utiliza exclusivamente a interface Web local Next.js/TypeScript, FastAPI e SQLite. A CLI sem GUI foi conservada por ter funcionalidades e testes próprios. Nenhum commit ou push foi realizado.

## Recuperação e auditoria anterior às exclusões

Ponto de recuperação: `3f5a14b0440fb869b816e7043ecf9225396c9496`. Os 45 arquivos excluídos estavam rastreados e sem alterações em relação ao HEAD. As exclusões permanecem no working tree, revisáveis por `git diff`, recuperáveis do commit sem criar commits automáticos. A única modificação inicial observada foi `web/next-env.d.ts`.

O [mapa anterior à limpeza](DESKTOP_REMOVAL_MAP.json) registra estrutura rastreada, imports diretos/relativos, chamadas de importação dinâmica e caminhos removidos. A revisão de backend/core não encontrou dependência de GUI, inclusive na inicialização local, imports condicionais PostgreSQL, provedores e exportação. Os testes mistos foram inspecionados por função e por dependência de helpers.

## Estrutura anterior e resultante

| Componente | Antes | Depois |
|---|---|---|
| `web/` | Next.js + BFF | Preservado; somente textos antigos corrigidos |
| `backend/` | FastAPI e SQLite local | Preservado; novo teste impede regressão de imports GUI |
| `core/` | 63 módulos de negócio | Todos preservados sem alteração |
| `ui/` | 29 módulos GUI | Removido, incluindo cache |
| `app.py` | Aplicação CustomTkinter | Removido |
| `main.py` | CLI + abertura GUI por padrão | Somente CLI; sem argumentos mostra uso do argparse |
| `scripts/` | 4 validadores GUI e script Places | Validadores GUI removidos; script Places mantido |
| PyInstaller | `LoungLeads.spec` | Removido; artefatos ignorados |
| Dados, backups e `.env` | Locais e privados | Preservados |
| SaaS e migrations | Implementação histórica | Preservada; login não reativado |

## Arquivos removidos

- `LoungLeads.spec`
- `app.py`
- `assets/fonts`
- `docs/local/saas-env-examples/desktop.env.example`
- `scripts/check_desktop_gui.py`
- `scripts/check_priority_gui.py`
- `scripts/check_sdr_gui.py`
- `scripts/check_sdr_redesign_gui.py`
- `tests/test_commercial_ui.py`
- `tests/test_copy_field.py`
- `tests/test_lead_workspace.py`
- `tests/test_prototype_ui.py`
- `tests/test_sales_workspace.py`
- `tests/test_sdr_presentation.py`
- `tests/test_sdr_responsiveness.py`
- `tests/test_sdr_workspace_redesign.py`
- `ui/__init__.py`
- `ui/browser_action.py`
- `ui/commercial_logic.py`
- `ui/commercial_panel.py`
- `ui/components.py`
- `ui/copy_field.py`
- `ui/dashboard.py`
- `ui/dialogs.py`
- `ui/home.py`
- `ui/lead_workspace.py`
- `ui/lead_workspace_logic.py`
- `ui/my_day.py`
- `ui/outreach_panel.py`
- `ui/pending_edits.py`
- `ui/places_logic.py`
- `ui/places_search.py`
- `ui/presentation.py`
- `ui/prototype_logic.py`
- `ui/prototype_studio.py`
- `ui/responsive_text.py`
- `ui/sales_panel.py`
- `ui/sales_workspace.py`
- `ui/sales_workspace_logic.py`
- `ui/sdr_components.py`
- `ui/sdr_diagnostics.py`
- `ui/sdr_formatting.py`
- `ui/settings.py`
- `ui/sidebar.py`
- `ui/theme.py`

Além disso, removidos somente os 29 arquivos de bytecode de `ui/__pycache__/`, depois de verificar o caminho absoluto e que não era um link. Nenhum build/executável Desktop adicional foi identificado em `build/` ou `dist/`. Ambientes virtuais, dependências instaladas, caches Web utilizados pela validação, bancos, backups e exportações do usuário foram conservados.

Contagem: **45 arquivos rastreados + 29 caches = 74 arquivos removidos**. Conteúdo removido: **263,000 bytes rastreados + 302,571 bytes de cache = 565,571 bytes** (aproximadamente 552.3 KiB). Essa é a soma dos arquivos excluídos, não a redução líquida do diretório, pois relatório, mapa e saídas de testes também ocupam espaço. O histórico Git continua armazenando o código antigo.

## Módulos e dependências preservados

Todos os módulos `core/`, incluindo `database`, schema/migrations SQLite, `commercial`, `providers/google_places`, `prospecting`, `qualification`, `sales` (Groq e prompts intactos), `exporter`, `importers`, scraper, launcher de navegador, outreach e prototypes/templates. Não houve extração de regras de negócio nem alteração de contratos, deduplicação ou prompts comerciais.

Removida a dependência direta `customtkinter` de `requirements.txt`. Tkinter é da biblioteca padrão e não tinha linha de instalação. PyInstaller não constava dos manifests. Playwright permanece: `core/scraper.py`, CLI, testes e validação do navegador ainda o utilizam. Nenhuma versão de pacote foi atualizada; manifests backend/Node e lockfile permanecem intactos.

## Alterações

- GUI, validadores e testes exclusivamente GUI removidos. Casos GUI em testes mistos retirados, preservando casos de serviços, scraper, Places, CRM, SDR e persistência.
- `main.py` conserva `cli_main` e elimina `gui_main` e import de `app`.
- README principal atualizado; documentação antiga movida para `docs/desktop-history.md`, explicitamente histórica. Guias backend/Web/local/testes corrigidos.
- `.gitignore` complementado para `.spec`, `.app`, `.dmg`, `.msi`; regras existentes de SQLite, backups, exports, ambientes, logs, caches e `.env` preservadas.
- `backend/local_database.py`: somente comentário atualizado; execução/migrations não alteradas.
- Textos da interface que orientavam usar Desktop substituídos por referências à base local/regras comerciais. Valor legado `preferencia_desktop` mantido no contrato.
- `backend/tests/test_no_gui.py`: processo limpo bloqueia imports `tkinter`, `customtkinter`, `ui`, `app`, inicializa e reinicia SQLite sintético.
- `web/next-env.d.ts` já estava modificado antes do trabalho; Next o regenerou durante builds e as referências de desenvolvimento `.next/dev/types` foram recolocadas. É arquivo gerado; não foi incluído em exclusões.

## Testes antes e depois

| Verificação | Antes | Depois |
|---|---|---|
| Serviços/CLI (`tests`) | 1034 passaram, 1 falhou | **814 passaram**; redução corresponde aos casos GUI removidos |
| API completa histórica | Incompleta: aguardava PostgreSQL sintético local | Mesmo bloqueio identificado por stack; seis arquivos dependentes desse servidor excluídos somente do comando de execução |
| API independente de PostgreSQL | Referência parcial na execução completa | **163 passaram**, incluindo o novo teste sem GUI |
| API operacional SQLite (subconjunto) | Coberta parcialmente na referência | **112 passaram**: local, CRUD, CRM, Pipeline, follow-ups, Places/Groq mocks, jobs, deduplicação, CSV/XLSX e reinício |
| Node/BFF | **22 passaram** | **22 passaram** |
| TypeScript e lint | Passaram | Passaram; verificação final após textos registrada em `temp/desktop-final-*.log` |
| Build de produção | Passou | Passou; revalidação final após textos registrada em `temp/desktop-final-build.log` |
| Edge/Playwright, produção local | Não executado na referência | Dashboard sem login, criação/listagem de lead, navegação Pipeline/Meu Dia/SDR/configurações, preferências SQLite via BFF, Places mock e CSV/XLSX passaram; zero erros JS |
| Dados e ambiente | Hashes registrados antes das exclusões | **13 arquivos de dados/ambiente com hashes idênticos** |

Os 112 testes são subconjunto dos 163, não devem ser somados. Testes usam bancos temporários e fornecedores simulados. Nenhuma chamada real a Places/Groq, acesso a Supabase remoto, edição de credenciais ou escrita na base comercial foi realizada. Screenshot verificado: `temp/local-dashboard-browser.png`. Logs completos ignorados pelo Git em `temp/desktop-*.log`.

As primeiras tentativas no sandbox falharam por ausência de Playwright no ambiente backend, restrições de diretórios temporários e `spawn EPERM`. A validação foi refeita com subprocessos locais permitidos e `--basetemp` no workspace. Para serviços/CLI foi necessário usar os pacotes já instalados no ambiente raiz via `PYTHONPATH`; a API foi validada independentemente no ambiente backend, sem GUI. Não se alteraram ambientes nem credenciais.

## Regressões corrigidas e pendências

- Encontrado após a limpeza um caso GUI indireto (`test_ui_exhaustion_does_not_show_full_progress` importava helper de `test_places_ui`). Somente esse caso foi retirado; cenários comerciais do arquivo preservados. Nenhuma exclusão adicional de produção foi feita para contornar falhas.
- A falha **anterior** `test_missing_config` ocorria porque o runner injeta chave Groq sintética e o teste remove apenas variáveis OpenAI. O teste agora seleciona explicitamente `AI_PROVIDER=openai`, isolando o cenário pretendido sem mudar código de produção.
- Suíte histórica PostgreSQL depende do servidor efêmero PGlite em `127.0.0.1:55431`, ausente. Processos de teste bloqueados foram encerrados; nenhum servidor remoto foi usado. Essa parte permanece não validada nesta tarefa.
- Windows validado. macOS documentado com os comandos reais, mas não executado neste computador. Integrações externas reais não chamadas por decisão de usar mocks.
- Aviso existente: Starlette recomenda `httpx2` em vez de `httpx` no TestClient; nenhuma atualização de dependências fora do escopo foi feita.

## Estado final do Git

```text
git status --short
 M .gitignore
 D LoungLeads.spec
 M README.md
 D app.py
 D assets/fonts
 M backend/README.md
 M backend/local_database.py
 M docs/local/README.md
 D docs/local/saas-env-examples/desktop.env.example
 M main.py
 M requirements.txt
 D scripts/check_desktop_gui.py
 D scripts/check_priority_gui.py
 D scripts/check_sdr_gui.py
 D scripts/check_sdr_redesign_gui.py
 M tests/README.md
 M tests/test_browser_preferences.py
 M tests/test_commercial.py
 D tests/test_commercial_ui.py
 M tests/test_contact_routing.py
 D tests/test_copy_field.py
 M tests/test_desktop_redesign.py
 M tests/test_lead_target.py
 D tests/test_lead_workspace.py
 M tests/test_outreach.py
 M tests/test_places_neighborhood.py
 M tests/test_places_target.py
 M tests/test_places_target_sprint.py
 M tests/test_places_ui.py
 M tests/test_priority_ux.py
 M tests/test_prospecting.py
 D tests/test_prototype_ui.py
 M tests/test_sales.py
 M tests/test_sales_contact.py
 M tests/test_sales_ollama.py
 M tests/test_sales_redesign.py
 D tests/test_sales_workspace.py
 D tests/test_sdr_presentation.py
 D tests/test_sdr_responsiveness.py
 D tests/test_sdr_workspace_redesign.py
 M tests/test_ui_qualification.py
 D ui/__init__.py
 D ui/browser_action.py
 D ui/commercial_logic.py
 D ui/commercial_panel.py
 D ui/components.py
 D ui/copy_field.py
 D ui/dashboard.py
 D ui/dialogs.py
 D ui/home.py
 D ui/lead_workspace.py
 D ui/lead_workspace_logic.py
 D ui/my_day.py
 D ui/outreach_panel.py
 D ui/pending_edits.py
 D ui/places_logic.py
 D ui/places_search.py
 D ui/presentation.py
 D ui/prototype_logic.py
 D ui/prototype_studio.py
 D ui/responsive_text.py
 D ui/sales_panel.py
 D ui/sales_workspace.py
 D ui/sales_workspace_logic.py
 D ui/sdr_components.py
 D ui/sdr_diagnostics.py
 D ui/sdr_formatting.py
 D ui/settings.py
 D ui/sidebar.py
 D ui/theme.py
 M web/README.md
 M web/next-env.d.ts
 M web/src/app/configuracoes/page.tsx
 M web/src/components/crm/followup-list.tsx
 M web/src/components/crm/lead-profile.tsx
 M web/src/components/dashboard-data.tsx
 M web/src/components/leads-table.tsx
 M web/src/components/sdr/lead-summary.tsx
?? backend/tests/test_no_gui.py
?? docs/desktop-history.md
?? docs/local/DESKTOP_REMOVAL_MAP.json
?? docs/local/DESKTOP_REMOVAL_REPORT.md
```

```text
git diff --stat
 .gitignore                                       |   8 +-
 LoungLeads.spec                                  |  44 --
 README.md                                        | 681 +----------------------
 app.py                                           | 142 -----
 assets/fonts                                     |   0
 backend/README.md                                |  10 +-
 backend/local_database.py                        |   2 +-
 docs/local/README.md                             |   4 +-
 docs/local/saas-env-examples/desktop.env.example |  16 -
 main.py                                          |  18 +-
 requirements.txt                                 |   1 -
 scripts/check_desktop_gui.py                     | 141 -----
 scripts/check_priority_gui.py                    | 143 -----
 scripts/check_sdr_gui.py                         | 142 -----
 scripts/check_sdr_redesign_gui.py                | 241 --------
 tests/README.md                                  |   2 +-
 tests/test_browser_preferences.py                |  88 ---
 tests/test_commercial.py                         |  64 ---
 tests/test_commercial_ui.py                      |  51 --
 tests/test_contact_routing.py                    |  19 -
 tests/test_copy_field.py                         |  63 ---
 tests/test_desktop_redesign.py                   | 128 -----
 tests/test_lead_target.py                        |  43 --
 tests/test_lead_workspace.py                     |  72 ---
 tests/test_outreach.py                           |  63 ---
 tests/test_places_neighborhood.py                |  32 --
 tests/test_places_target.py                      |  18 -
 tests/test_places_target_sprint.py               |  10 -
 tests/test_places_ui.py                          | 396 -------------
 tests/test_priority_ux.py                        |  82 ---
 tests/test_prospecting.py                        | 150 +----
 tests/test_prototype_ui.py                       |  89 ---
 tests/test_sales.py                              |  46 +-
 tests/test_sales_contact.py                      |  15 -
 tests/test_sales_ollama.py                       |  30 -
 tests/test_sales_redesign.py                     |  53 --
 tests/test_sales_workspace.py                    |  60 --
 tests/test_sdr_presentation.py                   |  80 ---
 tests/test_sdr_responsiveness.py                 | 103 ----
 tests/test_sdr_workspace_redesign.py             | 158 ------
 tests/test_ui_qualification.py                   |  89 ---
 ui/__init__.py                                   |   0
 ui/browser_action.py                             |  58 --
 ui/commercial_logic.py                           |  94 ----
 ui/commercial_panel.py                           | 157 ------
 ui/components.py                                 | 174 ------
 ui/copy_field.py                                 |  57 --
 ui/dashboard.py                                  | 127 -----
 ui/dialogs.py                                    |  82 ---
 ui/home.py                                       | 518 -----------------
 ui/lead_workspace.py                             | 228 --------
 ui/lead_workspace_logic.py                       |  67 ---
 ui/my_day.py                                     |  69 ---
 ui/outreach_panel.py                             | 106 ----
 ui/pending_edits.py                              |  41 --
 ui/places_logic.py                               |  87 ---
 ui/places_search.py                              | 566 -------------------
 ui/presentation.py                               |  58 --
 ui/prototype_logic.py                            |  53 --
 ui/prototype_studio.py                           | 112 ----
 ui/responsive_text.py                            |  37 --
 ui/sales_panel.py                                | 337 -----------
 ui/sales_workspace.py                            | 604 --------------------
 ui/sales_workspace_logic.py                      |  40 --
 ui/sdr_components.py                             | 183 ------
 ui/sdr_diagnostics.py                            |  40 --
 ui/sdr_formatting.py                             |  35 --
 ui/settings.py                                   |  53 --
 ui/sidebar.py                                    |  53 --
 ui/theme.py                                      |  53 --
 web/README.md                                    |   8 +-
 web/next-env.d.ts                                |   4 +-
 web/src/app/configuracoes/page.tsx               |   2 +-
 web/src/components/crm/followup-list.tsx         |   2 +-
 web/src/components/crm/lead-profile.tsx          |   2 +-
 web/src/components/dashboard-data.tsx            |   4 +-
 web/src/components/leads-table.tsx               |   2 +-
 web/src/components/sdr/lead-summary.tsx          |   2 +-
 78 files changed, 40 insertions(+), 7672 deletions(-)
```

`git diff --stat` exclui os quatro arquivos novos: teste sem GUI, mapa, relatório e documentação histórica.
