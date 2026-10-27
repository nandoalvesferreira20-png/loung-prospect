# Acesso após login — diagnóstico de 20/10/2026

## Causas e evidências

1. **FastAPI iniciado sem configuração do processo.** No serviço existente em 8000, GET `/health` retornou 200 com `configured:false`. GET `/v1/session` retornou 503 com a instrução de configurar Supabase/PostgreSQL, inclusive antes de verificar token. O `.env` da raiz tem as variáveis, mas `Settings.from_environment()` só lê `os.environ`; iniciar Uvicorn sem `--env-file` não carrega esse arquivo. O BFF transformava esse 503 numa mensagem genérica de acesso indisponível.
2. **Endpoint PostgreSQL atualmente inacessível por DNS.** O diagnóstico explícito com as variáveis do arquivo identifica login restrito `loung_web` e TLS obrigatório, mas falha em `database_connect` com `DB_DNS_FAILED`. A verificação foi repetida fora do sandbox: o host configurado não resolve em IPv4 nem IPv6. O host Auth resolve em IPv4. A URL Auth do backend coincide com a pública do navegador. A DSN não coincide com o padrão direto derivado do projeto Auth; o padrão derivado também não resolveu neste ambiente, portanto não se afirma que simplesmente acrescentar/trocar uma parte do host resolverá. Copiar o endpoint exato do Dashboard, sem adivinhá-lo.

O primeiro erro impede chegar ao JWT e ao banco; o segundo bloqueia a etapa seguinte. **Não há evidência de que grants, RLS ou a membership real estejam errados**: não foi possível alcançar a autenticação PostgreSQL. Não trocar permissões para resolver DNS.

O endereço de health existente é `/health`, não `/api/health`. Abrir uma URL do FastAPI com headers de origem de navegador pode produzir `BFF_REQUIRED`; isso é a proteção de origem e não comprova sessão ou disponibilidade do banco. O navegador continua usando Next BFF, sem CORS aberto.

## Correções implementadas

- `backend/scripts/run_api.py`: inicialização explícita com arquivo escolhido pelo operador. Não carrega `.env` desktop implicitamente, não altera o arquivo, preserva precedência de variáveis já exportadas e mantém o bind em loopback.
- `backend/persistence/runtime.py`: códigos seguros de falha e log de etapa/status/código. Health informa os nomes de configurações ausentes, sem seus valores. Autenticação e autorização permanecem obrigatórias.
- `backend/persistence/errors.py` e `postgres.py`: falhas de conexão, troca de papel, identidade transacional e consulta de membership são classificadas. Falha SQL de permissão/schema na consulta de membership deixa de escapar como erro genérico 500. Texto bruto do driver nunca vai para a resposta ou log.
- `web/src/app/api/session/route.ts` e `web/src/lib/auth/access-errors.ts`: o BFF traduz somente códigos permitidos, sem repassar detalhes brutos. Rejeita destino remoto/credenciais em LOUNG_API_URL antes de encaminhar o token, preservando a mesma restrição dos demais proxies.
- `backend/scripts/check_access.py`: diagnóstico explícito, read-only e sem dados pessoais. Conexão real só com `--database` e login `loung_web`; checa SET LOCAL ROLE, contexto auth.uid e que uma identidade sintética sem membership não lê organizações. Não cria usuário nem registro. Toda transação de diagnóstico é revertida ao fechar. Sai com código 1 quando falha.
- `web/.env.example`: voltou a conter placeholders, sem configuração pública específica de projeto.

Logs novos contêm apenas etapa, HTTP, código e classe de erro. Nunca JWT, cookies, refresh token, DSN, senha ou chave. Principais códigos: BACKEND_NOT_CONFIGURED, DB_DNS_FAILED, DB_LOGIN_REJECTED, DB_POOLER_USER_FORMAT, DB_PERMISSION_DENIED, DB_SCHEMA_MISSING, AUTH_INVALID e MEMBERSHIP_REQUIRED.

## Procedimento manual necessário

**Não executar novamente migrations nem alterar usuários/roles para esta falha.**

1. No mesmo projeto Supabase usado pelo Auth, abrir **Connect** e copiar os parâmetros do método escolhido. Conferir status do projeto e restrições de rede se o endpoint não resolver.
2. Para backend persistente com IPv6 funcional, conexão direta usa o login `loung_web` e o host/porta diretos mostrados no Dashboard. Se a rede é somente IPv4, escolher **Session pooler**, porta 5432, usuário **`loung_web.PROJECT_REF`**. O host do pooler deve ser copiado do Dashboard; não compor região/índice manualmente. O custom role é suportado no pooler compartilhado com esse sufixo. [Documentação oficial](https://supabase.com/docs/guides/database/connecting-to-postgres).
3. Ajustar **somente LOUNG_POSTGRES_DSN no arquivo de ambiente usado pelo servidor**, mantendo a senha já definida para `loung_web`, não a de uma conta administrativa. Codificar caracteres reservados da senha na URI e manter TLS (`sslmode=require` ou verificação de certificado configurada). Não enviar a DSN para o frontend/chat. Nenhum `.env` existente foi editado automaticamente nesta investigação.
4. Executar o diagnóstico na raiz:

```powershell
backend/.venv/Scripts/python.exe -m backend.scripts.check_access --env-file .env --database
```

Esperado: configuração presente; database_connect ok; runtime_role ok/restricted true; transaction_identity ok/auth_uid_matches true; membership_rls ok/unknown_identity_has_no_access true. Isso valida a infraestrutura restrita, **não a membership do usuário real**. Se houver DB_PERMISSION_DENIED, parar e revisar a permissão específica antes de propor migration incremental. Não usar postgres, service_role, BYPASSRLS ou desabilitar RLS.

5. Encerrar **no próprio terminal** o FastAPI antigo em 8000 e reiniciar explicitamente:

```powershell
backend/.venv/Scripts/python.exe -m backend.scripts.run_api --env-file .env --port 8000
# Alternativa equivalente:
# backend/.venv/Scripts/python.exe -m uvicorn backend.main:app --env-file .env --host 127.0.0.1 --port 8000
```

O `.env` da raiz não é carregado automaticamente pelo comando antigo. O exemplo usa esse arquivo porque é onde as variáveis já estão no workspace; pode apontar para outro arquivo de configuração exclusivamente do backend. Variáveis de processo previamente exportadas têm precedência; corrigir/remover exports antigos no próprio terminal se necessário.

6. Consultar `/health` sem headers de Origin (por exemplo com Python/cliente HTTP local): deve retornar `configured:true` e `missingConfiguration:[]`. Isso **não** testa o banco. Uma chamada a `/v1/session` sem JWT deve retornar 401; não é necessário liberar acesso anônimo para validar saúde.
7. Next usa LOUNG_API_URL=http://127.0.0.1:8000 por padrão. Reiniciar seu Next para carregar o BFF atualizado. Em desenvolvimento: `cd web; npm.cmd run dev`. Se usa npm start, executar build com as variáveis públicas corretas antes do start.
8. Entrar pelo Next e observar `/api/session`: 200 com nome/organização/papel, seguido das consultas do Dashboard. 403/MEMBERSHIP_REQUIRED é ausência de associação autorizada após JWT válido; 401 é token/sessão; 503 e código DB_* apontam a etapa de infraestrutura. Somente após os passos anteriores investigar a membership real. Nenhum token deve ser copiado para comandos, logs ou relatório.

## Validação e limites

Instância temporária em 8011, usando `run_api --env-file .env`, respondeu `/health` com `configured:true` e sem campos ausentes. `/v1/session` sem token retornou 401/AUTH_INVALID. Isso confirma a correção do carregamento mantendo autenticação; essa instância foi encerrada, e o processo original do usuário em 8000 foi preservado.

Testes Python incluem configuração ausente, launcher explícito, falhas de DNS e SET ROLE, mensagens sem vazamento, recuperação após falha temporária, sessão autorizada/não membro, JWT inválido/expirado, isolamento, concorrência e carteira compartilhada. Integração SQL e navegação usam apenas PGlite em memória, Auth sintético e providers simulados. Nunca são usados os usuários ou a carteira reais.

A conexão real parou em DNS. Não foram confirmados senha PostgreSQL, SET ROLE, auth.uid, políticas RLS ou membership reais, nem acesso real ao Dashboard. Nenhum SQL administrativo, migration, mudança de conta/permissão ou escrita comercial foi executado. A solução real depende de o operador ajustar o endpoint e reiniciar o backend explicitamente.

## Resultados finais

| Verificação | Resultado |
|---|---|
| Suíte Python offline completa, com PostgreSQL sintético | **120 aprovados** |
| Rechecagem de diagnóstico/JWT após refinamento de erros SQL | **19 aprovados** |
| Testes de autenticação, cookies SSR e BFF | **6 aprovados** |
| Lint / TypeScript | **Aprovados** |
| Build Next.js em cópia isolada, sem arquivos de ambiente reais | **Aprovado** |
| Edge headless: login, Dashboard autenticado, persistência, CRM com autoria, logout, recuperação e não membro | **Aprovado** com Auth/PostgreSQL sintéticos |
| Falha temporária e recuperação no BFF/backend | **Aprovado** em testes |
| Diagnóstico real antes da correção do comando de início | `/health` 200/configured false; `/v1/session` 503 |
| Inicialização explícita temporária em 8011 | `/health` 200/configured true; sessão sem JWT 401 |
| Conexão PostgreSQL real somente leitura | **Bloqueada em DNS**, antes de autenticar ou executar consultas |
| SQLite original | **Hash idêntico**, nenhuma escrita |

O primeiro teste completo de navegador encontrou uma condição de corrida na automação ao trocar para a recuperação por navegação SPA; o teste foi estabilizado aguardando um carregamento completo dessa página. Nenhuma regra de autenticação foi relaxada para passar o teste. A navegação autenticada ao Dashboard já havia funcionado na primeira passagem sintética.

Os serviços sintéticos em 3100, 8100 e 55431 foram encerrados após as verificações. O build isolado ficou em diretório de testes ignorado pelo Git, sem substituir o build ou o processo ativo do usuário. O backend original em 8000 e o Next original não foram encerrados automaticamente: reinicie-os no próprio terminal após ajustar a configuração conforme os passos acima.
