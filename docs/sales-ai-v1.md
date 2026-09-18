# SDR de IA sem envio

Na Carteira, selecione um lead e abra a aba **SDR IA**. Clique em **Gerar abordagem
com IA**, revise o rascunho, edite e use **Salvar edição** ou **Aprovar**. Aprovar
salva exatamente o texto visível como APROVADA: não abre WhatsApp, não envia e não
registra interação nem altera status comercial. A aba Abordagem por templates
permanece disponível, sem dependência de IA.

## Configuração

### Ollama local

1. Instale e abra o Ollama.
2. No terminal, baixe explicitamente o modelo: `ollama pull gemma3:4b`.
3. Configure o `.env` (nenhuma chave é necessária neste modo):

```dotenv
AI_PROVIDER=ollama
AI_MODEL=gemma3:4b
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_TIMEOUT=120
```

4. Execute o LoungLeads normalmente (`python main.py`) e abra a aba SDR IA.
5. Gere um rascunho, revise e aprove manualmente.

A factory escolhe exclusivamente o provider configurado. Ollama usa uma chamada
HTTP `POST /api/chat`, `stream=false` e o mesmo schema JSON, prompt e evidências
da OpenAI. Não faz fallback, retry nem download de modelo. Usa biblioteca padrão,
sem SDK adicional. O timeout de socket é configurável (maior que zero, até 600s);
não é um prazo global de toda a geração. A URL aceita origem HTTP/HTTPS sem
credenciais, query ou caminho adicional; os dados são enviados a esse host.

O parser aceita JSON puro, cercado por code fence ou por texto, mas exige um único
objeto com as três chaves esperadas. Não corrige confiança fora de 0–1 nem salva
resposta inválida. Chaves duplicadas, objetos ambíguos e saídas truncadas são
rejeitados. Erros de conexão, timeout e modelo ausente chegam à tela sem body ou
headers. Somente provider/modelo são registrados em logging (nível INFO).

Referências oficiais: [Chat](https://docs.ollama.com/api/chat) e
[Structured outputs](https://docs.ollama.com/capabilities/structured-outputs).

### OpenAI (preservado)

No .env local, já ignorado pelo Git:

```dotenv
AI_PROVIDER=openai
AI_API_KEY=
AI_MODEL=
```

Preencha a chave e o identificador de um modelo disponível em sua conta que
suporte Responses API com Structured Outputs. Não foi escolhido um modelo
automaticamente; os campos vazios bloqueiam geração com erro de configuração.
Variáveis já definidas no ambiente têm precedência. Não há novas dependências.
Provider implementa protocolo SalesAIProvider; outro provider pode substituir
o adapter sem alterar serviço ou UI. Uma geração executa uma chamada, sem retry
automático, timeout 45s, limite 1600 tokens de saída, store=false e nenhuma ferramenta.
Custos dependem do modelo configurado. Nenhuma chamada real ocorreu nos testes.

Referência da integração:
https://developers.openai.com/api/docs/guides/structured-outputs

## Dados e limites

Somente empresa, segmento, cidade, URL Site, avaliação, quantidade de avaliações
e score são enviados quando presentes. Telefone, email, notas comerciais e histórico
não são enviados. Campos textuais são tratados pelo prompt como dados não confiáveis.
Site vazio não é interpretado como inexistência: a carteira não preserva toda
metadata de observação. Não reconstruímos evidência de ausência a partir do score
ou oportunidade. O prompt exige linguagem conservadora e proíbe fatos inventados.
Isso não garante factualidade de toda saída do modelo; revisão humana é necessária.
Confiança é autoavaliação do rascunho, não probabilidade de venda nem nota calibrada.

Retorno exige mensagem não vazia até 1200 caracteres, ângulo até 200 caracteres
e confiança numérica finita de 0 a 1. JSON inválido, recusa, resposta incompleta,
timeout ou HTTP inválido não criam rascunho. Erros não exibem chave, body ou headers.

## Histórico e estados

Inicialização idempotente adiciona tabela outreach e índice por lead/data, sem
alterar dados anteriores. Campos: id, lead_id, canal, mensagem, angulo, confianca,
status, criado_em, atualizado_em, aprovado_em, enviado_em, respondeu_em, provider,
model. As duas últimas colunas são adicionadas de forma idempotente; rascunhos
antigos e providers fake sem identificação permanecem com NULL. Datas são
UTC ISO 8601. Escritas usam parâmetros SQL e transações com rollback em falha.
Existência do lead é verificada antes da geração e novamente ao inserir/atualizar.

GERADA → EDITADA/APROVADA/CANCELADA; EDITADA → EDITADA/APROVADA/CANCELADA.
APROVADA e CANCELADA são imutáveis nesta versão. ENVIADA e RESPONDEU estão reservadas,
sem API de transição. Regenerar usa a fotografia dos dados desta sessão e cria
uma nova linha, preservando todas as versões, inclusive aprovadas. Após reabrir
o modal, a fotografia é refeita com dados atuais. O histórico pode ser consultado
sem chave configurada. Gerar novamente substitui a edição ainda não salva na tela.

A UI usa thread e fila para não bloquear Tk. Durante geração, ações e seleção
ficam bloqueadas. Fechar o modal não aborta HTTP em curso: ele pode terminar e
salvar GERADA, consultável ao reabrir. Nunca aprova sozinho. Não há envio, detecção
de resposta, follow-up automático ou alteração do histórico comercial.
