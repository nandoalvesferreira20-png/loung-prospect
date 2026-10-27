# Fase 3.2 — equipe, permissões e operações

## Estrutura aproveitada

O fluxo permanece Next.js BFF → FastAPI → PostgreSQL. Supabase Auth verifica JWT; a API consulta membership em cada requisição, valida a organização selecionada contra essa consulta e configura identidade/organização na transação com `SET LOCAL ROLE loung_api`. Não há conta administrativa na conexão operacional, fallback SQLite ou confiança em organização enviada no corpo. Login, cookies SSR, Pipeline, interações, contatos e persistência SDR foram preservados.

Papéis existentes: owner, admin e member. Todos operam a carteira compartilhada. Owner gerencia papéis e remoção de acessos; owner/admin consultam o histórico global. Member consulta o histórico do próprio lead pelas rotas já existentes. Não foi criado um limite artificial de quatro contas. Contas sem membership continuam bloqueadas com `MEMBERSHIP_REQUIRED`; não ganham uma organização padrão.

## Funcionalidades e arquivos

- `backend/persistence/team.py`: listagem da equipe, alteração de papel, remoção de membership e histórico com paginação por cursor. E-mails são obtidos por função SQL restrita ao workspace, sem conceder leitura de `auth.users` ao runtime. Erros de acesso, integrante ausente e último owner recebem mensagens controladas.
- `backend/persistence/leads.py`: criação manual pelo mesmo mecanismo de deduplicação já usado na importação selecionada; consulta dos campos editáveis e edição com revisão otimista. Empresa, localização, contatos e observações são editáveis; organização, autoria, IDs e campos internos não são aceitos do navegador. Alterar contato não registra envio nem redefine consentimento de WhatsApp.
- `backend/persistence/runtime.py`: registra as rotas e aplica `LOUNG_ENABLE_WRITES` a todas as requisições de mutação, antes dos handlers/provedores. A sessão informa a capacidade de escrita à interface.
- `supabase/migrations/202610200002_team_operations.sql`: funções restritas de listagem e gestão, identidade da membership imutável, proteção do último owner com serialização por organização e auditoria de associação/papel/remoção. Não concede INSERT/UPDATE/DELETE de membership ao runtime. Eventos de equipe contêm IDs e papéis, sem e-mail, tokens ou credenciais. Migrations anteriores não foram editadas.
- `web/src/lib/api/team-proxy.ts` e rotas em `app/api/team`, `app/api/organization/activities`, `app/api/leads`: caminhos fixos, cookies tratados no servidor, bearer verificado, validação estrita de campos, proteção de origem e respostas sem cache. Headers de organização/cookies do navegador não são encaminhados.
- `web/src/app/configuracoes/equipe/page.tsx`: integrantes reais da organização, nome/e-mail/papel e vínculo, ações disponíveis para owner com escrita habilitada. A própria conta não pode ser alterada. “Vinculado” significa membership, não sessão ativa nem ausência de bloqueio no Auth.
- `web/src/app/configuracoes/atividades/page.tsx`: metadados de auditoria para owner/admin; omite payloads, contatos e mensagens. Autoria ausente é identificada como operador/importação.
- `web/src/components/lead-editor.tsx`, páginas `leads/novo` e `leads/[id]/editar`: formulário de criação/edição com tratamento de duplicidade, escrita desabilitada e revisão desatualizada. Links adicionados à carteira e ao perfil.
- `web/src/components/session-provider.tsx`, `web/src/app/configuracoes/page.tsx`: capacidade de escrita, ID de sessão e entrada para equipe.

As rotas existentes de estágio, interações, follow-up, contatos e SDR continuam usando transações, revisão, validação de membership, RLS e auditoria da Fase 3.1. A nova edição manual registra `leads.update`; os valores pessoais de contato não foram acrescentados ao payload de auditoria existente.

## Convites: decisão desta entrega

Não foi adicionada Admin API nem credencial `service_role`. Para as quatro contas iniciais, o operador envia o convite pelo Supabase Auth, com as configurações de expiração e redirect revisadas no projeto, e provisiona a membership após confirmar a identidade da conta. O link deve usar a confirmação de Auth existente; não se aceita papel ou organização vindos de metadados editáveis pelo usuário. Convite de Auth e membership são etapas separadas. Convites não criam membership automaticamente.

Antes de provisionar, conferir o UUID da organização, o UUID do usuário em Auth, a confirmação do e-mail e a inexistência de vínculo duplicado. Criar `profiles` com ID daquele usuário e nome conferido; inserir membership com papel `member`. A constraint UNIQUE impede duplicidade de organização/usuário. Fazer isso em transação por um operador, nunca pelo login operacional. Promover para admin/owner é ação separada de um owner. Não remover o owner inicial antes de confirmar um segundo owner.

Um fluxo automático futuro precisará de componente administrativo separado, token armazenado como hash, expiração, uso único, revogação, rate limit, associação ao e-mail confirmado e proteção contra duplicidade. Essa integração **não está implementada nem validada** nesta entrega. Não existe endpoint de envio de convite; o teste confirma que essa operação não é exposta. Nenhum convite/e-mail real foi enviado. A confirmação de convite e expiração reais dependem do Supabase e precisam de homologação com contas autorizadas.

## Implantação manual

1. Preservar o backup/PITR PostgreSQL e os relatórios da migração concluída. Não repetir a importação SQLite. Manter `LOUNG_ENABLE_WRITES=0` no backend de produção.
2. Revisar a migration incremental e aplicá-la primeiro em um projeto PostgreSQL/Supabase de homologação. O executor precisa ser dono das tabelas/funções ou ter poderes de implantação e leitura de `auth.users`; isso não muda a credencial do backend. Executar o arquivo como uma transação completa, uma vez, usando o mecanismo de migrations. Não reaplicar migrations já registradas.
3. Validar nessa base owner/admin/member de duas organizações. Conferir listagem, negação de papel, isolamento, auditoria, último owner e expiração/revogação do Auth. Somente no processo de homologação explicitamente autorizado, habilitar `LOUNG_ENABLE_WRITES=1` e reiniciar a API. Testar com registros sintéticos nessa base separada.
4. Após revisão, aplicar somente a migration nova no projeto real e publicar backend/frontend compatíveis, ainda com escrita desligada. Verificar login e equipe em leitura. Uma conta só tem ações de owner se sua membership já tiver esse papel; não há promoção automática.
5. Convidar e vincular os integrantes pelo fluxo de operador descrito acima. Validar cada login individual. Não compartilhar a conta do administrador.
6. Habilitar escrita em produção **somente após confirmação explícita do responsável**, alterando `LOUNG_ENABLE_WRITES=1` no ambiente do processo FastAPI e reiniciando-o. Validar uma operação previamente combinada, autoria e histórico. Não usar os leads reais como massa de teste.
7. Para interromper alterações, retornar a flag a `0` e reiniciar a API. Isso não reverte registros já confirmados. Não executar DELETE/TRUNCATE, desativar RLS ou repetir importação para reverter esta versão.

Nenhuma variável de produção adicional é necessária. Permanecem Supabase público no Next, `SUPABASE_URL`, `LOUNG_POSTGRES_DSN` restrito e `LOUNG_ENABLE_WRITES` no FastAPI. Não copiar `LOUNG_MIGRATION_DSN` ou chave administrativa para o frontend/runtime. Esta implementação não editou arquivos `.env` nem ativou escrita de produção.

## Testes e reprodução

Banco de testes PostgreSQL em memória, sem DSNs do ambiente:

```powershell
node web/scripts/phase31-postgres.mjs
# Em outro terminal:
backend/.venv/Scripts/python.exe -m backend.scripts.run_offline_tests backend/tests -q --basetemp=backend/.phase32-validation -o cache_dir=backend/.pytest_cache
# No diretório web:
npm.cmd run typecheck
npm.cmd run lint
node --test scripts/auth.test.mjs scripts/team.test.mjs
```

A suíte executa a migration nova apenas no banco marcado `synthetic-memory-only`. Cobre papéis, CRUD permitido/negado, organização forjada, isolamento, revogação, SQL direto sem privilégio, proteção do último owner, auditoria, rollback, idempotência e concorrência das operações existentes. Há testes específicos para ausência do endpoint de convite e bloqueio geral da flag de escrita.

Resultado em 20/10/2026: **142 testes Python passaram**, incluindo dez casos novos da Fase 3.2; **8 testes Node Auth/BFF passaram**. TypeScript e ESLint passaram. O build de produção Next.js com webpack passou em cópia temporária sem `.env` real. O QA de navegador passou na versão final compilada, incluindo alteração de papel persistida, equipe em desktop/mobile, criação/edição de lead e auditoria. Dois owners concorrentes não conseguem remover os poderes um do outro simultaneamente; falha na auditoria reverte a alteração de papel. Houve apenas o aviso preexistente de depreciação Starlette/httpx na suíte Python.

QA visual: `backend/tests/phase32_fixture_server.py` cria quatro contas **somente no banco sintético** e expõe Auth/API locais na porta 8100. `web/scripts/check_phase32.py` usa Edge/Playwright e exige a assinatura do fixture; testa equipe, papel persistido, layout em 1440/1024/390 px, criação/edição e histórico. O Next de QA deve ser compilado/servido na porta 3100 com URL/key públicas sintéticas e `LOUNG_API_URL=http://127.0.0.1:8100`, sem carregar `.env` real. Se houver Next aberto, usar uma cópia temporária dos fontes sem arquivos de ambiente. Não encerrar o servidor do usuário para fazer o teste.

## Limites de validação

Os testes locais não homologam entrega de e-mail, configuração de Auth/redirects no projeto real, permissões do executor de migration nem operação sob carga no Supabase hospedado. Nenhuma migration desta fase foi aplicada ao Supabase real. SQLite e os 160 leads reais não foram modificados.
