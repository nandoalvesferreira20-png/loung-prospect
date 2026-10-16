# SDR: apresentação e componentes

Esta etapa altera apresentação, sem modificar providers, repositórios, regras,
abertura de navegador ou métodos públicos de geração/seleção/salvamento.
O workspace contém mudanças anteriores, preservadas; o diff geral inclui essas mudanças.

## Decisões

- Tokens existentes ampliados com aliases de superfície, cores semânticas,
  espaçamento de 32 px e tipografia específica. Não há cores hexadecimais
  fora de `ui/theme.py` nos módulos de UI.
- Cards de KPI, ponto de conexão, stepper, seleção com borda, badges e barra
  de feedback têm componentes pequenos e sem acesso a dados.
- Ícones locais desenhados em Canvas, com o mesmo traço em toda a sidebar.
  Não dependem de glifos instalados, Pillow, downloads ou fontes externas.
- Sidebar compactada, com marcador lateral ativo e navegação rolável.
- Lista de 360 px; painel de edição ocupa o restante. A largura mínima passa
  a 1100 px. Paginação de 12 itens e lotes de três foram preservados.
- As abas ocupam a largura do painel. Uma adaptação localizada de CTkTabview
  configura seu segmented button interno; deve ser revista em upgrades do CTk.
- Dropdown de versões mostra data de America/Sao_Paulo, com horário de verão
  histórico quando aplicável. Datas inválidas/sem fuso são identificadas, não
  reinterpretadas silenciosamente. Dados persistidos não mudam.
- Confiança é apenas formatada em percentual e cor (<50%, 50–75%, >75%).
  Não representa uma nova regra comercial nem probabilidade de venda.
- Salvar e copiar ficam junto ao editor; versões/aprovação/descarte ficam
  agrupados em “⋯ Mais ações”. A ação de WhatsApp segue fixa logo abaixo.
- Feedback de rascunho e navegador compartilha a mesma barra. Textos temporários
  expiram em oito segundos; mensagens de operação em andamento permanecem.
  Cada timer é cancelado em substituição/destruição.

## Arquivos

Criados: `ui/sdr_components.py`, `ui/sdr_formatting.py`,
`tests/test_sdr_presentation.py` e este documento.

Alterados: `ui/theme.py`, `ui/components.py`, `ui/sidebar.py`,
`ui/sales_workspace.py`, `ui/sales_panel.py`, `app.py` (largura mínima),
`tests/test_sales_redesign.py` (double de teste com stepper).

Nenhuma dependência foi adicionada. ZoneInfo usa a base de fusos já disponível
no ambiente, validada com São Paulo e uma data histórica de horário de verão.

## Validação

```powershell
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe -m compileall -q app.py ui tests
git diff --check
.venv\Scripts\python.exe scripts/check_sdr_redesign_gui.py
```

O teste gráfico usa Tk real e SQLite temporário; simula IA, navegador e
localização de executáveis. Cobre geometria em três tamanhos, foco por teclado,
seleção, edição, cópia, geração, preferência Edge/Chrome e fallback. Não faz
chamadas reais. Uma primeira execução detectou editor comprimido; a distribuição
foi corrigida, mantendo o texto e a ação principal visíveis no tamanho menor.

Os testes de apresentação cobrem fuso, preservação de registros, faixas de cor,
contraste AA da paleta, stepper e cancelamento de timer. Não substituem revisão
visual final no monitor/DPI do usuário. No app, conferir também nomes/ângulos
longos, expansão de Mais ações e feedback após copiar/salvar.
