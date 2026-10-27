# Diagnóstico SDR / Groq — 26/10/2026

## Evidência e limite da conclusão

A chamada real autorizada posteriormente confirmou a causa do incidente: **falha de validação da cadeia TLS pelo cliente HTTP usado no Windows**, antes de qualquer resposta HTTP do Groq. A exceção foi `APIConnectionError`, causada por `ConnectError` e `SSLCertVerificationError`. Não houve resposta de autenticação, modelo ou quota; esses fatores não devem ser apontados como a causa desta tentativa.

A mensagem genérica informada pelo usuário era agravada pela perda do diagnóstico entre o SDK e a interface:

1. `GroqSalesProvider` recebia uma resposta HTTP e convertia a exceção em texto seguro, descartando status, tipo e código do provedor.
2. `SalesAgent` convertia novamente para `SalesGenerationError`.
3. `SdrService.generate` capturava qualquer exceção e devolvia o mesmo 502 genérico.
4. Assim, chave inválida, modelo indisponível, rate limit, timeout e falhas JSON ficavam indistinguíveis.

Um teste novo, executado antes da correção, reproduziu `401 invalid_api_key` simulado chegando como 502. Depois da correção, o mesmo caso retorna `503` com `X-Loung-SDR-Code: GROQ_AUTH_INVALID`, mensagem segura e log sanitizado. 401 do provedor não vira 401 de autenticação local, evitando confusão com login.

## Chamada real autorizada

Foi executada exatamente uma tentativa de `POST /openai/v1/chat/completions`, com `openai/gpt-oss-20b`, o prompt comercial existente e dados sintéticos. Retries estavam desabilitados. Nenhum acesso SQLite foi realizado e nenhum dado de lead real foi enviado.

Resultado seguro: `realRequestsAttempted=1`, `http=null`, `tlsVerificationFailed=true`, cadeia `ConnectError → ConnectError → SSLCertVerificationError`, código então emitido `GROQ_CONNECTION_FAILED`, duração aproximada 1,4 s. O diagnóstico agora classifica essa cadeia especificamente como `GROQ_TLS_FAILED`.

A correção usa `truststore.SSLContext(PROTOCOL_TLS_CLIENT)` no HTTPX do SDK Groq no Windows, mantendo `CERT_REQUIRED` e validação de hostname. É o mesmo mecanismo de confiança nativa já empregado pelo projeto para JWKS, sem depender de Supabase. Não há `verify=False`, alteração global de SSL ou instalação de certificados no sistema. macOS/Linux mantêm o cliente padrão anterior. A dependência Windows já existia no backend; foi também declarada nos requisitos da raiz para o adaptador compartilhado.

Testes locais com HTTPS demonstraram aceitação de uma cadeia explicitamente confiada apenas no cliente de teste e rejeição de certificado não confiável e hostname incorreto. **Não houve segunda chamada ao Groq após a correção**, respeitando a autorização de uma única tentativa. Portanto, autenticação/modelo/quota da conta e geração real após reiniciar ainda dependem da validação manual; a causa TLS e a correção no cliente foram verificadas sem novo consumo de API.

## Configuração observada

- `.env` existente: chave presente, sem espaços, modelo `openai/gpt-oss-20b`, SQLite e escritas habilitadas. Nenhum valor de chave foi exibido.
- No processo usado para o diagnóstico, não havia `GROQ_API_KEY`, `GROQ_MODEL` ou `GROQ_TIMEOUT` exportados sobrepondo o arquivo; também não foram encontradas essas variáveis persistidas nos escopos User/Machine.
- Isso não revela o ambiente privado de outro PowerShell já aberto. O launcher usa `override=False`: variáveis exportadas nesse terminal têm precedência, inclusive valores vazios. Um teste demonstra essa precedência.
- O loader padrão encontra `.env` na raiz. O launcher também aceita um arquivo explícito via `--env-file`; nenhuma credencial foi modificada.
- SDK Groq instalado no backend: 0.37.1. Backend e BFF em execução responderam em modo local durante as verificações somente de leitura.
- Não houve mudança de modelo. A [documentação oficial do GPT OSS 20B](https://console.groq.com/docs/model/openai/gpt-oss-20b) lista JSON Object Mode e JSON Schema Mode; o contrato atual `response_format={"type":"json_object"}` é compatível. A [documentação de saídas estruturadas](https://console.groq.com/docs/structured-outputs) distingue JSON válido de validação de schema. O projeto continua validando exatamente `mensagem`, `angulo` e `confianca` no backend. Disponibilidade na conta não é confirmada pela documentação pública.

## Correção

- Erro tipado `GroqProviderError` com códigos/mensagens controlados pelo servidor; status e código sobrevivem ao SalesAgent e ao SDR, inclusive em retries idempotentes.
- Logs de falha registram somente endpoint fixo, etapa, status HTTP, classe de exceção e código Groq conhecido. Não registram resposta bruta, prompt, chave, headers, dados do lead ou mensagem comercial.
- BFF mantém o status apropriado, inclusive 504, e só publica códigos de diagnóstico de uma lista permitida. A interface já mostra `detail`; edição e texto atual continuam preservados.
- Falhas de salvamento SQLite têm diagnóstico separado `SDR_STORAGE_FAILED`, sem serem apresentadas como falha do Groq.
- Prompts comerciais, modelo, formato JSON, parâmetros de geração, salvamento explícito, revisão manual e WhatsApp manual permanecem iguais. Não existe fallback fictício ou envio automático.

| Código | HTTP local | Significado |
| --- | --- | --- |
| GROQ_CONFIG_INVALID | 503 | Configuração ausente/inválida no backend |
| GROQ_AUTH_INVALID | 503 | Groq retornou 401 para a credencial |
| GROQ_PERMISSION_DENIED | 503 | Groq retornou 403 |
| GROQ_MODEL_UNAVAILABLE | 503 | model_not_found ou model_decommissioned |
| GROQ_RATE_LIMITED | 429 | Rate limit do Groq |
| GROQ_TIMEOUT | 504 | Timeout no SDK |
| GROQ_CONNECTION_FAILED | 503 | Transporte/conectividade, incluindo possível TLS |
| GROQ_TLS_FAILED | 503 | Falha comprovada de validação de certificado na cadeia de exceções |
| GROQ_UNAVAILABLE | 503 | HTTP 5xx do provedor |
| GROQ_JSON_INVALID | 502 | json_validate_failed ou JSON não parseável |
| GROQ_OUTPUT_TRUNCATED | 502 | finish_reason=length |
| GROQ_RESPONSE_INVALID | 502 | Schema/conteúdo de resposta inválido |
| GROQ_REQUEST_REJECTED | 502 | Outra rejeição HTTP do Groq |
| SDR_STORAGE_FAILED | 503 | Falha de transação, schema, backup ou banco ocupado |

Códigos Groq desconhecidos não são expostos nos logs. Mensagens brutas do SDK nunca são copiadas para a interface. O teste de conexão existente também não é executado automaticamente.

## Variáveis necessárias

```dotenv
LOUNG_AUTH_MODE=local
LOUNG_STORAGE_BACKEND=sqlite
LOUNG_ENABLE_WRITES=1
GROQ_API_KEY=<sua chave, somente no ambiente privado>
GROQ_MODEL=openai/gpt-oss-20b
GROQ_TIMEOUT=30
```

O backend limita o timeout a 30 segundos; o BFF espera até 40 segundos pela geração. O SQLite mantém o caminho configurado por `LOUNG_DATABASE_PATH`. Nenhuma variável Supabase é necessária.

## Validação manual

1. No mesmo PowerShell usado para iniciar o backend, rode o relatório **offline**, com o mesmo arquivo de ambiente:

   ```powershell
   backend/.venv/Scripts/python.exe -m backend.scripts.check_groq_config --env-file .env
   ```

   `sources` informa onde cada valor vem; `processDiffersFromFile` mostra diferenças sem revelar credenciais. Se uma variável exportada estiver obsoleta, remova-a somente desse terminal com `Remove-Item Env:GROQ_API_KEY` / `Remove-Item Env:GROQ_MODEL`, conforme o caso. Não é necessário apagar ou trocar credenciais do arquivo.

2. Reinicie o backend no mesmo terminal e frontend após a atualização do código:

   ```powershell
   backend/.venv/Scripts/python.exe -m backend.scripts.run_api --env-file .env
   ```

   Em outro terminal: `cd web` e `npm.cmd run dev`.

3. Abra `/sdr`, selecione um lead, escolha serviço/destinatário e escreva uma orientação. Clique em gerar **somente quando desejar realizar a chamada real**. Em caso de falha, consulte Network: `POST /api/sdr/generate` retorna `detail` e `code`; no backend, procure `groq.failure`. Compartilhe somente esses campos seguros.
4. Em sucesso, revise o texto, salve, recarregue o histórico e regenere para obter outra versão. Confirme preservação das mensagens salvas após reiniciar. Abra o WhatsApp pelo botão e confira o texto; o envio continua manual.

Não se deve executar testes contra a base real. A verificação automatizada usa bases temporárias, MockTransport do SDK oficial e HTTPS em loopback. A única tentativa real autorizada foi concluída e não será repetida automaticamente.

## Testes executados

- 1.110 testes Python passaram: suíte do núcleo/desktop, SDR, modo local, integração Groq e TLS nativo. Incluem geração válida, autenticação inválida, permissão negada, modelo ausente/desativado, rate limit, timeout, JSON inválido, schema inválido, saída truncada, configuração ausente, precedência do ambiente, logs sanitizados, persistência/revisões, regeneração e rollback SQLite. Os testes TLS verificam cadeia confiada no cliente de teste, rejeição de certificado não confiável e rejeição de hostname incorreto.
- 22 testes Node passaram, incluindo propagação segura de código/status pelo BFF e URL WhatsApp com o texto revisado exato.
- Playwright/Edge headless passou: geração, revisão, salvamento, aprovação, regeneração, histórico, texto preservado, WhatsApp interceptado sem envio e quatro resoluções. Zero erros JavaScript.
- TypeScript e build Next.js passaram; ESLint sem avisos. Testes usaram somente respostas simuladas e bases temporárias.
- No sandbox Windows, o harness de teste ajustou ACLs de criação dos diretórios temporários do pytest e combinou dependências dos dois ambientes virtuais existentes, sem mudanças no runtime do produto. `AI_PROVIDER=openai` foi definido somente no processo de testes para isolar uma configuração desktop antiga. O runner bloqueou sockets/DNS externos.

## Arquivos desta correção

- `core/sales/errors.py`, `core/sales/groq_provider.py`, `core/sales/agent.py`.
- `backend/sdr/service.py`, `backend/sdr/storage.py`, `backend/scripts/check_groq_config.py`.
- `web/src/lib/api/sdr-proxy.ts`.
- `backend/tests/test_groq_integration.py`, `web/scripts/local.test.mjs`.
- `backend/tests/test_groq_tls.py`, `requirements.txt` para a correção TLS Windows.
- Este relatório. Alterações anteriores do Git foram preservadas; nenhum commit criado.
