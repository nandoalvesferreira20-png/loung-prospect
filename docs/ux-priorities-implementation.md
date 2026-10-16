# Melhorias prioritárias de UX/UI — 15/10/2026

## Comportamentos implementados

1. **Etapas comerciais compartilhadas.** SDR, Carteira e Meu Dia usam o vocabulário de `core/commercial/values.py`. Valores antigos são reconhecidos na apresentação, filtros e indicadores: `Contatado` → `Contato realizado`, `Respondeu` → `Em conversa`, `Reunião`/`Reunião marcada` → `Reunião agendada`, `Não interessado` → `Sem interesse`, `Novo Lead` → `Novo`. Os antigos estados de preparação `Mensagem gerada`/`Revisado` são apresentados comercialmente como `Novo`; o estado atual do rascunho de IA aparece separadamente nos cards do SDR. `Interessado` e `Não contatar` continuam disponíveis. Valores personalizados são preservados. Não há migração que regrave os status existentes: a normalização de gravação ocorre quando o usuário salva explicitamente o acompanhamento. O repositório genérico continua aceitando/importando valores legados.
2. **Proteção de edição.** Fechar o detalhe, sair da Carteira com um detalhe aberto ou substituir uma mensagem pendente oferece Salvar, Descartar alterações e Continuar editando. Os dados comerciais incluem observações, responsável, etapa, canal, próxima ação e próximo contato. Falha de salvamento impede o prosseguimento. Na troca de rascunho ou geração de IA, a versão humana pode ser salva primeiro. Mensagens por modelo ganham rascunho persistente separado do histórico de IA.
3. **Seleção e abertura separadas.** A Carteira não abre modal ao selecionar uma linha. Abrir lead, Enter ou duplo clique abrem os detalhes, seguindo o padrão do Meu Dia.
4. **Carteira compacta.** Empresa, Etapa, Próximo contato e Prioridade são as primeiras colunas, com larguras úteis preservadas. Score, Cidade, Segmento e Responsável continuam acessíveis por rolagem horizontal. O componente compartilhado não oculta mais colunas ao reduzir a janela, inclusive no Meu Dia.
5. **Ações de abordagem explícitas.** Abas Por modelo e Com IA. Ações Gerar por modelo, Nova versão por modelo, Salvar rascunho, Gerar com IA, Abrir rascunho salvo, Nova versão com IA, Salvar edição, Aprovar versão e Descartar versão. Abrir abordagem com IA apenas abre o editor; a geração depende de ação explícita. Aprovação e salvamento não enviam mensagens.

## Persistência

A inicialização do esquema acrescenta somente a tabela `template_drafts`, com um rascunho por lead e seus seletores de canal, objetivo e tom. Não altera ou remove registros preexistentes. O salvamento por modelo não modifica os dados comerciais, o consentimento ou o histórico de IA. Rascunhos não salvos continuam transitórios, protegidos pela confirmação ao sair ou substituir.

## Arquivos alterados nesta implementação

O workspace já tinha alterações anteriores. A lista abaixo se refere ao trabalho desta etapa, e não a todos os arquivos exibidos por `git status`.

| Área | Arquivos |
| --- | --- |
| Etapas e indicadores | `core/commercial/values.py`, `core/commercial/day.py`, `core/sales/contact.py`, `ui/lead_workspace_logic.py`, `ui/sales_workspace_logic.py`, `ui/commercial_logic.py`, `ui/presentation.py` |
| Rascunhos por modelo | `core/database/schema.py`, `core/database/template_draft_repository.py` (novo), `ui/outreach_panel.py` |
| Proteção e ações | `ui/pending_edits.py` (novo), `ui/commercial_panel.py`, `ui/sales_panel.py`, `ui/lead_workspace.py`, `ui/sales_workspace.py` |
| Tabelas e Meu Dia | `ui/components.py`, `ui/my_day.py` |
| Testes | `tests/test_commercial.py`, `tests/test_sales_contact.py`, `tests/test_sales_workspace.py`, `tests/test_outreach.py`, `tests/test_priority_ux.py` (novo) |
| Verificadores | `scripts/check_desktop_gui.py`, `scripts/check_priority_gui.py` (novo) |
| Relatório | `docs/ux-priorities-implementation.md` (novo) |

## Comandos e resultados

Executados a partir da raiz do projeto:

```powershell
# Primeira rodada direcionada: identificou cinco testes que precisavam acompanhar
# as novas opções de etapa e os novos contratos de confirmação; corrigidos.
.\.venv\Scripts\python.exe -B -m pytest tests/test_commercial.py tests/test_commercial_ui.py tests/test_lead_workspace.py tests/test_sales_contact.py tests/test_sales_workspace.py tests/test_sales_redesign.py tests/test_desktop_redesign.py tests/test_outreach.py tests/test_sales.py -q --basetemp=tmp/pytest-ux-priority

# Suíte completa intermediária: 918 passed.
.\.venv\Scripts\python.exe -B -m pytest -q --basetemp=tmp/pytest-ux-priority-full

# Suíte completa final, incluindo falha ao salvar: 919 passed in 21.64s.
.\.venv\Scripts\python.exe -B -m pytest -q --basetemp=tmp/pytest-ux-priority-final

# 14 combinações de tela/resolução, errors [].
.\.venv\Scripts\python.exe -B scripts/check_desktop_gui.py

# Três ciclos com 197 leads sintéticos, errors [].
.\.venv\Scripts\python.exe -B scripts/check_sdr_gui.py --rows 197

# Passou: seleção/Enter, abertura pelo Meu Dia, três decisões, persistência
# comercial/modelo/IA, bloqueio por data inválida e tabela em dois tamanhos.
.\.venv\Scripts\python.exe -B scripts/check_priority_gui.py

# Sem erros de whitespace; Git emitiu avisos de conversão LF/CRLF.
git diff --check
```

O verificador prioritário foi executado novamente após acrescentar o caso de data inválida e passou. Ele também aciona os três botões do modal real de confirmação. Os testes de SQLite usam bancos temporários; as integrações externas são bloqueadas ou simuladas. Não foram realizadas buscas, chamadas a APIs, abertura de WhatsApp real ou alterações nos leads reais. A aplicação normal não foi iniciada contra a base de produção durante esta implementação.

## Limites da validação

Os verificadores constroem widgets Tk reais e exercitam eventos, persistência e geometria em 1280×760 e 1050×650. Não substituem uma inspeção visual por captura, testes com leitor de tela ou verificação de escalas de DPI diferentes. Nenhuma chamada ao provedor real foi feita, conforme solicitado; esse caminho foi validado com os testes e os provedores simulados existentes.
