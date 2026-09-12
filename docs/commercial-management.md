# Gestão Comercial V1

Na **Carteira de Leads**, abra um lead. O modal oferece as abas **Dados**,
**Comercial** e **Histórico**, abrindo inicialmente em Comercial. Dados mantém os
campos copiáveis e os botões de abertura de links, acionados somente pelo usuário.

Em Comercial, informe status, responsável, canal preferencial, próxima ação,
próximo contato e observações. Clique em **Salvar alterações**. Próxima ação aceita
até 240 caracteres. Datas usam `dd/mm/aaaa HH:MM` no horário local do computador;
campo vazio remove o agendamento. O banco armazena UTC em ISO 8601 com offset.
O sistema não muda status antigos automaticamente; valores legados continuam
editáveis. As opções principais são Novo, Contato realizado, Em conversa,
Reunião agendada, Proposta enviada, Fechado, Não respondeu, Retornar depois,
Sem interesse e Perdido.

Em Histórico, **+ Registrar interação** permite salvar tipo, canal opcional e
descrição (inclusive vazia). O histórico é apresentado do mais recente para o
mais antigo, com ID como desempate. Marque **Atualizar também os próximos passos**
somente se quiser atualizar status, próxima ação e próximo contato junto à
interação. Sem marcar, esses campos são preservados. Responsável e observações
não são substituídos ao registrar uma interação. Alterações ainda não salvas no
formulário principal também são preservadas ao atualizar apenas o histórico.

## Persistência e APIs

A inicialização do schema adiciona, se necessário, quatro colunas TEXT em leads:
`ultimo_contato`, `proximo_contato`, `proxima_acao`, `canal_preferencial`.
As duas datas são opcionais. Nenhum registro ou status anterior é migrado.

Nova tabela `lead_interactions`:

| Campo | Tipo |
| --- | --- |
| id | INTEGER PRIMARY KEY AUTOINCREMENT |
| lead_id | INTEGER NOT NULL |
| tipo | TEXT NOT NULL |
| canal | TEXT |
| descricao | TEXT |
| created_at | TEXT NOT NULL |

Há índice por lead/data/ID. Não foi adicionada foreign key nem alterado o modo
de conexão existente: o repository valida a existência do lead na transação.
SQL externo ao aplicativo pode ignorar essa validação.

`InteractionRepository(path)` oferece `create_interaction`, `list_interactions`,
`get_last_interaction` e `count_interactions`. A API não edita nem apaga histórico.
O método direto `create_interaction` grava apenas histórico.

`CommercialService(path).register_interaction(...)` grava a interação e atualiza
`ultimo_contato` e `updated_at` com o mesmo timestamp UTC, na mesma transação.
Qualquer falha desfaz ambas as gravações. Campos opcionais omitidos são preservados;
`None` explícito limpa os opcionais. Toda interação, inclusive Observação, marca
o horário do registro como último contato nesta versão; não é prova de envio ou
entrega de mensagem. Não há lançamento retroativo nesta versão.

`LeadRepository.update_commercial_followup(...)` atualiza o formulário de forma
atômica. `mark_last_contact(...)` aceita datetime timezone-aware ou ISO com offset.
`update_details()` e as demais operações anteriores permanecem disponíveis.

## Meu Dia

Abra **🎯 Meu Dia**. Responsável vazio mostra todos; preenchido aplica comparação
exata. A referência inicia em hoje e pode ser alterada em `dd/mm/aaaa`.

- Atrasados: data local do próximo contato anterior à referência, exceto Fechado,
  Sem interesse e Perdido. Um horário anterior no mesmo dia pertence a Hoje.
- Hoje: data local igual à referência, incluindo status terminais, conforme a
  definição desta sprint.
- Novos, Reuniões e Propostas: status Novo, Reunião agendada e Proposta enviada,
  respectivamente, independentemente de agendamento.

Os blocos podem se sobrepor; a listagem mostra cada lead uma vez. A ordem é:
atrasados mais antigos, contatos de hoje por horário, demais por score decrescente;
score desempata horários e ID desempata scores. Datas são comparadas como datetime,
convertidas para o horário local. Datas inválidas ou sem offset não entram nos
contadores de agendamento e geram aviso, sem impedir a listagem por status.
A prioridade reutiliza `classify_priority` das regras existentes. Score vazio
mostra prioridade não disponível.

Use **Abrir lead na Carteira** ou duplo clique para abrir o mesmo modal.
Reabra Meu Dia ou clique em Atualizar para refletir mudanças. Não há atualização
automática à meia-noite, notificações, calendário externo ou sincronização.
Consultas reutilizam `list_leads(responsavel=...)` e montam a visão em memória;
paginação poderá ser necessária para carteiras grandes.

## Verificação offline

`python -m pytest -q`

`python -m compileall -q main.py app.py core ui scripts tests`

`git diff --check`

Os testes usam bancos temporários e mocks. Nenhuma mensagem é enviada nem busca
externa é necessária para usar ou testar a gestão comercial.
