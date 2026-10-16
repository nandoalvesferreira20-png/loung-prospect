# Redesign desktop e abertura manual do WhatsApp

## Arquitetura preservada

`main.py` abre `LoungLeadsApp` em `app.py`. A aplicação usa CustomTkinter;
Carteira e Meu Dia usam tabelas ttk. Sidebar, cabeçalhos, campos, botões,
indicadores e tabelas continuam em `ui/components.py` e `ui/theme.py`.
`ui/settings.py` está vazio, sem tela ativa adicional.

O SDR usa `SalesWorkspacePage` → `SalesPanel` → `SalesAgent`. Mensagens e
revisões continuam em `OutreachRepository`, no banco existente. Consentimento
e status continuam em `ContactService`. Nenhuma migração ou alteração de
schema faz parte desta mudança.

## Diagnóstico do botão

O callback estava conectado, consultava o ID correto e já lia o texto atual
do editor. Não foi reproduzido um defeito de URL para um lead autorizado com
telefone válido. Não é possível atribuir toda falha relatada a uma causa única
sem reproduzir a associação de navegador no Windows do usuário.

Foram identificados e tratados problemas concretos:

- O botão era desabilitado por validação, mas a explicação ficava no formulário
  de consentimento recolhido. A explicação agora fica visível no editor.
- Um WhatsApp contendo somente espaços impedia usar o telefone válido do lead.
  Agora esse valor vazio usa o telefone, inclusive ao registrar consentimento.
- Telefones formatados com espaço não separável eram rejeitados; espaços de
  formatação agora são aceitos sem inserir dígitos.
- A falha do navegador tinha apenas mensagem genérica, sem recuperação.
  Agora existe Copiar link e feedback específico de abertura não confirmada.
- `webbrowser.open` era síncrono no callback. Agora roda em worker isolado.

## Comportamento

Abrir WhatsApp e Copiar link reconsultam o lead/consentimento e leem
`message.get("1.0", "end-1c")`, incluindo edições não salvas. Ambos preservam
recusa, revogação, Não contatar e autorização vinculada ao número atual.
Texto vazio é rejeitado. Telefones brasileiros recebem 55 somente quando
necessário. Números internacionais explicitamente informados com + são
preservados; não há adivinhação de DDI, DDD ou nono dígito.

A URL usa `https://wa.me/{numero}?` e `urlencode({"text": mensagem})`.
O navegador é solicitado por `webbrowser.open(url, new=2)`. A interface recebe
o resultado por fila, somente na thread Tk. Após dez segundos sem resposta,
oferece recuperação; a chamada nativa já iniciada não pode ser cancelada e
pode terminar depois. Retorno True confirma apenas que o sistema aceitou a
abertura, não que o WhatsApp carregou nem que o número tem conta.

Nenhuma mensagem é enviada e nenhum status, consentimento ou histórico é
alterado por abrir/copiar. Copiar link revalida os dados em vez de reutilizar
uma URL antiga. URLs/textos privados não são registrados nos logs.

## Telas

- Visão Geral: indicadores reais, ações, leads recentes, segmentos,
  oportunidades e acesso ao SDR; leitura/agregação em worker.
- Buscar Leads: formulário em duas colunas, ação principal, progresso,
  cancelamento e resultados preservados; rolagem vertical em janelas menores.
- Carteira: filtros em superfície compartilhada, linhas mais legíveis e
  colunas secundárias recolhidas quando a largura é menor que 980 pixels.
  Todos os dados continuam acessíveis nos detalhes.
- Busca Legada: formulário consistente e rolável; callbacks do scraper agora
  entregam eventos por fila, sem chamar métodos Tk em threads secundárias.
- Meu Dia: central de atividades com dados existentes e tabela adaptável.
- SDR: duas colunas, paleta compartilhada, editor ampliado, CTA azul,
  informações de contato completas e explicação de consentimento visível.
- Prototype Studio: etapas de dados e escolha do template, campos e ações
  compartilhados. Nenhuma nova integração.
- Detalhes, Comercial, Histórico, Abordagem e SDR IA herdam os mesmos tokens.

Navegar novamente para a tela ativa não recria seus widgets. Páginas roláveis
são identificadas pelo objeto lógico, não pelo frame interno do CustomTkinter.
Buscas em andamento pedem encerramento antes de sair; alterações de
acompanhamento no SDR também podem impedir descarte acidental.
Paginação, wrapping com debounce e descarte de editores limpos foram mantidos.

## Verificação

Resultado desta etapa: **893 testes passando**, compileall sem erros e
`git diff --check` sem erros de whitespace. O teste desktop completou 14
combinações de tela/resolução e as abas de detalhes, sem erros de callback.
O SDR completou três ciclos com 1.000 leads: carregamentos de 1,391, 1,709 e
1,761 segundos. O maior intervalo entre callbacks do roteiro foi 3,696 s
(inclui múltiplas seleções e salvamentos no mesmo callback); isso não é uma
garantia de latência máxima de cada interação.

```powershell
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe -m compileall -q app.py core ui scripts tests
git diff --check
.venv\Scripts\python.exe scripts/check_desktop_gui.py
.venv\Scripts\python.exe scripts/check_sdr_gui.py --rows 1000
```

O roteiro desktop cria banco temporário e navega em sete telas, nas dimensões
1280×760 e 1050×650. Confere abas dos detalhes, edição não salva, URL, retorno
de falha do navegador, clipboard e preservação dos leads. `--show` exibe a
janela; sem essa opção ela fica transparente. Navegador e APIs são simulados.

A captura de tela nativa neste ambiente falhou com “Identificador inválido”.
Os testes de widgets e callbacks não substituem aprovação visual. Não houve
teste real de Google, Groq ou da associação do navegador padrão nesta etapa.

## Validação manual no Windows

1. Abrir o aplicativo em 1280×760 e 1050×650; percorrer as telas e conferir
   contraste, nomes extensos, rolagem, tabelas e ações.
2. Selecionar no SDR um lead com telefone válido e autorização já registrada
   para esse número. Conferir a orientação visível caso o botão esteja bloqueado.
3. Gerar ou carregar a mensagem, editar incluindo acentos e quebra de linha,
   sem salvar. Abrir WhatsApp e conferir número e texto. Não enviar no teste.
4. Conferir que status e último contato não mudaram. Testar Copiar link.
5. Com um registro sintético recusado/Não contatar, confirmar que abrir e copiar
   permanecem bloqueados; não conceder consentimento fictício a lead real.
6. Repetir SDR → Dashboard → SDR, filtros e seleção. Confirmar preservação de
   rascunhos e aviso antes de descartar alterações.
7. Validar as integrações reais Google/Groq somente por ação explícita, e conferir
   exportação, geração de protótipo e registros existentes na operação habitual.

## Arquivos desta etapa

- `app.py`: referência à página lógica e navegação sem reconstrução da tela ativa.
- `core/sales/contact.py`: espaços de formatação e fallback de WhatsApp vazio.
- `ui/browser_action.py` (novo): abertura assíncrona e retorno por fila.
- `ui/sales_workspace.py`, `ui/sales_panel.py`: CTA, recuperação, editor e proteção de edições.
- `ui/theme.py`, `ui/components.py`, `ui/sidebar.py`: identidade e componentes compartilhados.
- `ui/dashboard.py`, `ui/presentation.py`: projeções reais e carregamento em worker.
- `ui/home.py`, `ui/places_search.py`: formulários roláveis e proteção de busca ativa.
- `ui/lead_workspace.py`, `ui/my_day.py`: superfícies e tabelas adaptáveis.
- `ui/prototype_studio.py`: organização em etapas.
- `tests/test_desktop_redesign.py` (novo), `tests/test_sales_workspace.py`,
  `tests/test_ui_qualification.py`: regressões e adequação dos doubles de teste.
- `scripts/check_desktop_gui.py` (novo): teste gráfico offline.
- Este documento (novo).

O workspace já continha mudanças de etapas anteriores; elas foram preservadas.
O diff geral do Git inclui essas mudanças e não representa apenas esta entrega.
