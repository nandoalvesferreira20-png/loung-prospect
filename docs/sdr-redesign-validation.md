# SDR Inteligente: redesenho e WhatsApp

> Registro da etapa anterior. O fluxo atual foi simplificado e não exige cadastro
> de autorização. Consulte [SDR: fluxo simplificado](sdr-simple-flow.md).

Implementação em 15/10/2026, preservando a paleta escura/azul e os componentes existentes.

## Causa do bloqueio e investigação do link

O bloqueio mostrado é produzido por `core/sales/contact.py`: o consentimento deve estar Autorizado, ter origem e data válidas e estar vinculado ao telefone atual. Os valores são persistidos em `leads.whatsapp_consent`, `consent_source`, `consent_at`, `consent_number` e `do_not_contact`. Essa validação foi mantida, inclusive o bloqueio por recusa/revogação e por troca do número.

Não foi encontrado defeito na montagem original do link: `normalize_phone` já normalizava números brasileiros com DDD para o código 55, preservava números internacionais explícitos com +DDI e `urlencode` já codificava o texto. O caminho `ContactPanel.current_url` → `ContactService.preview_url` → `whatsapp_url` → `BrowserAction.open` foi exercitado com mensagem com acentos, espaços, &, + e quebra de linha. O navegador continua sendo solicitado por `webbrowser.open(url, new=2)` em uma thread. O código não envia mensagens automaticamente.

O problema adicional de interface era a disponibilidade calculada com uma mensagem fictícia, junto de dois botões de abertura e atualização incompleta de seus estados. Agora existe uma única ação de WhatsApp. Ela considera a mensagem atual, geração em andamento, versão descartada, autorização salva e abertura de navegador em andamento. Alterações pendentes de consentimento ou etapa impedem o uso de uma autorização anterior até o salvamento. Os requisitos são novamente verificados ao clicar.

## Tela implementada

- Cabeçalho compacto, ações Testar Groq e Atualizar leads lado a lado e indicadores em uma faixa discreta.
- Lista estreita, busca, filtros com opções explícitas de todos, limpeza, paginação, seleção e borda de foco. Setas movem o foco entre leads, Enter/Espaço selecionam e Alt+↓ abre os filtros.
- Empresa, segmento, etapa e telefone no resumo do selecionado. Estado da versão no seletor e no resumo da mensagem; estados de rascunho também aparecem na lista.
- Abas Mensagem, Dados e consentimento e Histórico. O painel inteiro não rola: só os dados extensos ou o histórico na respectiva aba.
- Mensagem com altura flexível e ações de abrir/gerar, criar versão, salvar, aprovar, descartar e copiar. O motivo opcional de regeneração é revelado pelo botão Motivo.
- Rodapé com Abrir WhatsApp, Copiar link e explicação do requisito ausente. Datas do formulário usam dd/mm/aaaa HH:MM local e são convertidas para ISO com fuso antes do salvamento.
- Mensagens para carregamento, falha de carregamento com orientação de tentar novamente, carteira vazia, filtros sem resultados, telefone ausente/inválido e ausência de rascunho.
- Anéis de foco reutilizáveis, navegação por Tab e ativação de botões por Enter/Espaço. As edições por lead continuam preservadas ao alternar entre empresas.

## Arquivos alterados nesta etapa

| Arquivo | Mudança |
| --- | --- |
| `ui/sales_workspace.py` | Estrutura da tela, navegação da lista, abas, dados/consentimento e uma única ação de WhatsApp com disponibilidade atualizada |
| `ui/sales_panel.py` | Editor compacto flexível e notificações de alteração/geração para atualizar a ação de contato |
| `ui/components.py` | Tratamento opcional de foco e teclado, aplicado ao SDR |
| `ui/sales_workspace_logic.py` | Opções explícitas de todos nos filtros |
| `core/sales/contact.py` | Orientação do consentimento, origem em branco e mensagens de telefone ausente/inválido |
| `tests/test_sales_workspace.py` | Atualização dos cenários de interface para os novos estados |
| `tests/test_desktop_redesign.py` | Atualização dos cenários de abertura e retorno do navegador |
| `tests/test_sdr_workspace_redesign.py` | Novas regressões de requisitos persistidos, autorização pendente, texto atual, versão descartada e erro de carregamento |
| `scripts/check_sdr_redesign_gui.py` | Novo verificador com Tk real, SQLite descartável, IA e navegador simulados |
| `docs/sdr-redesign-validation.md` | Este relatório |

O workspace já continha outras alterações; elas não foram revertidas.

## Validação

Comandos principais executados a partir da raiz:

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/test_sales_workspace.py tests/test_desktop_redesign.py tests/test_sales_contact.py tests/test_sales_redesign.py tests/test_sdr_responsiveness.py tests/test_priority_ux.py -q --basetemp=tmp/pytest-sdr-redesign-2
.\.venv\Scripts\python.exe -B -m pytest -q --basetemp=tmp/pytest-sdr-delivery
.\.venv\Scripts\python.exe -B scripts/check_desktop_gui.py
.\.venv\Scripts\python.exe -B scripts/check_sdr_gui.py --rows 197
.\.venv\Scripts\python.exe -B scripts/check_sdr_redesign_gui.py
.\.venv\Scripts\python.exe -B scripts/check_sdr_redesign_gui.py --show
.\.venv\Scripts\python.exe -B scripts/check_priority_gui.py
git diff --check
```

- Suíte direcionada: **118 testes passaram**.
- Suíte completa final: **935 testes passaram**, em 13,90 s.
- Verificador desktop existente: **14 combinações**, sem erros.
- Verificador SDR existente: **três ciclos com 197 leads**, sem erros na rodada final.
- Verificador prioritário existente: passou em dois tamanhos, incluindo proteção de edições e persistência dos rascunhos por modelo e IA.
- Novo verificador: passou em **1280×760, 1050×650 e 1440×900**; verifica geometria dos controles, foco/setas/Enter, mensagem vazia, consentimento ausente, preenchimento e salvamento do consentimento pela UI, telefone ausente/inválido, texto com acentos, retorno de falha do navegador, copiar, editar/salvar, geração simulada e listas vazias.

Os testes detectaram corte do rodapé na primeira versão do layout; o empacotamento foi corrigido para reservar espaço às ações e à explicação antes de dimensionar o editor. Uma primeira execução do verificador SDR existente apresentou erro de bloqueio no SQLite temporário; as execuções posteriores, incluindo a final, passaram. A suíte inicial também exigiu adaptar os mocks aos novos estados da interface.

Toda a validação usou dados temporários e integrações bloqueadas ou simuladas. Nenhum lead real foi alterado, nenhuma busca foi realizada e nenhuma API ou conversa real foi aberta. Não foi alterado o `.env`.

## Limites

A ferramenta de inspeção desktop não encontrou a janela sintética entre as janelas acessíveis. Portanto, não houve inspeção visual por captura. Os testes usam widgets Tk reais e verificam geometria e comportamento, mas não substituem revisão visual manual, leitor de tela e testes em outros níveis de DPI. A abertura real do WhatsApp e a configuração do navegador do usuário não foram testadas, conforme a restrição de chamadas externas; o link e a solicitação ao navegador foram validados com simulação.
