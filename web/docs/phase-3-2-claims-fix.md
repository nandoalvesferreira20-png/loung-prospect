# Fase 3.2 — remover a dependência de USAGE em auth no trigger de autoria

Revisão de 22/10/2026. SQL novo: `supabase/migrations/202610220001_stamp_actor_from_verified_claims.sql`.

**Estado da entrega:** SQL revisado e aprovado no PostgreSQL isolado. Não aplicado no Supabase real. Escrita real continua desabilitada. Nenhuma alteração dos 160 leads reais ou dos arquivos de ambiente reais foi realizada.

## Causa exata

POST `/v1/leads` passa por `backend/persistence/leads.py:create`, pelo writer PostgreSQL e pelo INSERT de `backend/prospecting/storage.py:SelectionStore.save`. O PostgreSQL dispara:

```sql
CREATE TRIGGER stamp BEFORE INSERT OR UPDATE ON public.leads
FOR EACH ROW EXECUTE FUNCTION public.stamp_actor();
```

A função original é SECURITY INVOKER e executa `NEW.created_by := auth.uid()` e `NEW.updated_by := auth.uid()`. O FastAPI configura `SET LOCAL ROLE loung_api`, portanto essa resolução do nome `auth.uid()` acontece com os privilégios do runtime. Sem USAGE em auth, o PostgreSQL retorna 42501 antes de confirmar o lead. O erro vira DB_PERMISSION_DENIED no backend.

Esse mesmo trigger de autoria está associado a interações, abordagens SDR, revisões e outras tabelas de negócio. A correção da função beneficia todos esses caminhos sem alterar rotas ou recriar triggers.

Há outras referências legítimas a auth.uid: políticas RLS e funções existentes, como `public.is_member`, `public.shared_profile`, `public.audit_change` e a gestão de equipe. Não foram removidas ou modificadas. A auditoria usa a função SECURITY DEFINER já existente; sua execução não requer conceder USAGE do schema ao caller do trigger invoker. Os testes confirmam o fluxo com USAGE revogado do runtime.

## Identidade já disponível na transação

`backend/authorization.py:TokenVerifier.verify` valida assinatura ES256/RS256, issuer, audience, expiração, claims obrigatórias e role authenticated. A membership é consultada no PostgreSQL. Só depois o backend estabelece a organização autorizada.

`backend/persistence/postgres.py:Database.open` utiliza o SQL fixo de `backend/persistence/session_queries.py` para configurar:

```sql
SET LOCAL ROLE loung_api;
SELECT set_config('request.jwt.claims', $1, true),
       set_config('app.organization_id', $2, true);
```

O primeiro parâmetro contém somente sub normalizado pelo verificador e role authenticated. O segundo é a organização validada. Ambos são parâmetros do servidor e locais à transação, não valores de identidade aceitos do navegador. Nenhum JWT bruto é gravado nas configurações SQL.

`auth.uid()` não valida criptograficamente o JWT: ele extrai identidade do contexto SQL. Para este writer, ler o sub das claims já estabelecidas elimina o lookup de schema sem trocar a fronteira de autenticação.

## SQL escolhido e análise de segurança

Não é necessária função auxiliar SECURITY DEFINER. A migration substitui somente a função de aplicação `public.stamp_actor()`, com SECURITY INVOKER e search_path vazio. O núcleo é:

```sql
DECLARE actor pg_catalog.uuid;
BEGIN
 actor := nullif(
  nullif(pg_catalog.current_setting('request.jwt.claims', true), '')::pg_catalog.jsonb ->> 'sub',
  ''
 )::pg_catalog.uuid;
 IF current_user = 'loung_api' AND actor IS NULL THEN
  RAISE EXCEPTION 'Authenticated transaction identity required' USING ERRCODE = '42501';
 END IF;
 IF TG_OP = 'INSERT' THEN
  NEW.created_by := actor;
 ELSE
  NEW.created_by := OLD.created_by;
 END IF;
 NEW.updated_by := actor;
 RETURN NEW;
END;
```

O arquivo completo inclui BEGIN/COMMIT, validação prévia e pós-condições. Não aplicar apenas esse fragmento.

- **Proprietário:** a migration exige execução pelo dono esperado da função, postgres, e aborta se o owner da função existente ou seu modo de execução forem inesperados. CREATE OR REPLACE conserva owner, OID e ACLs; não há ALTER OWNER.
- **Contexto:** continua SECURITY INVOKER. Não são criadas funções com privilégios elevados nem acrescentados acessos a tabelas ou schemas.
- **Resolução de nomes:** search_path vazio; current_setting e tipos usados na leitura de identidade são qualificados com pg_catalog. Não há SQL dinâmico nem nome de objeto controlado pelo cliente.
- **Grants:** nenhum GRANT/REVOKE é executado pela migration. A pós-condição rejeita EXECUTE direto inesperado para loung_api, anon ou authenticated. Os triggers já existentes não precisam de um novo grant para disparar.
- **RLS e organização:** todas as políticas, grants de tabelas e verificações de membership permanecem inalterados. Extrair um sub não concede acesso a outra organização; o role do JSON não muda o role PostgreSQL.
- **Autoria:** created_by é atribuído pelo servidor no INSERT e preservado no UPDATE; updated_by recebe o ator atual. Dados enviados nas colunas de autoria não substituem essa regra.
- **Identidade ausente ou inválida:** o runtime sem sub falha com 42501; JSON/UUID inválido aborta a transação. Trabalho legítimo de operador sem claims continua permitindo autoria NULL, como na migração/importação anterior.
- **Fronteira de confiança:** a credencial SQL restrita continua exclusiva do backend. Quem possui uma credencial SQL pode definir GUCs; essa característica já existia com auth.uid(). A função não é uma alternativa à validação JWT. Clientes SQL legados que usem somente request.jwt.claim.sub não substituem o contrato JSON usado pelo FastAPI e precisam de avaliação separada.

Não se altera ownership de auth ou de qualquer schema gerenciado. Não se concede SELECT em auth.users, USAGE amplo, CREATE de schema ou bypass RLS. Não se revoga um USAGE que eventualmente exista e seja usado por outras funcionalidades.

## Diagnóstico de prontidão atualizado

`backend/scripts/check_phase32_readiness.py` passou a aceitar auth sem USAGE **somente quando** reconhece o corpo exato desta versão revisada de stamp_actor, owner postgres, SECURITY INVOKER e search_path vazio. Um corpo alterado ou desconhecido não recebe essa exceção. As demais verificações de ACL, RLS, triggers e funções continuam ativas.

Na releitura real, a migration nova não estava instalada: o diagnóstico read-only permaneceu reprovado por identidade antiga do trigger e ausência de USAGE. Esses dois checks representam o mesmo bloqueio antes da aplicação, não duas correções SQL distintas. A flag continuava zero. Nenhuma operação de mutação real foi tentada.

## GROQ_MODEL: o que o código exige

Não existe modelo Groq hardcoded no SDR. `core/sales/config.py` lê GROQ_MODEL; `core/sales/groq_provider.py` recusa modelo vazio e envia o valor ao SDK oficial. O contrato atual usa chat.completions, stream=false, response_format=json_object e max_completion_tokens=1600. A resposta passa pela validação de mensagem/ângulo/confiança; JSON sintaticamente válido não basta. Não há fallback automático de modelo.

Valor documentado para configuração explícita pelo operador:

```dotenv
GROQ_MODEL=openai/gpt-oss-20b
```

O [catálogo de produção](https://console.groq.com/docs/models) lista esse modelo e a [documentação de JSON Object Mode](https://console.groq.com/docs/structured-outputs) o utiliza com o mesmo response_format. Essa é uma opção tecnicamente compatível, não comprovação de acesso/cota ou qualidade na conta específica. O limite de 1600 tokens foi preservado; truncamento continua rejeitado pelo provider, sem salvar mensagem incompleta.

Na releitura do arquivo real, GROQ_MODEL **já estava presente**, correspondendo a um dos Llama reconhecidos no catálogo atual como Enterprise. Não alterei o valor. O [Llama 3.3 70B](https://console.groq.com/docs/model/llama-3.3-70b-versatile) suporta JSON Object Mode, mas sua disponibilidade não deve ser presumida para qualquer chave. Confirmar a permissão do projeto antes de mantê-lo ou escolher outra opção.

Os arquivos `.env.example` e `backend/.env.example` agora mostram openai/gpt-oss-20b como exemplo público. O `.env` real não foi editado e nenhuma chave foi trocada. Se o modelo atual já estiver habilitado e adequado, não é necessário substituí-lo por esse exemplo.

Uma validação autenticada de metadados pode ser realizada posteriormente pelo operador com `create_groq_provider().test_connection()`: ela consulta o modelo sem enviar dados de lead ou gerar abordagem. Essa chamada real não foi executada nesta tarefa. Os testes utilizaram SDK/MockTransport e credenciais sintéticas.

## Testes realizados

Novo PostgreSQL nativo 17.11 descartável em 127.0.0.1:55431, com marcadores sintéticos. O schema anterior foi montado apenas nesse cluster; em seguida a migration nova foi testada com USAGE de auth revogado. O runner impediu rede externa.

- **191 testes backend aprovados**, zero falhas/erros/pulados, 148,35 s. Incluem 21 casos da migration nova e nove casos de concorrência nativa já existentes.
- **20 testes Groq aprovados**, zero falhas/pulados, 1,29 s, com MockTransport. O teste novo passa GROQ_MODEL da configuração ao SDK e verifica o contrato JSON e o limite existente de tokens.
- O fluxo novo utiliza conexão real como **loung_web**, assumindo loung_api, não uma sessão administrativa apenas simulando o runtime.
- Cobertura da correção: criação, edição, Pipeline, interação, geração/salvamento/revisão SDR, autoria imutável, auditoria, isolamento e rollback de todas as linhas/filhos em falha de auditoria.
- Tentativas de SET ROLE postgres, escrita de membership, INSERT direto na auditoria e leitura de auth.users foram negadas ao login restrito. Role service_role no JSON não permite gravar em outra organização.
- JSON/sub ausente, vazio ou inválido não permite escrita. O preflight de catálogo aprova a versão corrigida sem USAGE; rejeita corpo não revisado.
- A migration foi aplicada duas vezes no cluster sintético: dados, políticas, flags RLS, triggers, ownership de schemas, OID/ACL/modo da função permaneceram iguais. Uma concessão inesperada de EXECUTE faz a migration abortar atomicamente.

Comandos da execução:

```powershell
backend/.venv/Scripts/python.exe -B -m backend.scripts.run_offline_tests backend/tests -q --basetemp=temp/phase32-claims-fix-20261022/backend-pytest -p no:cacheprovider --junitxml=temp/phase32-claims-fix-20261022/backend-tests.xml
backend/.venv/Scripts/python.exe -B -m backend.scripts.run_offline_tests tests/test_sales_groq.py --noconftest -q --basetemp=temp/phase32-claims-fix-20261022/groq-pytest -p no:cacheprovider --junitxml=temp/phase32-claims-fix-20261022/groq-tests.xml
```

O comando combinado inicial foi interrompido na coleta porque o conftest dos testes legados importa Playwright, ausente no venv backend. As suites foram executadas separadamente; somente a suite Groq, que não usa fixtures de navegador, foi isolada desse conftest. Não houve instalação de dependências desnecessárias. Há o aviso preexistente de depreciação Starlette/httpx na suite backend.

Evidências: `artifacts/qa/phase32-claims-fix-20261022/backend-tests.xml`, `groq-tests.xml`, `summary.json` e `real-before-application.json`. Sem credenciais ou valores de leads reais. Nenhum TypeScript ou fluxo de autenticação/BFF foi alterado; lint/build frontend não foram repetidos nesta etapa SQL/Python.

O cluster descartável foi encerrado normalmente após os testes. O ZIP, os binários portáteis e os dados sintéticos do cluster foram removidos; relatórios foram preservados. A conferência final confirmou a porta de testes fechada e LOUNG_ENABLE_WRITES=0 no arquivo real.

## Aplicação segura — apenas procedimento, não executado

1. Manter **LOUNG_ENABLE_WRITES=0**. Confirmar projeto correto, histórico de migrations e backup. Capturar por leitura a definição/owner/ACL atuais de public.stamp_actor e os triggers/políticas associados para revisão e eventual restauração da definição.
2. Revisar integralmente `202610220001_stamp_actor_from_verified_claims.sql`. Não editar nem reaplicar as migrations anteriores, nem executar db push indiscriminadamente quando o histórico de aplicações manuais não estiver conciliado.
3. Somente após autorização, um operador com o papel postgres/dono esperado da função aplica **apenas o arquivo novo completo**, em sua transação. Essa credencial é de implantação, não deve ser colocada no backend ou frontend. Não é necessário alterar o dono de auth ou conceder USAGE.
4. Se a pré/pós-condição falhar, interromper e revisar owner/ACL; não remover a validação para forçar a aplicação. A transação deve ser revertida, preservando o estado anterior.
5. Repetir o diagnóstico read-only com o backend ainda em modo sem escrita:

```powershell
backend/.venv/Scripts/python.exe -m backend.scripts.check_phase32_readiness --env-file .env
```

Esperado: claimsStampInstalled=true, readyByCatalog=true, nenhum failedCheck. O check auth pode mostrar actual=false e required=false: isso é esperado nessa solução. Se houver outra falha, revisar a permissão específica, sem ampliar grants automaticamente.

6. Confirmar login, Dashboard e leitura de leads sem erro. Configurar/validar GROQ_MODEL no ambiente efetivo do backend se necessário e reiniciar o FastAPI mantendo a flag zero. Não copiar GROQ_API_KEY para NEXT_PUBLIC nem compartilhar logs/headers com tokens.
7. A homologação de escrita real permanece uma decisão separada, com autorização e um lead fictício exclusivo, seguindo o roteiro de `phase-3-2-homologation.md`. A aplicação da migration **não habilita escrita**.

Para eventual retorno, preservar a flag zero e restaurar somente a definição anterior capturada, com o owner autorizado; não usar DROP FUNCTION/CASCADE, não remover auditoria/RLS e não executar DELETE/TRUNCATE. Repor a função antiga pode reintroduzir a exigência de USAGE para futuras escritas, portanto não liberar mutações nesse estado.

A migration não faz backfill nem INSERT/UPDATE/DELETE em tabelas de negócio. Os 160 leads reais permanecem fora dos testes. Não foi criada uma função definer adicional nem modificado ownership de schema.

Referências de segurança: [PostgreSQL 17 — CREATE FUNCTION](https://www.postgresql.org/docs/17/sql-createfunction.html), [Supabase — funções invoker/definer](https://supabase.com/docs/guides/database/functions). As conclusões sobre a aplicação foram verificadas contra o código local e os testes isolados, não inferidas somente dessas referências.
