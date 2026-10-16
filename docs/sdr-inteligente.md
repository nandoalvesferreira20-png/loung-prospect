# SDR Inteligente

## Painel inline e configuração Groq

O SDR agora usa duas colunas (aproximadamente 40/60), lista de empresas com seleção
por clique, rolagem vertical independente e editor no próprio painel. Não abre
uma janela adicional. Consentimento/status e histórico podem ser expandidos no
painel direito. Os indicadores vêm dos registros: total, rascunhos aguardando
revisão, contatados, interessados e reuniões (incluindo o status legado).

Cada lead mantém seu editor em memória enquanto a página está aberta. Trocar
leads não descarta alterações nem dispara IA. A resposta em background atualiza
somente o editor que a solicitou; não troca a seleção atual. Ao sair da página ou
fechar a aplicação, há confirmação para descartar mensagens não salvas.

A configuração é carregada de `Path(__file__).resolve().parents[2] / '.env'`
no loader compartilhado, antes da criação de clientes, sem depender do diretório
de execução. `override=False` preserva variáveis já exportadas. Não altera o `.env`.
Se `AI_PROVIDER` estiver ausente/vazio e `GROQ_API_KEY` estiver preenchida, a factory
seleciona Groq. Uma escolha explícita de OpenAI/Ollama continua sendo respeitada.
Groq consulta exclusivamente `GROQ_API_KEY`, `GROQ_MODEL` e `GROQ_TIMEOUT`.

O indicador inicial é **Groq não verificada**, ou **Groq não configurada** se faltar
configuração. **Testar Groq** faz uma consulta autenticada ao modelo configurado,
sem gerar texto ou enviar leads. Só uma resposta bem-sucedida dessa consulta ou
uma geração válida torna o indicador **Groq conectada**. Falhas mostram **Erro de
conexão**. Esse indicador representa o último teste, não monitora continuamente.

Validação desta revisão: teste autenticado real, geração com dados fictícios e
uma geração com os três campos expressamente autorizados do lead #306; nenhuma
resposta foi salva e nenhum contato foi aberto/enviado. Widgets reais foram
verificados em 1050×650, 1280×760 e 1600×900 lógicos, respeitando o escalonamento e
os limites físicos da tela do Windows. Google foi verificado somente pela suíte
offline; não foi executada uma busca real adicional.

## Arquitetura preservada

A busca Google continua em `core/providers/google_places.py`, orquestrada por
`core/prospecting/service.py` (qualificação e deduplicação antes de persistir).
Os leads ficam no SQLite existente, por padrão `data/loung_prospect.db`.
`LeadRepository.create_lead_if_new` já prioriza provider + Place ID; o SDR usa o ID
local dessa mesma linha, sem reimportar ou duplicar empresas. A busca Playwright
legada, cancelamento e exportação pandas/openpyxl em `core/exporter.py` não mudam.

A nova seção CustomTkinter reutiliza `SalesAgent`, `SalesPanel` e a tabela
`outreach`. A integração Groq implementa o mesmo contrato dos providers OpenAI
e Ollama. A geração segue na thread/fila existente; abrir a seção ou consultar
o histórico não chama a IA. Não há chamadas de IA na coleta.

## Instalar e configurar

Na raiz do projeto, com a venv ativada:

```powershell
python -m pip install -r requirements.txt
```

O SDK oficial `groq>=0.31,<1` é a única dependência direta nova. Validado com
0.37.1. Reutilizamos python-dotenv. Configure o `.env` local, ignorado pelo Git:

```dotenv
AI_PROVIDER=groq
GROQ_API_KEY=
GROQ_MODEL=
GROQ_TIMEOUT=60
```

Preencha a chave localmente e o identificador de um modelo de texto disponível
em sua conta com suporte a JSON Object Mode. Não há modelo escolhido
automaticamente nem chamada de descoberta de modelos. Variáveis do ambiente
têm precedência sobre `.env`. OpenAI e Ollama continuam selecionáveis por
`AI_PROVIDER`; não há fallback automático entre eles.

```powershell
python main.py
```

Abra **SDR Inteligente**, filtre por empresa/segmento/status e abra um lead.
O detalhe tem abas **Mensagem**, **Dados do lead** e **Histórico**. O fluxo principal
é selecionar o lead, gerar/revisar a mensagem e abrir o WhatsApp.

## Teste operacional da Groq (manual, consome tokens)

1. Configure as variáveis acima.
2. Selecione apenas um lead sem recusa de contato.
3. Clique em **Gerar com IA** e aguarde o feedback. A configuração existente da Groq é reutilizada.
4. Revise o texto, ângulo e confiança; nenhuma mensagem foi enviada.
5. Reabra o lead: o texto salvo deve reaparecer sem nova chamada à Groq.

Uma geração faz uma chamada ao SDK, com `max_retries=0`, timeout configurável
(até 300s) e saída limitada a 1600 tokens. O SDK usa
`https://api.groq.com/openai/v1/chat/completions` com `response_format=json_object`.
Autenticação, 429, timeout, conexão e resposta inválida têm mensagens próprias,
sem exibir credenciais, body ou headers. Não habilite logs DEBUG do SDK/HTTP
para uso com dados reais. Os logs da aplicação registram somente provider e
resultado/configuração, não prompts ou leads.

Referências: [SDK oficial](https://github.com/groq/groq-python),
[geração de texto](https://console.groq.com/docs/text-chat) e
[JSON mode](https://console.groq.com/docs/structured-outputs).

## Mensagens e revisão

O seletor **Contato provável** sugere Recepção/equipe, Contato direto ou
Indefinido pelo nicho e permite ajuste manual salvo por lead. A próxima geração
usa essa escolha sem substituir rascunhos anteriores. Regras, casos ambíguos e
testes estão em [Abordagens por contato provável](sdr-contact-routing.md).

O prompt pede português natural, 250–450 caracteres preferenciais, uma ideia
relevante e pergunta curta, sem alegar auditoria, ausência de site ou fatos não
comprovados. O limite estrutural existente de 1200 caracteres foi preservado.
Telefone, email e notas comerciais não compõem a evidência da geração.
Oportunidade é uma hipótese, não um problema comprovado.

**Gerar com IA** cria o primeiro rascunho; **Abrir rascunho salvo** recupera uma
mensagem existente sem consumir IA. **Mais ações → Nova versão com IA** é uma
ação explícita, aceita um motivo de até 500 caracteres e envia as cinco últimas
versões como contexto para evitar repetição. O motivo não sobrepõe as regras do
prompt. Uma repetição textual de versão já salva é rejeitada sem retry.
Similaridade semântica e factualidade ainda exigem revisão humana.

Editar/salvar e aprovar preservam o texto anterior em `outreach_revisions`.
Versões aprovadas continuam imutáveis. Gerações anteriores, revisões, datas e
provider/modelo ficam no mesmo banco. Cancelar uma versão não representa recusa
do lead. Para recusa no SDR, registre **Não contatar**; recusas e revogações antigas
continuam preservadas.

A UI confirma descarte de alterações não salvas ao regenerar, trocar versão ou
fechar o detalhe. Fechar durante geração não aborta a requisição já iniciada;
ela pode terminar e salvar um rascunho. Nunca aprova ou envia automaticamente.

## Abertura manual do WhatsApp

O seletor **Abrir WhatsApp com** permite usar o navegador padrão, Microsoft Edge
ou Google Chrome. A escolha é salva por usuário e restaurada ao reabrir o sistema.
Se o navegador escolhido não estiver disponível, a tela oferece usar o padrão,
sem alterar a preferência. Veja [detalhes e validação](sdr-browser-preference.md).

O SDR não pede autorização, origem ou data para abrir uma conversa. Os campos
antigos continuam no banco e não são alterados ao abrir o link ou salvar o
acompanhamento comercial. A ausência ou incompletude desses campos não bloqueia
a abertura. Uma mudança de telefone usa o número atual, sem exigir novo cadastro.

**Abrir WhatsApp** fica desabilitado sem telefone válido, sem mensagem, durante
geração/abertura ou diante de recusa explícita/Não contatar.
O serviço reconsulta o banco ao clicar, não confia no estado visual do botão.
Usa o texto atual da aba Mensagem, com URL encoding, e apenas abre `wa.me` no
navegador. Não usa Playwright, não clica em Enviar nem altera status/data de contato.
O usuário registra **Contato realizado** e sua data manualmente, além de responsável e notas.

Números brasileiros com DDD válido recebem 55 quando necessário; números com
55 não são duplicados. Internacional deve conter `+DDI`. Não adivinha DDD,
prefixo de operadora, ramal ou nono dígito. Validação é sintática: não confirma
titularidade nem existência de conta WhatsApp.

Uma recusa ativa `do_not_contact`, bloqueando novas gerações e abertura mesmo
se outra tela alterar o status do lead. Não há reativação após recusa nesta versão.
Pode consultar/copiar o histórico existente; não existe disparo em massa.

## Persistência, status e indicadores

Migrações são aditivas/idempotentes: `whatsapp_consent`, `consent_source`,
`consent_at`, `consent_number`, `do_not_contact` em leads; tabela
`outreach_revisions` para textos anteriores às edições e `revisado_em` em outreach
para a data da última revisão. Não se alteram dados
legados nem se inicializa o banco real durante os testes.

Status comercial, responsável, notas e último contato reutilizam campos existentes.
Mudanças comerciais manuais são auditadas em `lead_interactions`, na mesma
transação da atualização. Etapa comercial e estado do rascunho são apresentados
separadamente. O salvamento do SDR não exige nem sobrescreve a autorização legada.

Indicadores contam leads únicos: cadastrados, com rascunho ativo, com última
versão revisada, com data de contato registrada e interessados. A listagem usa
o último rascunho não cancelado. Clique em atualizar após alterações externas.

## Verificação offline

```powershell
python -m pytest
python -m compileall -q core ui scripts tests app.py
git diff --check
```

Testes usam SQLite temporário, mocks do navegador e HTTP MockTransport do SDK
oficial. Não dependem de chave, conta, rede ou Ollama. Qualidade real do texto,
disponibilidade do modelo, latência e aparência na máquina do operador precisam
de validação manual; nenhuma API paga foi chamada na implementação.
