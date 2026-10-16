# SDR Inteligente — fluxo simplificado

## Implementação

O fluxo principal é **selecionar um lead → gerar/revisar a mensagem → abrir o WhatsApp**.
A mensagem ocupa a área central. Gerar/abrir rascunho, salvar edição e copiar
ficam visíveis; nova versão, aprovação, descarte e motivo opcional ficam em
**Mais ações**. A ação azul **Abrir WhatsApp** fica no rodapé, com feedback visível.
Dados do lead e histórico continuam em abas secundárias; não existe botão ou
formulário de consentimento no SDR.

## Causa e correção

O botão era bloqueado por `whatsapp_url`, que exigia autorização, origem,
data e correspondência do número com a autorização anterior. Essas verificações
foram removidas da construção/abertura do link. O SDR também não exige mais salvar
esses campos para habilitar a ação.

A normalização existente acrescenta 55 aos números brasileiros com DDD quando
necessário e aceita números internacionais explícitos com +DDI. `urlencode`
preserva acentos, espaços, símbolos e quebras de linha. A abertura usa o telefone
atual e o texto atual do editor, inclusive edições ainda não salvas. O navegador
é solicitado em thread, sem envio automático e sem marcar contato realizado.

Continuam os avisos de telefone ausente/inválido, mensagem vazia, versão
descartada, geração em andamento e falha do navegador. Restrições explícitas
de recusa/revogação e Não contatar continuam respeitadas; falta de cadastro
de autorização não é uma restrição.

## Compatibilidade e arquivos

Nenhum esquema foi alterado. Os dados antigos permanecem no SQLite. O novo
`ContactService.save_tracking` salva apenas acompanhamento comercial e histórico,
sem exigir ou sobrescrever origem, data, autorização ou número autorizado.
Não contatar continua persistindo a restrição. O método legado de armazenamento
permanece disponível para compatibilidade, fora do fluxo do SDR.
A integração Groq e o `.env` não foram alterados; não é necessária uma nova chave.

Arquivos alterados nesta etapa:

- `core/sales/contact.py`: link sem exigência de autorização e salvamento comercial separado.
- `ui/sales_workspace.py`: campos removidos, aba Dados do lead, resumo do fluxo e CTA destacado.
- `ui/sales_panel.py`: ações principais simplificadas e opções secundárias em Mais ações.
- `tests/test_sales_contact.py`, `tests/test_desktop_redesign.py`, `tests/test_sales_workspace.py`,
  `tests/test_sdr_workspace_redesign.py`: novo contrato de abertura, preservação dos campos e restrições explícitas.
- `scripts/check_sdr_redesign_gui.py`, `scripts/check_desktop_gui.py`: cenários sem cadastro de autorização.
- `docs/sdr-inteligente.md`, `docs/sdr-redesign-validation.md`, `docs/sdr-simple-flow.md`: documentação atualizada.

## Validação offline

```powershell
.\.venv\Scripts\python.exe -B -m pytest -q --basetemp=tmp/pytest-sdr-simple
.\.venv\Scripts\python.exe -B scripts/check_sdr_redesign_gui.py
.\.venv\Scripts\python.exe -B scripts/check_desktop_gui.py
.\.venv\Scripts\python.exe -B scripts/check_sdr_gui.py --rows 197
.\.venv\Scripts\python.exe -B scripts/check_priority_gui.py
.\.venv\Scripts\python.exe -B -m pytest tests/test_sdr_workspace_redesign.py tests/test_sales_contact.py tests/test_sales_workspace.py tests/test_desktop_redesign.py -q --basetemp=tmp/pytest-sdr-simple-final
git diff --check
```

A suíte completa passou com **933 testes**. O novo verificador passou em
**1050×650, 1280×760 e 1440×900**, incluindo teclado, abertura sem autorização,
texto com acentos e quebra de linha, edição/cópia, geração simulada, campos
ausentes, falha do navegador, listas vazias e salvamento comercial sem alterar
os dados de autorização. O desktop percorreu **14 combinações**, sem erros.
O verificador SDR completou **três ciclos com 197 leads**, sem erros.
Após o ajuste final de persistência do Não contatar, **87 testes direcionados**
passaram. O verificador de proteção de edições também passou em dois tamanhos.

Os bancos são temporários e navegador/IA são simulados. Nenhum lead real foi
alterado e nenhuma conversa ou chamada externa foi aberta durante a validação.
A geometria foi verificada com Tk real; não houve inspeção por captura de tela.

## Teste manual

1. Na raiz do projeto, execute `.\.venv\Scripts\python.exe main.py`.
2. Entre em **SDR Inteligente** e selecione um lead com telefone e DDD.
3. Clique em **Gerar com IA** ou **Abrir rascunho salvo**. A geração usa a Groq
   já configurada e consome sua quota normal.
4. Revise e edite a mensagem; **Salvar edição** é opcional para abrir a conversa.
5. Clique em **Abrir WhatsApp**. Confirme que a conversa mostra o destinatário
   e o texto completos. O envio permanece manual.
6. Para testar os avisos, selecione um lead sem telefone ou apague temporariamente
   a mensagem no editor: o botão deve ficar desabilitado e explicar o motivo.
   Restaure o texto ou continue editando ao receber aviso de edição pendente.
