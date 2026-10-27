# Loung Prospect — diagnóstico e correção do HTTP 503

Data: 22/10/2026. Este relatório atualiza a investigação anterior: a mudança de redirecionamento para 503 corrigia a classificação do erro, mas não resolvia o transporte TLS.

## Causa comprovada

A comunicação HTTPS dos processos server-side com o Supabase falhava na validação da cadeia de certificados. Não era um 401 causado por uma chamada sem cookies.

No Node v24.21.0, o probe ao Auth/JWKS falhou com SELF_SIGNED_CERT_IN_CHAIN. Com o MESMO endpoint e a MESMA chave pública, mudando somente a inicialização para `node --use-system-ca`, ambos responderam 200. Nenhuma opção de desativação de TLS foi usada. A API local em 8000 respondeu /health 200, configured=true, storage=postgres e nenhuma variável obrigatória ausente.

No Python 3.13, o cliente JWKS padrão também falhou: PyJWKClientConnectionError causado por SSLCertVerificationError. A comparação fora do sandbox, com o mesmo URL e PyJWKClient configurado com truststore.SSLContext(PROTOCOL_TLS_CLIENT), retornou 200. Uma requisição ao FastAPI existente com JWT de assinatura sintética não confiável retornou 503/AUTH_UNAVAILABLE, antes de membership/banco. O JWT sintético nunca pode autenticar um usuário; não foram usados tokens de contas reais.

A confiança nativa do Windows resolve a cadeia apresentada nesta rede. O diagnóstico não identifica quem instalou a CA, nem comprova quando a rede/certificados mudaram. Não há evidência causal ligando o problema à migration 3.2 ou à limpeza. A limpeza documentada preservou ambiente, dependências e build ativo. O histórico Git não tem um commit isolado da Fase 3.2 que permita comparar cronologicamente todos esses arquivos.

## Origem das respostas e fluxo

- `web/src/components/auth-form.tsx`: signInWithPassword diretamente no Supabase, seguido de navegação para /. Essa chamada não atravessa o FastAPI.
- `web/src/lib/auth/browser.ts`: createBrowserClient de @supabase/ssr, singleton, armazenamento em cookies. Não há armazenamento alternativo em localStorage nessa implementação.
- `web/src/proxy.ts`, função proxy: createServerClient, getAll/setAll e getUser. O catch produz exatamente a mensagem “Serviço de autenticação indisponível. Tente novamente.” e o HTTP 503 observado na página /. Falha TLS em getUser impede chegar ao BFF e ao FastAPI. Antes da primeira correção, erros retornados pelo SDK eram classificados como expiração e geravam 307 para /login?expired=1.
- O proxy permite /login, recuperação, atualização de senha e confirmação. Página pública com GET 200 é normal; não há regra de redirecionamento do login para si próprio. APIs protegidas sem sessão continuam 401, páginas protegidas continuam redirecionando para login.
- `web/src/components/session-provider.tsx`: consulta /api/session nas páginas protegidas e redireciona exclusivamente em 401; 403/503 são exibidos como falha de acesso.
- `web/src/lib/auth/server.ts`, backendHeaders: valida usuário com getUser e só então obtém o token da sessão e monta Bearer. `web/src/app/api/session/route.ts` encaminha para o endereço fixo /v1/session no FastAPI local. O endpoint desta árvore é /api/session; não existe /api/v1/session no frontend.
- `backend/authorization.py`, TokenVerifier: baixa JWKS e valida assinatura ES256/RS256, issuer, audience, expiração e claims. `backend/persistence/runtime.py`, middleware authorize, produz AUTH_INVALID em falhas de autenticação, AUTH_UNAVAILABLE em indisponibilidade e consulta membership antes de servir dados.

Cookies host-only não são compartilhados entre localhost e 127.0.0.1. Isso é esperado: usar sempre http://127.0.0.1:3000 durante login, recuperação e navegação. Não foi ampliado o Domain do cookie. Browser, SSR e proxy usam o mesmo resolvedor de configuração e a mesma codificação do SDK. O teste real do SDK confirma rotação de cookies tanto na requisição quanto na resposta, envio do token renovado ao BFF e limpeza de cookies após refresh inválido.

## Ambiente e banco: evidências e limites

Sem imprimir valores, foram confirmados: web/.env.local presente, NEXT_PUBLIC_SUPABASE_URL presente, NEXT_PUBLIC_SUPABASE_ANON_KEY presente, PUBLISHABLE_KEY ausente (o alias ANON_KEY é selecionado corretamente). A URL Auth da raiz/backend coincide com a pública do Next, a chave pública coincide quando definida nos dois arquivos, LOUNG_API_URL aponta ao loopback esperado, SUPABASE_URL e LOUNG_POSTGRES_DSN estão presentes e o arquivo da raiz mantém LOUNG_ENABLE_WRITES=0. NEXT_PUBLIC é incorporado no build: um processo/build antigo não é corrigido mudando apenas o arquivo de ambiente.

Não foi alterada a configuração remota de Site URL/redirect URLs no Supabase, pois não há acesso ao painel administrativo nesta tarefa. O formulário de recuperação usa a origem atual; a confirmação aceita exclusivamente invite/recovery. O fluxo de e-mail/convite real continua dependente da configuração do projeto.

Foi feita conexão PostgreSQL somente leitura com o login restrito loung_web e SET LOCAL ROLE loung_api. A conexão e a troca de papel funcionaram. A consulta real de membership executou com sucesso para uma identidade sintética aleatória e retornou ausência de autorização, como esperado. Não se consultou perfil ou organização de um usuário real.

O diagnóstico genérico check_access terminou com DB_PERMISSION_DENIED na chamada explícita a auth.uid(). A conferência de catálogos confirmou auth schema USAGE=false, auth.uid EXECUTE=true e public schema USAGE=true. Isso NÃO prova que o endpoint de sessão esteja quebrado: a consulta real de membership funcionou, e as políticas já resolvem referências às funções. O check_session_access confirmou separadamente membership ok e falha apenas no probe direto auth.uid. Nenhum grant foi alterado ou proposto como correção deste incidente. O perfil da conta real e sua membership não foram homologados sem uma sessão real autorizada.

## Correção mínima

1. `web/package.json`: dev/build/start iniciam o Next com node --use-system-ca. engines atualizado para Node 22.19+ da linha 22 ou 24.6+; versão instalada e testada: 24.21.0.
2. `web/package-lock.json`: apenas requisito Node da aplicação sincronizado nesta tarefa; demais alterações preexistentes preservadas.
3. `backend/authorization.py`: somente no Windows, passa contexto TLS nativo truststore ao PyJWKClient, sem monkey patch global e sem alterar a validação JWT. Demais plataformas mantêm ssl.create_default_context.
4. `backend/requirements.txt`: truststore==0.10.4, com marcador de plataforma Windows. Instalado no venv backend desta máquina.
5. `web/src/proxy.ts` e `backend/authorization.py`: logs estruturados de falha contendo somente componente, etapa, HTTP, classe de erro permitida, UUID de correlação e duração. O proxy devolve X-Request-Id para correlacionar o 503. Mensagens brutas, URL, cookies, DSN, dados pessoais e tokens não são logados.
6. `web/scripts/check-auth-connectivity.mjs`: probes seguros, somente leitura, de Auth, JWKS e health FastAPI.
7. Testes: `web/scripts/auth.test.mjs`, `backend/tests/test_auth_tls.py`, `backend/tests/auth_session_fixture.py`, `web/scripts/check_auth_session.py`. A fixture é loopback, não usa banco nem arquivos de ambiente reais.
8. Este relatório: `web/docs/auth-session-investigation.md`.

Nenhum banco, usuário, senha, migration, RLS, organização, lead, interação ou credencial foi alterado. Não foi criado commit. Nenhuma verificação de TLS foi desativada: um teste comprova rejeição de CA autoassinada desconhecida. A nova confiança vem do repositório de certificados confiáveis do Windows.

## Testes executados

- Node: `node scripts/auth.test.mjs` (9 aprovados) e `node scripts/team.test.mjs` (2 aprovados), em web.
- Python: 22 aprovados e 2 testes de migration/backup explicitamente não selecionados. Comando na raiz:

```powershell
backend/.venv/Scripts/python.exe -m backend.scripts.run_offline_tests backend/tests/test_auth_tls.py backend/tests/test_access_diagnostics.py backend/tests/test_phase31_security.py -k 'not backup_source_unchanged_and_history and not invalid_records_prevent_all_writes' -q --basetemp=temp/auth-tls-final-python2 -p no:cacheprovider
```

- npm.cmd run lint: passou. npm.cmd run typecheck: passou.
- npm.cmd run build -- --webpack: passou, 26 páginas geradas, em temp/auth-tls-qa/web, cópia isolada dos mesmos fontes, sem .env real. Webpack foi necessário porque Turbopack não resolve o junction de dependências fora da raiz da cópia. O proxy copiado e o fonte principal tiveram hashes iguais. O build/processo ativo do usuário não foi substituído nesta investigação.
- Navegador Edge headless: ` .venv/Scripts/python.exe web/scripts/check_auth_session.py`, na raiz, passou em dev e produção. Passou novamente após a mudança TLS do backend. Cobre login válido/inválido, Dashboard autorizado, recarga, host-only cookies, logout, proteção de API, redirecionamentos sem loop, indisponibilidade Auth e indisponibilidade API.
- SDK Supabase real com respostas HTTP sintéticas: login, cookies, refresh token, token renovado no BFF, sessão válida sem refresh extra, refresh rejeitado e cookies removidos. Nenhuma conta real foi usada.
- TLS real, somente leitura: Auth/JWKS Node antes falha, depois 200; JWKS Python padrão falha, contexto Windows 200.
- A suíte Python emite aviso preexistente de depreciação Starlette/httpx. Primeiras tentativas de testes/subprocessos foram limitadas pelo sandbox (EPERM/permissão de temporários); as execuções finais passaram com a permissão necessária. O primeiro acesso do dev excedeu o timeout de compilação inicial; repetido com timeout apropriado, passou.

Os serviços sintéticos em 8112/3198 foram encerrados ao concluir. Os serviços do usuário em 3000/8000 não foram reiniciados automaticamente. O login real e o Dashboard com os 160 leads continuam pendentes de validação humana; não se afirma que esse teste passou.

## Reiniciar e validar manualmente

Encerre os processos antigos com Ctrl+C nos respectivos terminais. Na raiz do projeto, backend:

```powershell
Set-Location 'C:\Users\BR0450988468\Desktop\loung\loung-prospect'
backend/.venv/Scripts/python.exe -m pip install truststore==0.10.4
$env:LOUNG_ENABLE_WRITES='0'
backend/.venv/Scripts/python.exe -m backend.scripts.run_api --env-file .env --port 8000
```

Em outro terminal, frontend:

```powershell
Set-Location 'C:\Users\BR0450988468\Desktop\loung\loung-prospect\web'
node --use-system-ca scripts/check-auth-connectivity.mjs
npm.cmd run dev
```

Para produção, com o servidor Next anterior encerrado:

```powershell
npm.cmd run build
npm.cmd run start
```

1. Use somente http://127.0.0.1:3000/login. Credenciais reais são informadas apenas no formulário, nunca no terminal/chat.
2. Faça login; confirme POST Auth de senha com sucesso, navegação para / e GET /api/session 200. Não copie payloads, headers ou respostas que contenham tokens.
3. Recarregue o Dashboard; confirme sessão persistida, leitura autorizada de leads e ausência de retorno ao login. Não crie/edite registros durante a validação.
4. Faça logout; confirme /login e negação de acesso protegido. Janela anônima sem sessão deve redirecionar ao login/retornar 401 nas APIs.
5. Para falhas 503, use o X-Request-Id/logs seguros. Para 403, investigar membership da conta autorizada; não tratar como senha inválida. Não provocar indisponibilidade em serviços reais para testar: esse cenário foi coberto na fixture.

A inicialização adicional de uma API temporária na porta 8013 com o .env real foi rejeitada pela revisão automática de aprovação, por permitir potencial acesso a dados reais mesmo com escrita zero. Não foi executada nem contornada. Essa validação adicional depende de autorização; os testes sintéticos e probes TLS somente leitura foram concluídos.

Referências oficiais: [Node: certificados do sistema](https://nodejs.org/learn/http/enterprise-network-configuration), [Truststore: validação nativa](https://truststore.readthedocs.io/en/stable/index.html), [PyJWT: ssl_context](https://pyjwt.readthedocs.io/en/latest/api.html). Também consultadas as fontes instaladas de Next 16, @supabase/ssr e PyJWT.
