# Fase 2.3 — SDR Inteligente com Groq e WhatsApp

## Resultado e auditoria

O SDR web agora permite buscar e selecionar leads existentes, conferir dados, escolher destinatário provável e serviço, gerar/regenerar uma abordagem, revisar/editar/copiar e abrir uma conversa com o texto preenchido. Não há automação de envio. Não é necessário iniciar o desktop.

A auditoria confirmou que a integração já existe em `core/sales/config.py` e `groq_provider.py`. A configuração reutiliza `GROQ_API_KEY`, `GROQ_MODEL` e `GROQ_TIMEOUT` do ambiente ou `.env` atual, carregado pelo helper `core/providers/environment.py` somente na ação de geração. Não foi criado formulário de chave, integração alternativa ou segredo público.

O nicho está em `leads.segmento`; preferências desktop ficam em `lead_contact_preferences.contact_type`. O histórico está em `outreach`, com revisões em `outreach_revisions`. `LeadRepository`, `SalesAgent.__init__` e o repositório de abordagens podem inicializar schema ou gravar automaticamente: não são instanciados contra a base web. `backend/sdr` adapta as entradas/saídas e usa conexões `mode=ro` nas consultas, `mode=rw` nas escritas autorizadas, sem criar banco ou tabelas.

## Reutilização e arquitetura

Fluxo: navegador → rotas BFF Next `/api/sdr/*` → FastAPI `/v1/sdr/*` → domínio Python/Groq existente. Rotas locais fixas, sem proxy arbitrário, sem CORS aberto, cookies ou credenciais encaminhadas. Chaves permanecem no servidor.

- `WebAgent` herda **o método real `SalesAgent.generate`**, substituindo apenas os adaptadores: leitura segura de lead, evidências da requisição e destino temporário do rascunho. Evita a gravação automática do desktop e a necessidade de migração.
- `build_evidence`, `SYSTEM_PROMPT`, `CONTACT_GUIDANCE`, `SalesGeneration` e validação de mensagem são compartilhados. Telefone, e-mail e observações CRM não são enviados ao modelo; strings legadas de evidência são limitadas a 1500 caracteres por campo.
- O mesmo `GroqSalesProvider` usa o SDK oficial, resposta JSON estruturada, zero retries e limite de saída existente. No web, o timeout configurado é limitado a 30 segundos; o BFF espera até 40 segundos. Endpoints síncronos FastAPI executam no threadpool, mantendo a interface responsiva.
- Geração tem uma chamada simultânea por processo, chave de idempotência UUID e cache de resultados/erros por 15 minutos. Repetir a mesma solicitação não cobra outra geração; reutilizar o ID com parâmetros diferentes retorna 409. Há limite de 100 solicitações em memória por janela de retenção. Nenhum prompt ou resposta é registrado em logs pelo adaptador.
- O frontend bloqueia cliques imediatamente com `useRef`, além dos estados desabilitados. Em falha de transporte ambígua, reutiliza o ID na tentativa seguinte; erros controlados permitem nova tentativa explícita. Não há chamadas de IA no carregamento da página.
- O frontend reutiliza Cards, Buttons, tokens, Lucide e Radix Dialog. Resumo de lead, histórico e diálogo de edição são componentes em `src/components/sdr/`. Não foi alterado o layout das outras páginas; apenas os avisos de disponibilidade foram atualizados.

## Endpoints

| FastAPI | BFF Next | Comportamento |
| --- | --- | --- |
| `GET /v1/sdr/leads/{id}` | `GET /api/sdr/leads/{id}` | Dados essenciais, sugestão/origem, número normalizado e motivo de bloqueio |
| `POST /v1/sdr/generate` | `POST /api/sdr/generate` | Gera rascunho temporário, independentemente da flag de escrita |
| `GET /v1/sdr/history/{id}` | `GET /api/sdr/history/{id}` | Até 50 versões, disponibilidade do schema e permissão efetiva de salvamento |
| `POST /v1/sdr/history` | `POST /api/sdr/history` | Salva texto revisado ou aprovado, com backup e flag obrigatória |

Geração: `{leadId, requestId, recipient, service, instruction, previousDraftId?}`. `recipient`: `auto/direct/reception/unknown`; `service`: `auto/website/landing/management/crm/automation`; instrução até 500 caracteres. Retorna `{draftId,leadId,message,angle,contactType,contactSource,state,provider,model}`. Regenerar fornece o token anterior e reutiliza a checagem de versão repetida do agente.

Salvamento: `{draftId,message,status}` com `status` apenas `EDITADA` ou `APROVADA`. Mensagem não vazia até 1200 caracteres. O backend resolve lead/provider/model pelo token, sem confiar em metadados enviados pelo navegador. Aprovar não significa enviar. Pydantic e Zod rejeitam campos extras, enums e tamanhos inválidos. Erros não retornam exceções do SDK, credenciais ou corpos brutos.

## Classificação e instrução de geração

`backend/sdr/policy.py` centraliza as opções de serviço, extensões da classificação e a política adicional do web; a tabela e o prompt existentes continuam em `core/sales`. Primeiro reutiliza a normalização de acentos/caixa e a classificação compartilhada. Quando o resultado é desconhecido, reconhece fotógrafos, freelancers e pequenos prestadores como contato provável direto, e salão com recepção como provável equipe. Segmentos desconhecidos, imobiliária geral e salão pequeno permanecem indefinidos.

Em Automático, uma preferência explícita salva pelo desktop tem precedência. A escolha manual na tela vale para a geração seguinte, sem sobrescrever preferências ou outros dados do lead. Ao trocar de lead, volta a Automático. “Responsável/proprietário” indica intenção de abordagem, não confirma o cargo de quem responderá.

Recepção/equipe pede encaminhamento de forma breve; desconhecido usa abertura neutra perguntando pelo responsável; contato direto faz apresentação objetiva e exploratória. A política restringe ofertas aos cinco serviços solicitados, veta promessas garantidas, fatos inventados e suposta análise de site/Instagram. Dados ausentes não provam ausência de site. Instrução adicional é preferência de redação, não fonte de fatos. Como toda geração probabilística, essas instruções não substituem a revisão humana; os testes simulados verificam contrato e contexto, não a qualidade de uma resposta real do modelo.

## WhatsApp

O backend reutiliza `core.sales.contact.normalize_phone`: DDD brasileiro válido recebe 55; DDI55 já presente é preservado; números internacionais identificados por `+DDI` não recebem prefixo brasileiro. Não inventa DDD/nono dígito e rejeita ramais, caracteres indevidos e números incompletos. Prefere `whatsapp` quando preenchido, senão `telefone`, como no desktop.

`src/lib/sdr-whatsapp.ts` recebe os dígitos normalizados e monta `https://wa.me/NUMERO?text=${encodeURIComponent(message)}`. O link é um `<a target="_blank" rel="noopener noreferrer">` acionado diretamente pelo usuário, sem `await` antes da abertura. Não altera navegador padrão nem usa shell. Acentos, espaços, `&` e quebras de linha são preservados. Texto vazio, número inválido, limite excedido e operação em andamento desabilitam a ação. Copiar continua disponível.

Não exige registrar autorização/origem/data; esses campos existentes não são alterados. As recusas/revogações e o bloqueio “Não contatar” existentes continuam impedindo novas abordagens. A API revalida bloqueio ao gerar e salvar. O link reflete a consulta do lead; use Atualizar leads caso outro processo altere telefone/bloqueio durante a sessão. A aplicação não verifica se o número tem WhatsApp nem detecta confirmação/envio dentro da outra aba.

## Histórico, gravação e preservação

Gerar/regenerar nunca escreve no SQLite, mesmo com `LOUNG_ENABLE_WRITES=1`. O rascunho fica em memória por 15 minutos. Apenas Salvar texto revisado ou Aprovar e salvar versão persiste. Sem flag, o histórico compatível continua legível e a tela explica por que não salva. Sem tabelas/colunas compatíveis, fica indisponível sem migração automática.

O adaptador compartilha **a mesma instância de `SelectionStore`** da prospecção: lock, `BEGIN IMMEDIATE`, conexão que não cria banco e backup SQLite validado antes da primeira mutação por processo. A transação revalida lead, bloqueio e schema. Repetir salvamento idêntico do mesmo token é idempotente. Editar/aprovar versão editável arquiva o texto anterior em `outreach_revisions`; versões encerradas são imutáveis e exigem nova geração. Não altera dados do lead, indicadores, interações ou marca como ENVIADA. Não requer mudança de schema.

Trocar lead, atualizar dados, carregar histórico ou regenerar com texto não salvo abre Salvar / Descartar / Continuar editando. Sem permissão/token válido, o salvamento permanece desabilitado e a cópia continua possível. Fechar/recarregar avisa pelo mecanismo nativo do browser; navegação pela sidebar também pede confirmação. Voltar/avançar do navegador via histórico SPA não tem bloqueio universal: copie/salve antes de usar. Texto manual ou carregado do histórico pode ser editado, copiado e aberto no WhatsApp; nesta fase, para persistir uma nova versão é necessário um token gerado na sessão. Uma aprovação salva torna o editor daquela versão somente leitura; Regenerar cria uma versão editável.

## Executar

Na raiz, PowerShell:

```powershell
backend/.venv/Scripts/python.exe -m pip install -r backend/requirements.txt
backend/.venv/Scripts/python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Em outro terminal:

```powershell
cd web
npm ci
npm run dev
```

Abra `http://127.0.0.1:3000/sdr`. O `.env` existente não precisa ser editado. Para habilitar histórico gravável, defina **no terminal backend**, antes de iniciá-lo, `$env:LOUNG_ENABLE_WRITES='1'`; recomenda-se apontar `$env:LOUNG_DATABASE_PATH` para uma cópia validada primeiro. Não habilitado nem utilizado para escrever na base original durante esta implementação. A aplicação permanece local, sem autenticação: não publicar ou vincular a interfaces externas nesta fase.

## Validação executada

```powershell
$env:PYTHONPATH='.'
backend/.venv/Scripts/python.exe backend/scripts/run_offline_tests.py backend/tests -q --basetemp=backend/.phase23-pytest-final
.venv/Scripts/python.exe backend/scripts/run_offline_tests.py tests/test_sales_groq.py tests/test_outreach.py tests/test_contact_routing.py tests/test_sales_contact.py tests/test_sales_workspace.py -q --basetemp=backend/.phase23-desktop-tests
backend/.venv/Scripts/python.exe backend/scripts/check_sdr_database_copy.py
cd web
npm run lint
npm run typecheck
npm run build
```

Resultado: **76 testes de backend e 160 testes existentes do domínio aprovados**, lint, TypeScript e build aprovados. O runner bloqueia DNS/conexões externas e injeta credenciais fictícias; provider Groq dos testes é simulado. Testes cobrem classificação, ajuste manual, evidências incompletas, configuração e timeout, respostas inválidas/vazias, bloqueio de chamadas concorrentes/idempotência, expiração/capacidade do cache, flags, revisões, backup/falha com rollback e preservação de registros/schema. Regressões existentes de prospecção e API também são executadas. O TestClient emite aviso de depreciação Starlette/httpx; não impede a validação e não foi introduzida dependência apenas para silenciá-lo.

Para reproduzir o fluxo visual sem consumo nem dados reais, na raiz:

```powershell
$env:PYTHONPATH='.'
backend/.venv/Scripts/python.exe -m uvicorn backend.tests.sdr_fixture_server:create_app --factory --host 127.0.0.1 --port 8100
```

Em outro terminal:

```powershell
cd web
$env:LOUNG_API_URL='http://127.0.0.1:8100'
npm run start -- --port 3100
```

Em outro terminal, na raiz:

```powershell
.venv/Scripts/python.exe web/scripts/check_sdr.py
.venv/Scripts/python.exe web/scripts/check_ui.py http://127.0.0.1:3100
```

A fixture cria e elimina **somente banco sintético temporário de teste**, dentro de pasta ignorada. O teste verifica assinatura da fixture antes de agir. O browser intercepta WhatsApp e bloqueia outros destinos externos: nenhuma conversa real é aberta. Capturas locais em `backend/.phase23-visual/`. Validação SDR em 1440, 1024, 768 e 390 px; navegação geral nas seis páginas em três resoluções, teclado/foco, clipboard e ausência de erros JavaScript. A cópia temporária da base existente validou preservação de todos os registros anteriores/schema e backup. A comparação SHA-256 dos 236 arquivos fora de `/web` e `/backend` confirmou desktop, `.env`, motor Places e banco original inalterados.

## Arquivos desta fase

- Novos: `backend/sdr/{__init__,models,policy,routes,service,storage}.py`, `backend/tests/test_sdr_api.py`, `backend/tests/sdr_fixture_server.py`, `backend/scripts/check_sdr_database_copy.py`.
- Backend ajustado: `main.py`, `requirements.txt` (SDK Groq já usado pelo desktop), `scripts/run_offline_tests.py`, `.gitignore`, `README.md`.
- Novos web: quatro handlers em `src/app/api/sdr/`, `src/lib/api/sdr-contracts.ts`, `src/lib/api/sdr-proxy.ts`, `src/lib/sdr-whatsapp.ts`, três componentes em `src/components/sdr/`, `scripts/check_sdr.py`, este relatório.
- Web ajustado: `src/app/sdr/page.tsx`, contratos/client API, avisos em `shared.tsx`/Configurações, `scripts/check_ui.py`, `README.md`, `docs/architecture.md`.

## Limites e próxima etapa

Serviço local de processo único: cache/idempotência/rascunhos expiram em 15 minutos ou no reinício; não usar vários workers nesta fase. Token expirado exige copiar texto e gerar novamente para salvar. A confirmação pelo usuário e a compatibilidade do telefone foram validadas sem chamada real Groq/WhatsApp; entrega real do provedor, login e disponibilidade da conta WhatsApp não foram exercitados. Nenhuma autenticação, Supabase ou integração comercial de envio foi adicionada.

Próxima etapa: introduzir isolamento por organização, autenticação e um armazenamento durável de rascunhos/idempotência antes de oferecer acesso em rede ou vários workers; ampliar edição persistida de histórico e recuperação de rascunhos sem consumo adicional de IA.
