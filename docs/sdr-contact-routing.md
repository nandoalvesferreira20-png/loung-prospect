# Abordagens por contato provável

## Fluxo implementado

O nicho continua armazenado no campo `segmento` de `leads`. O SDR usa o
`SalesPanel`, que chama `SalesAgent` e o provedor já configurado. A integração
Groq, o SDK, o modelo configurado e a chave existente não foram alterados.

O seletor **Contato provável**, junto ao editor, apresenta Recepção/equipe,
Contato direto ou Indefinido. Sem ajuste manual, a sugestão é calculada pelo
nicho e identificada como **pelo nicho**. Ao escolher uma opção, ela é salva
imediatamente e identificada como **manual**. A classificação continua sendo
uma hipótese sobre o contato, não uma afirmação de cargo ou estrutura.

A escolha manual vale para a próxima geração. Ela não substitui a mensagem
atual nem dispara a API. Quando já existe rascunho, **Abrir rascunho salvo**
continua carregando esse texto; use **Mais ações → Nova versão com IA** para
gerar outro texto com a nova classificação. Edições e aprovações anteriores
continuam no histórico. A mensagem permanece editável e não há envio automático.

## Regras e dados enviados

`core/sales/contact_routing.py` centraliza `NICHE_RULES`, normalização, as três
opções e `CONTACT_GUIDANCE`. A normalização remove acentos, ignora caixa,
padroniza espaços/pontuação e cobre plurais e qualificadores comuns.

| Nichos | Sugestão |
| --- | --- |
| Clínicas odontológicas, médicas, estéticas e veterinárias; hospitais veterinários | Recepção/equipe |
| Restaurantes, cafeterias, academias e CrossFit | Recepção/equipe |
| Salões explicitamente médios ou grandes | Recepção/equipe |
| Corretores/advogados explicitamente autônomos ou independentes | Contato direto |
| Barbeiros, barbearias explicitamente pequenas, profissionais autônomos de estética | Contato direto |
| Personal trainers e profissionais explicitamente independentes | Contato direto |
| Salão pequeno/sem porte, barbearia sem porte, imobiliária, classificação conflitante ou nicho desconhecido | Indefinido |

Não há informação estruturada de porte no cadastro atual. Por isso, porte é
considerado apenas quando está explícito no nicho; não é deduzido do nome da
empresa, telefone, score ou avaliações. Por exemplo, `dentista` isolado não prova
que se trata de uma clínica com equipe, e fica indefinido.

O payload mantém a lista permitida de dados disponíveis e acrescenta
`tipo_contato` (`recepcao_equipe`, `contato_direto`, `indefinido`) e
`tipo_contato_origem` (`sugestao_nicho` ou `ajuste_manual`). O nicho é enviado
como `segmento` somente quando informado. Notas comerciais, telefone e email
continuam fora das evidências enviadas ao modelo.

O prompt instrui a pedir encaminhamento para recepção/equipe, a conversar de
forma objetiva com o profissional no contato direto e a perguntar de forma
neutra pela pessoa responsável no caso indefinido. Proíbe presumir cargo,
porte, estrutura, serviços ou problemas. Oportunidade interna é hipótese, e
site vazio não prova ausência. Sem dados suficientes, a abertura deve ser
neutra e não conter observações específicas inventadas.

## Persistência e compatibilidade

A inicialização adiciona somente a tabela `lead_contact_preferences`, com
`lead_id`, `contact_type` e `updated_at`. A preferência é do lead e acompanha o
mesmo SQLite da carteira. O repositório valida as três opções e a existência do
lead. Não sobrescreve campos de `leads`, mensagens ou outras preferências.

A atualização é aditiva e idempotente. A classificação automática é recalculada
na leitura; uma escolha manual prevalece. Mesmo quando há um snapshot anterior
da abordagem, a geração consulta a classificação atual. Falha de salvamento
mantém a escolha anterior e avisa na tela. Durante a geração, o seletor fica
desabilitado e volta a ser editável ao concluir ou falhar.

## Arquivos alterados nesta etapa

- `core/sales/contact_routing.py` — novo: regras e orientação centralizadas.
- `core/database/contact_preference_repository.py` — novo: ajustes por lead.
- `core/database/schema.py` — criação aditiva da tabela de preferências.
- `core/sales/prompts.py` — inclusão da orientação por contato provável.
- `core/sales/agent.py` — contexto e escolha atual enviados ao provedor existente.
- `ui/sales_panel.py` — seletor, persistência, feedback e estados de geração.
- `ui/sales_workspace.py` — atualização da classificação ao reabrir/atualizar o lead.
- `tests/test_contact_routing.py` — novo: regras, persistência, payload SDK e revisão.
- `scripts/check_sdr_redesign_gui.py` — cobertura da classificação e ajuste na UI real.
- `docs/sdr-contact-routing.md`, `docs/sdr-inteligente.md` — documentação.

## Verificação realizada

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/test_contact_routing.py tests/test_sales_groq.py -q --basetemp=tmp/pytest-contact-routing
.\.venv\Scripts\python.exe -B -m pytest -q --basetemp=tmp/pytest-routing-all
.\.venv\Scripts\python.exe -B scripts/check_sdr_redesign_gui.py
.\.venv\Scripts\python.exe -B scripts/check_desktop_gui.py
.\.venv\Scripts\python.exe -B scripts/check_sdr_gui.py --rows 197
.\.venv\Scripts\python.exe -B scripts/check_priority_gui.py
git diff --check
```

- **67 testes direcionados** passaram, incluindo chamadas pelo SDK Groq com
  HTTP MockTransport e respostas representativas para as três classificações.
- **1.008 testes da suíte completa** passaram.
- O verificador SDR passou em 1050×650, 1280×760 e 1440×900. Verifica as três
  sugestões, ajuste manual sem substituir texto, aplicação na nova geração,
  histórico preservado e restauração após recriar a tela, além dos fluxos
  existentes de WhatsApp e navegador.
- Desktop: 14 combinações sem erros. SDR: três ciclos com 197 leads sem erros.

Os testes usam SQLite temporário, respostas simuladas e navegador simulado.
Nenhum lead real foi alterado nem chamada externa foi feita. Os testes validam
o prompt, os dados enviados e o fluxo com respostas controladas; não medem a
qualidade de uma resposta real do modelo. A revisão humana continua necessária.
A geometria foi verificada com Tk, sem inspeção visual por captura.

## Como testar os cinco comportamentos manualmente

Abra `.\.venv\Scripts\python.exe main.py` e entre em SDR Inteligente. Use leads
com os seguintes valores de Segmento. Gerar/nova versão usa a Groq já configurada
e consome sua quota habitual; abrir um rascunho salvo não gera novo texto.

1. **Clínica odontológica:** confira Recepção/equipe. Gere e revise se a mensagem
   pergunta quem cuida do assunto e pede encaminhamento, sem proposta extensa.
2. **Corretor autônomo:** confira Contato direto. Gere e revise uma abertura
   objetiva ao profissional, sem tratá-lo como proprietário nem inventar carência.
3. **Nicho desconhecido:** confira Indefinido. A abertura deve perguntar de
   forma neutra com quem conversar sobre o assunto.
4. **Ajuste manual:** altere o seletor, confira que o texto atual não mudou e
   use Mais ações → Nova versão com IA. Reabra a tela/aplicação para conferir
   a escolha salva; o histórico anterior deve continuar disponível.
5. **Dados incompletos:** use um lead com apenas empresa/segmento ou sem
   segmento/site. Confira que a mensagem não afirma ausência de site, tamanho
   da equipe, serviços ou problemas não informados. Edite antes de abrir WhatsApp.
