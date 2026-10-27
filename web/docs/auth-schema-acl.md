# ACL do schema auth e /v1/session — 20/10/2026

## Conclusão e limite da evidência

O privilégio ausente informado (`has_schema_privilege('loung_api','auth','USAGE') = false`) é uma divergência entre ACL efetiva e a migration original. Em PostgreSQL isolado, isso faz **`SELECT auth.uid()` falhar com SQLSTATE 42501, objeto schema auth, privilégio USAGE**. O grant mínimo para essa falha é `GRANT USAGE ON SCHEMA auth TO loung_api`.

**Não é prova suficiente da causa do erro de /v1/session.** Com as políticas e funções atuais deste repositório, a mesma ausência foi reproduzida e o endpoint ainda respondeu 200: expressões RLS guardam referências a funções já resolvidas; public.is_member é SECURITY DEFINER, com search_path vazio. A consulta externa de membership não escreve `auth.uid()` explicitamente. Portanto não se afirma que conceder USAGE resolverá o endpoint real sem capturar sua instrução falha. Essa distinção foi mantida como teste de regressão.

A captura real não foi executada: LOUNG_POSTGRES_DSN no `.env` confirmado continuou identificando login administrativo na verificação segura. O diagnóstico recusa esse login. Não se usou a senha desse arquivo para tentar outro usuário e nenhum comando de alteração foi enviado ao Supabase. O operador informou que avisará quando ajustar localmente a conexão restrita.

## Caminho exato do endpoint

1. FastAPI verifica JWT (assinatura, issuer, audience, expiração).
2. Database.open: conexão como loung_web, transação read-only, `SET LOCAL ROLE loung_api`.
3. `set_config('request.jwt.claims', ..., true)` define sub/role derivados do JWT; `app.organization_id` começa vazio. Nenhum token é colocado no PostgreSQL.
4. **statement_id=session_memberships**, antes de selecionar organização:

```sql
SELECT m.organization_id::text,m.role,o.name
FROM public.organization_members m
JOIN public.organizations o ON o.id=m.organization_id
WHERE m.user_id=$1
ORDER BY o.slug;
```

Esse SQL aplica api_members (`user_id=auth.uid()`) e api_org (`public.is_member(id)`). A função SECURITY DEFINER consulta memberships como seu proprietário; não deve ser convertida em SECURITY INVOKER para corrigir ACL.

5. Sem associação autorizada: 403/MEMBERSHIP_REQUIRED. Com associação: define Identity no servidor.
6. Nova conexão/transação, SET LOCAL ROLE e claims + organização ativa; revalida a membership e lê metadados das seis tabelas. Cada instrução tem um identificador fixo.
7. **statement_id=session_profile**:

```sql
SELECT display_name FROM profiles WHERE id=$1;
```

A política api_profiles usa auth.uid() e public.shared_profile(id), que também é SECURITY DEFINER. O endpoint devolve usuário/organização/papel. Um erro pode ocorrer em qualquer etapa; não presumir que é o SELECT do perfil.

Os SQLs estão centralizados em backend/persistence/session_queries.py. Logs agora incluem stage, statement_id, SQLSTATE e objeto/privilégio permitido por whitelist, nunca valores vinculados, JWT, cookies, DSN ou texto bruto do driver. Exemplo seguro de evidência capturada no teste de SELECT revogado:

```text
stage=membership_query code=DB_PERMISSION_DENIED sqlstate=42501
statement=session_memberships
object_type=table object=public.organization_members privilege=SELECT
```

Nesse caso, o grant de schema auth **não** é correção de SELECT na tabela. A instrumentação evita confundir as duas falhas. Erro de rollback posterior não sobrescreve mais o erro de consulta original.

## Migration incremental revisável

Arquivo: `supabase/migrations/202610200001_repair_auth_schema_usage.sql`.

```sql
BEGIN;
GRANT USAGE ON SCHEMA auth TO loung_api;
DO $verify_auth_usage$
BEGIN
    IF NOT has_schema_privilege('loung_api', 'auth', 'USAGE') THEN
        RAISE EXCEPTION USING
            ERRCODE = '42501',
            MESSAGE = 'USAGE on schema auth was not granted to loung_api; use an authorized schema owner or grantor';
    END IF;
END
$verify_auth_usage$;
COMMIT;
```

Só adiciona USAGE ao schema para o runtime; não concede CREATE, SELECT em auth.users, roles, grant option ou privilégios administrativos. Não muda auth.uid, políticas, ownership, JWT, memberships ou auditoria. EXECUTE em auth.uid já está na migration original; verificar separadamente antes de acrescentar qualquer outro grant. A migration original não foi editada (SHA-256 f3448ca7592d1bdb55cc7aa4e3f4ee18d81c5e12273366e7b7785f31cfb0632e).

### Por que repetir um GRANT pode não funcionar

Um executor que tem USAGE mas não ownership/grant option pode receber warning e não conceder privilégio efetivo. Isso foi reproduzido em um papel isolado sem grant option. A pós-condição da nova migration transforma esse falso sucesso em erro e rollback. Não se comprovou que esse foi o evento histórico ocorrido no projeto real; também podem existir revogação posterior, transação revertida ou execução em outro projeto.

O executor do SQL Editor **não precisa assumir loung_api para conceder ACL**. Ele precisa ser proprietário do schema ou já possuir USAGE WITH GRANT OPTION. Não conceder membership em loung_api para postgres apenas para executar o teste. No Supabase gerenciado, verificar o proprietário efetivo do schema auth; não tentar assumir roles internas ou alterar ownership como alternativa.

## Comandos de validação no Supabase real

### 1. SQL Editor: diagnóstico somente leitura, sem SET ROLE

```sql
SELECT current_database(),current_user;
SELECT n.nspname,pg_get_userbyid(n.nspowner) AS schema_owner,
       has_schema_privilege('loung_api',n.oid,'USAGE') AS api_usage,
       has_schema_privilege(current_user,n.oid,'USAGE WITH GRANT OPTION') AS executor_can_grant
FROM pg_namespace n WHERE n.nspname IN ('public','auth');

SELECT n.nspname,p.proname,p.prosecdef AS security_definer,
       pg_get_userbyid(p.proowner) AS function_owner,
       has_function_privilege('loung_api',p.oid,'EXECUTE') AS api_execute
FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
WHERE (n.nspname='auth' AND p.proname='uid')
   OR (n.nspname='public' AND p.proname IN ('is_member','shared_profile','active_org'));
```

Esperado: auth.uid executável; is_member/shared_profile com security_definer=true; USAGE efetivo em public/auth. Se executor_can_grant=false e não há ownership autorizado, **não insistir no mesmo GRANT** nem usar GRANT ALL: solicitar execução da migration ao operador/administrador que já possua o direito de conceder esse ACL. Se o schema gerenciado não oferecer um executor autorizado ao projeto, encaminhar ao suporte Supabase o SQLSTATE e os metadados de ACL, sem credenciais. Não criar um backend administrativo para contornar isso.

### 2. Aplicação manual, após revisão

Executar o conteúdo completo da nova migration no SQL Editor com executor autorizado. Nenhuma execução automática foi feita. Confirmar:

```sql
SELECT has_schema_privilege('loung_api','auth','USAGE') AS granted;
```

Resultado esperado: true. A migration aborta se o grant não se tornar efetivo. Se EXECUTE de auth.uid também estiver ausente, parar e revisar esse fato separadamente; não aplicar grants adicionais sem evidência/autorização.

### 3. Validação no contexto correto: conexão loung_web

Primeiro ajustar localmente LOUNG_POSTGRES_DSN para o login restrito, sem publicar senha. O SQL Editor conectado como postgres não substitui esse teste.

```powershell
backend/.venv/Scripts/python.exe -m backend.scripts.check_session_access --env-file .env --user-id UUID_EXISTENTE_DO_AUTH
```

O comando executa o trecho PostgreSQL de /v1/session com os mesmos SQLs, parâmetros vinculados, SET LOCAL e RLS, e depois uma chamada explícita separada a auth.uid. Só imprime resultados/códigos; se a etapa falha, informa statement_id e SQLSTATE. Um resultado negativo apenas em auth_uid_probe é diferente de falha em session_memberships/session_profile. Sem --user-id, usa UUID aleatório não persistido e espera ausência de membership, nunca inventa usuários no banco. O probe não substitui validação criptográfica de JWT: é uma ferramenta administrativa local de leitura, não endpoint de autenticação.

Opcionalmente validar via psql, com senha solicitada interativamente e parâmetros obtidos de Connect (não colocar senha no comando):

```powershell
psql -X -W "host=HOST_DO_CONNECT port=5432 dbname=postgres user=USUARIO_RESTRITO_DO_CONNECT sslmode=require" -v user_id=UUID_EXISTENTE_DO_AUTH -v organization_id=UUID_DA_LOUNG_TECH -f supabase/validation/session_access.sql
```

Em conexão direta, usuário loung_web. No pooler compartilhado, usar o nome loung_web.PROJECT_REF mostrado pelo método Connect. O arquivo inicia transação read-only, assume loung_api, checa auth.uid, membership, perfil, ausência de leitura fora da organização e ausência de privilégios em auth.users/CREATE auth, e termina em ROLLBACK.

Esperado: runtime_role_ok/auth_uid_ok/auth_usage/uid_execute/no_auth_create/no_auth_users_read/no_cross_org_rows/restricted_runtime=true; matching_memberships=1 e visible_own_profile=1. O teste isolado também usa uma segunda organização existente na fixture para comprovar 404/403 entre tenants; nenhum tenant real foi criado para testar.

### 4. Endpoint completo com JWT

Reiniciar o FastAPI com o arquivo restrito, usando `python -m backend.scripts.run_api --env-file .env --port 8000` no ambiente backend, e entrar normalmente pelo Next. Observar o retorno de /api/session e os logs seguros do FastAPI. Sucesso esperado: 200 com organização. Se ainda houver 503, usar statement_id/SQLSTATE/objeto para decidir a próxima correção; não copiar tokens nem cookies para comandos ou relatórios.

## Testes e restrições

Testes em PostgreSQL 18/PGlite WASM em memória: schema USAGE ausente, captura de 42501/objeto/USAGE; diferença entre chamada direta e RLS pré-resolvida; captura da consulta de membership com SELECT revogado; recuperação após restaurar o grant; migration repetida; executor sem grant option; RLS/FORCE RLS e isolamento entre dois tenants; ausência de CREATE auth, SELECT auth.users e BYPASSRLS. O bootstrap administrativo só existe no ambiente de testes para preparar ACLs; toda consulta de aplicação executa como loung_api. PGlite não prova login de rede real com loung_web nem as ACLs atuais do Supabase gerenciado.

Nenhuma alteração real foi executada. O resultado real de /v1/session permanece pendente da configuração restrita e da captura solicitada; o dado isolado não foi apresentado como confirmação da causa real.

Referências: [privilégios PostgreSQL](https://www.postgresql.org/docs/17/ddl-priv.html), [GRANT](https://www.postgresql.org/docs/15/sql-grant.html), [SQLSTATE](https://www.postgresql.org/docs/current/errcodes-appendix.html), [ownership de schemas Supabase](https://supabase.com/docs/guides/platform/permissions).

## Resultado da execução

- Suíte offline completa: **126 testes aprovados**.
- Rechecagem final de diagnóstico, incluindo recusa de login administrativo antes de conectar: **9 testes aprovados** (inclui um novo teste posterior à suíte completa).
- Quatro testes SQL específicos de ACL aprovados: falta de USAGE versus sessão real isolada, statement_id de SELECT negado, isolamento após grant e falha explícita do grant sem efeito.
- Migration original verificada por hash: inalterada.
- Nenhuma conexão administrativa foi usada no Supabase real; nenhuma alteração real foi aplicada. Na última verificação, o arquivo informado ainda não estava configurado com login loung_web; a captura do erro real permanece pendente do ajuste local avisado pelo operador.
