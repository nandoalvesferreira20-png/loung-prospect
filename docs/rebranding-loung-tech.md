# Rebranding Loung Prospect — Loung Tech

Identidade aplicada ao Dashboard, Prospecção, Leads e perfil/edição, SDR Inteligente, Pipeline, Meu Dia e Configurações. Alterações de apresentação; APIs, persistência e regras comerciais preservadas. Sem commit, push ou migration.

## Auditoria

Next.js 16, React 19, Tailwind 4 e Lucide. Componentes compartilhados Card, Button, PageHeader, EmptyState e campos `.field`. Identidade anterior azul com cinzas azulados. Nenhum arquivo de logo oficial encontrado: identificação em texto Loung Prospect / LOUNG TECH, sem símbolo inventado.

O SDR existente não possui seleção de abordagem tradicional/protótipo nem campo de URL de protótipo. Esses fluxos não foram acrescentados, pois o escopo é visual. Feedback permanece nos estados inline existentes, sem introduzir infraestrutura de toasts.

## Paleta e tokens

Centralizados em `web/src/app/globals.css`:

| Uso | Valor |
| --- | --- |
| Navegação | #0A0A0A |
| Texto | #171717 |
| Divisória escura | #262626 |
| Superfícies | #FFFFFF |
| Fundo | #F5F5F5 |
| Borda | #E5E5E5 |
| Ação / texto da ação | #B8FF3B / #0A0A0A |
| Hover da ação | #A6EB2C |
| Seleção suave / borda | #F1F8E6 / #C9DFA8 |
| Texto de destaque | #365314 |
| Foco | #527521 |
| Raios de controle / painel | 6px / 8px |

Cores semânticas de erro, alerta e sucesso preservadas. Sidebar escura, itens ativos e hover consistentes, navegação aninhada destacada. Botões, cards sem sombra decorativa, cabeçalhos, campos, checkboxes, tabelas, estados vazios e modais harmonizados. Gráfico usa variáveis do tema. Editor SDR com superfície própria e revisão humana preservada.

## Responsividade e acessibilidade

Mantidos drawer móvel, tabelas com rolagem e Kanban horizontal, com seletores de etapa como alternativa ao arraste. Área principal com largura mínima controlada, identificação do usuário truncada e campos com fonte 16px no celular. Foco visível na sidebar escura, movimento reduzido e números tabulares nos indicadores e tabelas.

## Validação

- TypeScript: passou.
- ESLint, zero warnings: passou.
- Testes existentes: 23/23 passaram com `node --test --test-isolation=none scripts/auth.test.mjs scripts/prospecting.test.mjs scripts/team.test.mjs scripts/local.test.mjs`.
- `npm test` padrão bloqueado por `spawn EPERM` no sandbox; execução sem isolamento passou.
- Build de produção: passou, incluindo TypeScript e geração das páginas. A primeira tentativa foi bloqueada por `spawn EPERM`; a execução com permissão de subprocessos terminou com código 0.
- `git diff --check`: passou.
- Navegador: host indisponível e inventário nativo com timeout. Screenshots e validação visual em 1920px, 1366px, tablet e celular pendentes. Responsividade revisada no código.

## Arquivos modificados

- `web/src/app/globals.css`.
- Páginas em `web/src/app`: Dashboard (`page.tsx`), Leads, SDR, Pipeline, Configurações, equipe, atividades, loading, error e not-found.
- Componentes em `web/src/components`: app-shell, shared, activity-chart, dashboard-data, leads-table, lead-editor, prospecting-workspace, read-status e auth-form.
- Componentes em `web/src/components/ui`: button e card.
- Componentes em `web/src/components/crm`: commercial-dashboard, followup-list, lead-contact-actions e lead-profile.
- Componentes em `web/src/components/sdr`: history-panel, lead-summary e pending-message-dialog.

Prospecção, formulários de Leads e Meu Dia também recebem a identidade pelos componentes compartilhados.
