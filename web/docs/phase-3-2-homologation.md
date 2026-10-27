# Fase 3.2 — homologação de escrita

Data: 22/10/2026. Resultado: **implementação aprovada nos testes isolados; escrita real ainda não liberada**.

Atualização posterior: [correção do trigger por claims](phase-3-2-claims-fix.md) elimina a necessidade de conceder USAGE em auth para autoria. A concessão mencionada abaixo foi uma alternativa anterior, substituída pela migration incremental revisada. O novo SQL também não foi aplicado no Supabase real; consultar o documento de correção antes de qualquer implantação.

## 1. Funcionalidades implementadas

| Operação | Interface / API FastAPI | Proteções e resultado |
|---|---|---|
| Criar lead | `/leads/novo` → POST `/v1/leads` | Modelo de campos permitido, deduplicação por organização, autoria e auditoria por trigger. |
| Editar lead | `/leads/<id>/editar` → PATCH `/v1/leads/<id>` | Revisão otimista, resposta 409 para edição desatualizada; organização/autor não aceitos no corpo. |
| Movimentar Pipeline | Abrir o lead pelo Pipeline e usar **Etapa atual / Salvar etapa** → PATCH `/v1/leads/<id>/stage` | Etapas existentes, confirmação para estados sensíveis, transação atômica com histórico. Não se presume contato por abrir WhatsApp. |
| Registrar interação | Perfil do lead → POST `/v1/leads/<id>/activities` | Inserção de histórico, revisão, confirmação para fatos comerciais; não altera etapa por inferência. |
| Gerar abordagem SDR | `/sdr?leadId=<id>` → POST `/v1/sdr/generate` | Provider Groq, contexto autorizado, bloqueio de não contatar, idempotência, limites e rascunho temporário. |
| Armazenar abordagem | **Salvar texto revisado** / **Aprovar e salvar versão** → POST `/v1/sdr/history` | Persistência explícita; revisão anterior preservada; versão aprovada encerrada para edição. Não envia mensagem. |
| Consultar auditoria | `/configuracoes/atividades` → GET `/v1/organization/activities` | Owner/admin; autoria e organização reais; UI omite os payloads de antes/depois. |
| Equipe | `/configuracoes/equipe` | Gestão por owner, bloqueio de autoalteração e do último owner, auditoria e serialização de alterações. Convite automático não está implementado. |

O caminho permanece navegador → Next BFF → FastAPI → PostgreSQL. Supabase verifica identidade; JWT é validado criptograficamente no backend, incluindo algoritmo, assinatura, issuer, audience e expiração. O papel de negócio vem da membership consultada no banco, não do corpo ou de metadados editáveis. Cada transação usa `SET LOCAL ROLE loung_api`, identidade derivada do JWT e organização validada. RLS, autoria e auditoria continuam ativas.

As escritas de negócio são compartilhadas por owner/admin/member autorizados da mesma organização. Falhas de autorização incluem ausência de JWT/membership e acesso a outra organização. Gestão de equipe é reservada ao owner. Não foi mudado esse modelo de permissões.

## 2. Configuração real: inspeção somente leitura

Foi adicionado `backend/scripts/check_phase32_readiness.py`. O script recusa login administrativo antes de conectar, abre transação read-only, consulta catálogos/ACLs e termina com rollback. Não chama funções de mutação, não aplica migrations, não lê valores de leads/contatos e não imprime DSN, tokens, senhas ou chaves.

Execução:

```powershell
backend/.venv/Scripts/python.exe -m backend.scripts.check_phase32_readiness --env-file .env --output artifacts/qa/phase32-homologation-20261022/real-catalog-readiness.json
```

Resultado final: **183 de 184 verificações passaram**. O exit code 1 é intencional: o preflight encontrou uma pendência real.

- A conexão com o arquivo inspecionado utiliza o login restrito `loung_web`, pode assumir `loung_api` e não possui poderes administrativos/bypass RLS. Os processos FastAPI encontrados usam o launcher explícito com `--env-file .env`, sem DSN na linha de comando. Variáveis eventualmente exportadas no terminal têm precedência sobre o arquivo; por isso a sessão da interface também deve ser conferida na janela manual.
- `LOUNG_ENABLE_WRITES=0` continua na configuração. Não foi alterado.
- Os grants de tabelas e sequências, políticas de escrita, RLS/FORCE RLS, triggers de autoria/auditoria e funções restritas de equipe passaram nas verificações executadas.
- `lead_interactions` e `outreach_revisions` têm INSERT, mas não UPDATE/DELETE. Isso é deliberado para preservar histórico; não se deve ampliar esses privilégios.
- **Falta USAGE no schema `auth` para `loung_api`.** Esta é a única falha dos 184 checks de catálogo.
- `GROQ_API_KEY` está presente; **`GROQ_MODEL` está ausente** na configuração explícita inspecionada. Nenhum valor foi impresso. Uma configuração adicional exportada em outro terminal não foi lida da memória do processo.

## 3. Problemas e ajustes necessários

### USAGE em auth: bloqueia escrita mesmo com login funcionando

O trigger `public.stamp_actor()` é executado no contexto do runtime e chama `auth.uid()`. A ausência de USAGE foi reproduzida exclusivamente no PostgreSQL descartável: GET de sessão respondeu 200, mas POST de criação de lead respondeu 503/DB_PERMISSION_DENIED e nenhuma linha/auditoria parcial persistiu. Restaurar somente USAGE no banco sintético fez a mesma criação responder 201.

Não foi tentada uma criação no banco real. A conclusão combina o catálogo real com a reprodução isolada do mesmo desvio de ACL, não uma gravação real.

O ajuste mínimo já está descrito na migration existente `supabase/migrations/202610200001_repair_auth_schema_usage.sql`: conceder apenas USAGE no schema auth a loung_api. **Não foi executado no Supabase real.** Um operador autorizado deve revisar essa correção separadamente, mantendo a flag de escrita em zero. Não é motivo para reaplicar a Fase 3.2, conceder SELECT em auth.users, CREATE no schema, poderes administrativos ou UPDATE nas tabelas de histórico.

Após eventual correção autorizada, repetir o preflight; ele deve terminar com `readyByCatalog:true` e nenhum failedCheck.

### Provider SDR

Definir no ambiente exclusivo do backend um `GROQ_MODEL` acessível à chave existente. Não copiar chave/modelo para NEXT_PUBLIC, não substituir credenciais e não escolher um modelo automaticamente. A disponibilidade e a cota reais do provider não foram homologadas: nenhum pedido Groq foi enviado nesta tarefa.

Gerar uma abordagem pode consumir cota e envia ao provider o contexto permitido do lead; usar apenas dados fictícios no teste. Os rascunhos permanecem em memória por 15 minutos e se perdem com reinício da API; salvar explicitamente antes disso. O histórico salvo permanece no banco.

### Um único usuário

A conta única permite homologar operações do owner, mas não os cenários manuais de admin/member, revogação ou concorrência entre usuários reais. Esses cenários passaram com identidades sintéticas. Não criar/remover usuários, alterar o próprio papel ou testar remoção do único owner no ambiente real. Convite e provisionamento de outro integrante ficam fora desta janela.

## 4. Testes realizados

Foi baixado o pacote portátil oficial PostgreSQL/EDB 17.11 e criado um cluster novo, descartável, em `127.0.0.1:55431`, sem serviço Windows e sem DSN de ambiente. O bootstrap verificou que o banco estava vazio e instalou o schema de teste somente ali. Os marcadores sintéticos são conferidos antes das fixtures de escrita. O runner bloqueou DNS/conexões fora do loopback e os providers foram substituídos por stubs.

| Execução | Resultado |
|---|---|
| Suíte completa `backend/tests` | **169 aprovados**, 0 falhas, 0 erros, 0 pulados, 79,66 s |
| Suíte de escrita após acrescentar a reprodução da ACL auth | **10 aprovados**, 0 falhas, 0 pulados, 36,73 s; inclui nove casos já executados e um novo |
| Auth/cookies/proxy/BFF Node | **9 aprovados** |
| Origem, validação e encaminhamento de BFF equipe | **2 aprovados** |
| Catálogo real, somente leitura | **183/184**, falha esperada em USAGE do schema auth |

Cobertura: owner cria/edita lead, revisão desatualizada, Pipeline, interações, geração/salvamento/revisão SDR, idempotência, auditoria com actor/organização corretos, identidade não forjável, acesso entre organizações negado, revogação, grants efetivos, último owner, falha na auditoria e rollback integral. Inclui nove cenários de concorrência nativa com conexões independentes em READ COMMITTED, REPEATABLE READ e SERIALIZABLE.

Os novos testes injetam falha de auditoria em criação, edição, etapa, interação, salvamento SDR e revisão SDR, e comparam as linhas de leads, interações, abordagens, revisões e auditoria antes/depois. Também verificam que a flag desabilitada impede todas essas mutações antes de instanciar o provider.

O dataset de preservação do teste tem 160 leads e 17 interações sintéticos. A suíte compara linhas e mapeamentos antes/depois da implantação sintética. Isso não é uma nova contagem nem uma alteração dos 160/17 registros reais informados pelo usuário.

Comandos executados na raiz, com o cluster sintético já inicializado:

```powershell
backend/.venv/Scripts/python.exe -B -m backend.scripts.run_offline_tests backend/tests -q --basetemp=temp/phase32-homologation-20261022/pytest -p no:cacheprovider --junitxml=temp/phase32-homologation-20261022/backend-tests.xml
backend/.venv/Scripts/python.exe -B -m backend.scripts.run_offline_tests backend/tests/test_phase32_writes.py -q --basetemp=temp/phase32-homologation-20261022/writes-regression -p no:cacheprovider --junitxml=temp/phase32-homologation-20261022/writes-regression.xml
node web/scripts/auth.test.mjs
node web/scripts/team.test.mjs
```

As suites sintéticas montam/alteram schema e ACLs de teste exclusivamente no cluster descartável. Nenhuma migration foi executada no Supabase real. Não houve alterações no código de produção nesta etapa; foram adicionados diagnóstico, testes e este roteiro. Lint/build do frontend não foram repetidos, pois nenhum fonte ou configuração de produção foi modificado nesta tarefa. Há apenas o aviso preexistente de depreciação Starlette/httpx.

Evidências em `artifacts/qa/phase32-homologation-20261022/`: `backend-tests.xml`, `writes-regression.xml`, `real-catalog-readiness.json` e `summary.json`. Os relatórios não contêm credenciais nem dados pessoais reais.

Ao concluir, o PostgreSQL descartável foi encerrado e seu ZIP, binários e cluster sintético foram removidos; relatórios e evidências foram preservados. O shutdown normal ficou aguardando workers no Windows; foram encerrados somente processos identificados pelo caminho exclusivo dos binários de QA. Nenhum serviço real foi interrompido.

## 5. Pré-condições para uma janela de escrita real

1. Resolver o USAGE de auth mediante aprovação específica e repetir o preflight até aprovação dos checks de catálogo. Não executar migrations automaticamente.
2. Configurar o modelo SDR e confirmar disponibilidade/cota, se SDR fizer parte da janela.
3. Confirmar backup/PITR recuperável e registrar os totais e estado de referência da organização. Preparar evidência somente leitura que permita comparar os registros reais existentes após o teste.
4. Aprovar explicitamente a janela, o operador owner e o único lead fictício a ser criado. Suspender uso paralelo, importações e pesquisas que possam salvar leads.
5. Usar somente `http://127.0.0.1:3000`, conferir usuário/organização corretos e reservar uma janela curta para executar o roteiro.

**Risco concreto:** a flag libera todas as mutações autorizadas da API, não apenas o lead com prefixo de teste, e não apenas o owner. A restrição a um único lead é um procedimento de operação, não um filtro técnico implementado. A criação acrescenta um registro e pode afetar contadores/métricas. Desabilitar a flag bloqueia novas mutações, mas não desfaz alterações já confirmadas. Não remover auditoria nem fazer limpeza automática do lead de teste.

## 6. Procedimento para habilitar e encerrar — não executado

Somente depois das pré-condições e da autorização: interromper o FastAPI antigo com Ctrl+C no próprio terminal. Na raiz do projeto, exportar a flag apenas naquele processo e iniciar explicitamente:

```powershell
# SOMENTE DEPOIS DE AUTORIZAÇÃO PARA A JANELA REAL
Set-Location 'C:\Users\BR0450988468\Desktop\loung\loung-prospect'
$env:LOUNG_ENABLE_WRITES='1'
backend/.venv/Scripts/python.exe -m backend.scripts.run_api --env-file .env --port 8000
```

O `.env` pode permanecer em zero: a variável exportada no terminal tem precedência. Não alterar a DSN, o login PostgreSQL nem as credenciais de Auth. Recarregar a interface e confirmar `/api/session` com `role=owner` e `writesEnabled=true`, sem copiar tokens/headers. Se continuar false ou retornar 401/403/503, interromper e diagnosticar; não contornar a proteção.

Ao concluir ou diante de qualquer divergência, interromper novamente o FastAPI, retornar a flag para zero e reiniciar:

```powershell
$env:LOUNG_ENABLE_WRITES='0'
backend/.venv/Scripts/python.exe -m backend.scripts.run_api --env-file .env --port 8000
```

Recarregar e confirmar `writesEnabled=false`. Esse encerramento não é rollback dos registros confirmados. Nenhum desses comandos de habilitação foi executado nesta tarefa.

## 7. Roteiro manual: somente um lead exclusivo

Nome sugerido: `HML-FASE32-20261022-<sufixo-único>`. Antes de criar, pesquisar o nome para evitar duplicatas. Não selecionar nem editar os 160 leads reais.

| Passo | Ação na interface | Evidência de aprovação |
|---|---|---|
| 0. Identidade | Confirmar owner, organização e flag true após aprovação da janela | `/api/session` 200; perfil/organização esperados; nenhum segredo registrado. |
| 1. Criar | `/leads/novo`: empresa com o prefixo, cidade/segmento fictícios; telefone/WhatsApp/site em branco, e-mail opcional `homologacao@example.invalid` | POST 201, um único lead novo, ID anotado; nunca usar telefone ou site real. |
| 2. Editar | Abrir esse ID → **Editar dados e contato**; editar cidade e observações com `HOMOLOGAÇÃO — dados fictícios, sem envio nesta janela` | Salvar, recarregar e conferir persistência; mesmo ID e mesmo autor de criação. |
| 3. Pipeline | Filtrar pelo nome, abrir o lead e mudar Novo → Em conversa por **Salvar etapa** | Recarregar Pipeline/perfil e conferir coluna/etapa e histórico da mudança. Não marcar contato/conversão reais. |
| 4. Interação | No mesmo perfil, tipo **Observação**, canal outro, descrição fictícia com o prefixo | Uma observação persistida, data e autoria do operador; nenhuma alteração de outro lead. |
| 5. SDR | `/sdr?leadId=<id>`; gerar abordagem com dados fictícios; revisar e usar **Salvar texto revisado** | Geração válida e salvamento explícito; manter o rascunho aberto para o próximo passo. Sem clicar em WhatsApp ou enviar mensagens. |
| 6. Revisão SDR | Ainda no mesmo rascunho, antes dos 15 minutos de expiração, editar e salvar outra vez; só então recarregar | Texto e autoria persistem; revisão anterior preservada. Repetir salvamento idêntico não duplica; versão aprovada exige nova geração para editar. |
| 7. Auditoria | `/configuracoes/atividades`, conferir eventos referentes exclusivamente ao ID de teste | `leads.insert/update`, `lead_interactions.insert`, `outreach.insert`; `outreach_revisions.insert/outreach.update` quando houver revisão; actor do owner e organização corretos. |
| 8. Encerrar | Repor flag zero, reiniciar API e recarregar | Sessão informa false; controles de escrita bloqueados. Comparar evidência dos registros reais de referência. |

Uma movimentação de etapa também cria uma interação de histórico; com apenas essa movimentação e uma observação, são duas novas interações, além das 17 informadas inicialmente. O total de leads passa de 160 para 161 se nenhum outro registro for criado. Não usar esses totais como substitutos de uma comparação dos registros preexistentes. Manter o lead de homologação claramente identificado; sua remoção ou exclusão das métricas requer decisão separada.

## 8. Critérios para uso diário

- Preflight de catálogo aprovado, sem login administrativo, sem ampliação de DML e com RLS, triggers e auditoria ativos.
- Modelo/cota/conectividade SDR confirmados na configuração efetiva, se essa função for liberada.
- Janela manual aprovada em todos os passos: persistência, Pipeline, interações, SDR e autoria/auditoria corretos.
- Os 160 leads e 17 interações preexistentes permanecem íntegros; novos registros limitam-se ao roteiro autorizado e estão identificados.
- Nenhum envio externo realizado; nenhum segredo ou dado pessoal real incluído nas evidências de teste.
- Falhas e conflitos apresentam erros controlados, sem duplicação por repetição; o operador sabe recarregar após 409 e preservar texto após timeout.
- Plano de restauração e retorno a somente leitura disponível. A flag permanece zero até decisão explícita de liberação; concluir a homologação não implica manter escrita ligada.
- Validações multiusuário reais continuam pendentes até provisionamento autorizado de outras contas; não confundir a cobertura sintética com homologação manual de usuários que ainda não existem.

Referência do binário de testes: [PostgreSQL Windows](https://www.postgresql.org/download/windows/) / [EDB portable binaries](https://www.enterprisedb.com/download-postgresql-binaries). SHA-256 do ZIP usado: `80379b2c04d51c30225532e0ae04509899141e9957ed096fe749d7fd9df8f82f` (hash local de identificação, não uma assinatura independente do fornecedor).
