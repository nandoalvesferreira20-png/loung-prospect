# Fase 3.2 — revisão de segurança da migration

SQL final: `supabase/migrations/202610200002_team_operations.sql`.
Revisão local em 20/10/2026. Não aplicada ao Supabase real.

## Problemas encontrados e correções

1. **Último owner / snapshot antigo:** o advisory lock original serializava os
   comandos, mas não invalidava snapshots de transações `REPEATABLE READ`.
   Duas transações podiam rebaixar owners diferentes e confirmar ambas.
   Reproduzido em PostgreSQL nativo 17.11 com duas conexões independentes:
   duas leituras iniciais encontraram dois owners; após os dois commits, zero.
   A versão final conserva o advisory lock e faz uma escrita MVCC na organização
   antes de verificar autorização/contar owners. `updated_at` mantém seu valor.
   Em `READ COMMITTED`, a segunda operação vê o estado confirmado; em snapshots
   antigos, PostgreSQL aborta com `40001`. A proteção está no trigger para cobrir
   `UPDATE`/`DELETE` diretos, inclusive em lote, e também antes da autorização do
   RPC para impedir que um owner revogado autorize usando um snapshot antigo.
2. **Proprietário implícito:** agora as quatro funções pertencem explicitamente
   a `postgres`. A aplicação exige esse papel de implantação confiável com
   `BYPASSRLS` já existente; não cria nem concede esse atributo. Isso é necessário
   ao definer para inserir em `audit_events` com `FORCE RLS`. O backend continua
   usando `SET LOCAL ROLE loung_api`, sem privilégios administrativos.
3. **Grants padrão:** revogar apenas `PUBLIC`, `anon` e `authenticated` podia
   deixar EXECUTE explícito concedido por `ALTER DEFAULT PRIVILEGES`, inclusive
   a `service_role` ou papéis personalizados. A migration remove todos os ACLs
   dessas quatro funções, exceto o proprietário, e concede apenas os dois RPCs
   a `loung_api`. Os triggers não recebem EXECUTE de runtime. Uma pós-condição
   aborta a transação se os papéis de API Supabase herdarem EXECUTE indiretamente.
4. **Configuração de runtime inesperada:** preflight aborta se `loung_api` puder
   assumir papéis administrativos ou tiver escrita direta nas tabelas de membros,
   organização ou auditoria (inclusive permissões por coluna). Não tenta corrigir
   esses grants nem ampliar permissões automaticamente.
5. **Argumentos NULL:** `target` e `remove_access` nulos agora são rejeitados com
   `22023`, assim como roles inválidas, em vez de cair em um caminho ambíguo.

Não havia escapes `NEW\.` no arquivo revisado; referências `NEW.role`,
`NEW.organization_id` e `NEW.user_id` estavam corretas.

## Análise das funções e dos privilégios anteriores

| Função | Execução | Limite de segurança |
|---|---|---|
| `team_roster()` | `postgres` definer; EXECUTE só `loung_api` | `active_org()` + `is_member(org)` que compara com `auth.uid()`; nenhum argumento permite escolher usuário; perfil/email apenas dos membros da organização autorizada. Não faz escrita e continua compatível com transação read-only. |
| `manage_member(uuid,text,boolean)` | mesmo proprietário e executor | Reconsulta o papel real do ator na organização depois da serialização; exige owner, impede autoalteração, não cria membership, só altera/remove alvo já pertencente à organização ativa e só aceita owner/admin/member. Um owner promover outro membro é a operação autorizada. |
| `guard_membership()` | somente trigger, sem EXECUTE para clientes/runtime | Impede mudar identidade da membership e perder o último owner por UPDATE/DELETE. Protege operações SQL de operador e multirow, além do RPC. |
| `audit_membership()` | somente trigger, sem EXECUTE para clientes/runtime | Guarda organização, sujeito e roles; `actor_id=auth.uid()`, nunca `current_user` (que seria o definer). `lead_id` fica NULL e não exige lead artificial. Falha na auditoria aborta a alteração de membership. |

Todas mantêm `SET search_path=''` e relações/funções de aplicação qualificadas
com schema. Não há SQL dinâmico com entrada do usuário nos RPCs/triggers. O SQL
dinâmico de implantação usa apenas identidades de catálogo, `regprocedure` e
identificadores escapados. Nenhum definer é criado em schema controlável pelo
cliente; nenhum runtime recebe propriedade das funções.

Na migration anterior, `loung_api` é NOLOGIN/NOINHERIT/NOBYPASSRLS; recebe SELECT
em memberships/perfis/organizações e leitura/escrita de negócio sujeita a RLS,
sem escrita de membership ou auditoria. O reparo anterior fornece USAGE em auth;
`auth.uid()` já tem EXECUTE concedido. As duas migrations anteriores permanecem
inalteradas. `is_member()` usa o sub autenticado, não o papel declarado no JWT.

FastAPI configura `request.jwt.claims` e `app.organization_id` com `set_config`
local à transação após verificar o JWT, e aplica `SET LOCAL ROLE loung_api`.
SECURITY DEFINER não troca essas configurações; os eventos continuam atribuídos
ao usuário autenticado. Operador sem sub produz `actor_id=NULL`, `origin=operator`;
requisição autenticada produz `origin=web`. Não se usa conta administrativa no
backend. Credenciais SQL de runtime continuam sendo uma fronteira de confiança:
quem as possuir pode definir claims; elas nunca podem chegar ao navegador.

## Concorrência e limites operacionais

O UPDATE sem alteração de valor cria uma versão MVCC da linha da organização.
Isso pode causar contenção por organização e abortos `40001` em transações com
snapshot antigo; o operador deve repetir **a transação inteira**, com novas
leituras. Não repetir apenas o último comando. RPC e DML direto podem adquirir
locks em ordens diferentes (linha da membership versus advisory/organização),
gerando `40P01`; PostgreSQL aborta uma transação, preservando o invariante. O
backend atual usa READ COMMITTED para escrita; não foi modificado para retry
automático. Scripts de operador devem preferir travar a organização primeiro.

TRUNCATE não dispara triggers de linha e permanece fora dos privilégios de
runtime; foi verificado que o runtime não o possui. Um administrador que
desabilite triggers, altere funções ou force replicação está fora da proteção
oferecida por estes RPCs. Não foram adicionados privilégios ou recursos para
permitir esses caminhos. INSERT de membership continua sendo provisionamento
de operador; não se exige owner no meio de um bootstrap de organização nova.

## Preservação e aplicação

A migration contém criação de funções/triggers, ACLs e verificações, em uma
transação. Não contém backfill nem UPDATE/DELETE/INSERT executado sobre dados
de negócio durante a implantação: os UPDATEs de organização estão dentro das
funções e só ocorrem em futuras alterações de membros. Não modifica tabelas,
índices, sequences, source-id ou políticas RLS de leads/interações.

Dataset sintético: 160 leads, 17 interações e mapeamentos `migration_map` foram
inseridos antes da migration. A comparação integral de linhas JSONB, incluindo
IDs, timestamps e audit_events preexistentes, passou após sua aplicação.
Isso comprova a preservação no schema ensaiado; o banco real não foi consultado.
SQLite original e migrations anteriores mantiveram seus hashes.

Aplicar manualmente somente se a Fase 3.2 ainda não foi aplicada, após backup
operacional e conferência de catálogo no projeto correto. Não tornar este SQL
`CREATE OR REPLACE` para mascarar implantação parcial/desconhecida. Se o
preflight falhar, revisar a divergência; não conceder admin ao runtime para
contorná-lo. `postgres` é papel de implantação/definer, não DSN do FastAPI.
Nenhuma credencial foi lida/impressa/alterada e LOUNG_ENABLE_WRITES não foi habilitado.

### Conferências manuais somente leitura no projeto real

Executar como operador autorizado; apenas metadados e contagens, sem perfis,
emails, credenciais ou dados de leads:

```sql
SELECT current_user;
SELECT rolname,rolsuper,rolbypassrls,rolcreaterole,rolinherit
FROM pg_roles WHERE rolname IN ('postgres','loung_api','loung_web');
SELECT has_schema_privilege('loung_api','auth','USAGE') AS auth_usage,
       has_function_privilege('loung_api','auth.uid()','EXECUTE') AS auth_uid;
SELECT has_any_column_privilege('loung_api','public.organization_members','INSERT,UPDATE') AS member_write,
       has_table_privilege('loung_api','public.organization_members','DELETE,TRUNCATE') AS member_delete,
       has_any_column_privilege('loung_api','public.audit_events','INSERT,UPDATE') AS audit_write;
SELECT c.relname,c.relrowsecurity,c.relforcerowsecurity
FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
WHERE n.nspname='public' AND c.relname IN ('leads','lead_interactions','audit_events');
SELECT (SELECT count(*) FROM public.leads) AS leads,
       (SELECT count(*) FROM public.lead_interactions) AS interactions,
       (SELECT count(*) FROM public.migration_map) AS mappings;
```

Guardar as contagens antes/depois (160/17 se não houver novas operações).
Depois da aplicação manual, conferir:

```sql
SELECT p.oid::regprocedure,pg_get_userbyid(p.proowner) AS owner,p.prosecdef,p.proconfig,p.proacl
FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
WHERE n.nspname='public' AND p.proname IN
 ('team_roster','manage_member','guard_membership','audit_membership');
SELECT r.rolname,
 has_function_privilege(r.oid,'public.team_roster()','EXECUTE') AS roster,
 has_function_privilege(r.oid,'public.manage_member(uuid,text,boolean)','EXECUTE') AS manage,
 has_function_privilege(r.oid,'public.guard_membership()','EXECUTE') AS guard,
 has_function_privilege(r.oid,'public.audit_membership()','EXECUTE') AS audit
FROM pg_roles r WHERE r.rolname IN ('loung_api','anon','authenticated','service_role');
```

Esperado: owner postgres, SECURITY DEFINER, search_path vazio; somente loung_api
tem roster/manage, nenhum desses quatro papéis tem guard/audit. Conferir ainda
`pg_trigger` para membership_guard e membership_audit habilitados. Testes que
alteram memberships devem continuar no ambiente sintético; não usar pessoas
reais para reproduzir falhas de autorização/concorrência.

## Reprodução local e testes

PostgreSQL portátil oficial EDB 17.11; cluster descartável, host 127.0.0.1,
porta 55431, sem serviço Windows instalado. Nunca usa DSN de ambiente.
Após a validação, o servidor foi encerrado e o cluster sintético, o ZIP e os
binários baixados foram removidos. Relatórios de teste foram preservados.
Inicialização requer cluster **vazio**, usuário de teste postgres e extensão
unaccent disponível. O bootstrap cria apenas roles/tabelas sintéticas e aplica
as duas migrations anteriores. O runner offline impede DNS/conexões externas.

```powershell
# Depois de initdb e de iniciar o cluster descartável em loopback:55431:
.\backend\.venv\Scripts\python.exe -B backend/tests/bootstrap_native_phase32.py
.\backend\.venv\Scripts\python.exe -B -m backend.tests.reproduce_owner_snapshot
New-Item -ItemType Directory -Force artifacts/qa/team-security | Out-Null
.\backend\.venv\Scripts\python.exe -B backend/scripts/run_offline_tests.py backend/tests/test_phase31_postgres.py backend/tests/test_auth_schema_acl.py backend/tests/test_phase32_team.py -q --basetemp=artifacts/qa/team-security/new-run
node --test web/scripts/auth.test.mjs web/scripts/team.test.mjs
```

Usar cluster novo por execução completa: as migrations usam CREATE e não são
reexecutáveis sobre funções existentes. Testes de concorrência nativa exigem
o marcador criado pelo bootstrap; o runner WASM antigo os pula explicitamente.
Os testes existentes usam o nome histórico de marker `synthetic-memory-only`;
o marker adicional identifica o cluster nativo descartável.

Cobertura: ACL direto/default/herdado, proprietário/search_path, usuário sem
identidade, organização forjada, admin/member sem autorização, role Python
forjada, autoalteração, alvo fora da organização, NULLs, identidade imutável,
RLS e auditoria via FastAPI, rollback em falha de auditoria, invariantes de
UPDATE/DELETE em lote e concorrência real por UPDATE/DELETE/RPC em READ COMMITTED,
REPEATABLE READ e SERIALIZABLE, com observação de espera de lock em pg_stat_activity.

Resultado final: **38 testes PostgreSQL passaram**, sem skips, incluindo nove
casos de concorrência nativa; **8 testes Auth/BFF passaram**. As verificações
de grants por tabela/coluna e EXECUTE herdado foram também executadas diretamente
contra o SQL final e passaram. JUnit local:
`artifacts/qa/team-security/native-release.xml`. Aviso preexistente de depreciação
Starlette/httpx não altera os resultados. A primeira tentativa de pytest restrita
falhou por ACL de temporários do Windows; executada com permissão local adequada.
Uma asserção inicial do fixture somava leads de outros testes junto aos 160 do
dataset de preservação; foi corrigida para contar pela organização sintética.
Não houve falha funcional na execução final. Não foram repetidos lint/build de
frontend: nenhuma implementação Python/TypeScript de produção foi alterada.

## Referências técnicas

- [PostgreSQL: isolamento de transações e 40001](https://www.postgresql.org/docs/17/transaction-iso.html).
  A necessidade da escrita MVCC, além do advisory lock, foi confirmada pela reprodução local.
- [PostgreSQL: segurança de funções DEFINER e EXECUTE padrão](https://www.postgresql.org/docs/17/sql-createfunction.html).
- [Supabase: funções e search_path seguro](https://supabase.com/docs/guides/database/functions).
- [PostgreSQL: pacotes Windows oficiais/EDB](https://www.postgresql.org/download/windows/).

Não foram identificados outros problemas no escopo revisado além dos itens
listados, considerando o schema anterior ensaiado e as fronteiras de confiança
descritas. A configuração efetiva do projeto real ainda depende das conferências
manuais acima; não foi presumida a partir de uma conexão administrativa remota.
