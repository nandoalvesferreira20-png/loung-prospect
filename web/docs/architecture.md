# Arquitetura e análise de migração

> Fase 2.4: Kanban, perfil comercial, atividades, retornos e Meu Dia implementados
> sobre o schema desktop, sem migrações. Escrita opt-in, backup e concorrência
> por revisão. Veja [phase-2-4.md](phase-2-4.md).

> Fase 2.3: SDR funcional via BFF/FastAPI, reutilizando `SalesAgent.generate`,
> provider/configuração Groq, evidências, classificação e normalização de telefone
> existentes. Geração em memória; histórico no schema desktop sem migrações.
> Veja [phase-2-3.md](phase-2-3.md) para fluxos, testes e limites atuais.

> Atualização Fase 2.1: a API local somente leitura está implementada em `/backend`,
> e Dashboard/Leads consomem seus dados pelo BFF Next.js. O inventário abaixo
> descreve a análise original da Fase 1. Veja [a auditoria e implementação atual](phase-2-1.md).

> Fase 2.2: prospecção Google Places, jobs locais e importação selecionada agora
> estão implementados. A escrita permanece opt-in e sem migrações automáticas.
> Veja [phase-2-2.md](phase-2-2.md) para a arquitetura atual e validação.

## Situação encontrada antes da implementação

O repositório é uma aplicação Python desktop CustomTkinter, com um fluxo CLI legado e testes Python. Não havia frontend JavaScript nem uma estrutura web a preservar. Havia alterações locais anteriores no desktop; elas foram mantidas. A nova aplicação tem seu próprio `package.json`, lockfile e configuração em `/web`.

| Funcionalidade                   | Implementação existente                                                           | Reaproveitamento na próxima fase                                                                     |
| -------------------------------- | --------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------- |
| Inicialização desktop/CLI        | `main.py`, `app.py`, `ui/`                                                        | Preservar; não importar widgets na API                                                               |
| Busca de empresas                | `core/providers/google_places.py`                                                 | Reutilizar provider Places API New no servidor                                                       |
| Orquestração da prospecção       | `core/prospecting/service.py`                                                     | Reutilizar limites, cancelamento, deduplicação e qualificação em jobs                                |
| Qualificação                     | `core/qualification/`                                                             | Reutilizar regras Python de score e prioridade                                                       |
| Carteira e interações            | `core/database/`, `core/commercial/`                                              | Adaptar serviços e repositórios; preservar aliases dos status legados                                |
| SQLite                           | `core/database/schema.py`, repositórios; `data/loung_prospect.db`                 | Não acessado nesta fase; futura camada de persistência por organização                               |
| SDR, versões e revisão           | `core/sales/agent.py`                                                             | Reutilizar o fluxo de rascunho, edição, aprovação e regeneração                                      |
| GroqCloud                        | `core/sales/groq_provider.py`, `config.py`, `provider.py`                         | Reutilizar configuração/modelo/provider existentes no backend; chave nunca no cliente                |
| Nicho e interlocutor provável    | `core/sales/contact_routing.py`, `core/database/contact_preference_repository.py` | Preservar classificação e ajuste manual por lead                                                     |
| WhatsApp                         | `core/sales/contact.py`                                                           | Preservar normalização, codificação e restrições de contato; abertura continua manual                |
| Navegador e preferências desktop | `core/browser_launcher.py`, `ui/browser_action.py`, `ui/settings.py`              | Apenas desktop: registry/PATH, processos e JSON por usuário do SO                                    |
| Importação/exportação            | `core/importers/excel_leads.py`, `core/exporter.py`                               | Reutilizar transformação de planilhas; substituir diálogos e `os.startfile` por upload/download HTTP |
| Protótipos                       | `core/prototype/`, `templates/`, `ui/prototype_studio.py`                         | Fora da Fase 1; avaliar jobs/arquivos isolados por organização                                       |

Também foram identificados `assets/`, `scripts/`, `tests/`, saídas de exportação e artefatos de build desktop. Nada disso foi movido ou removido. Nenhum arquivo `.env` foi lido para extrair valores, alterado ou copiado para o frontend.

## Decisão: Next.js no frontend, FastAPI para o domínio Python

O App Router organiza layouts e rotas; os componentes interativos são client components pequenos. Tailwind define tokens de cor e superfícies, shadcn/ui fornece o padrão de primitivas locais (Radix/CVA), Lucide mantém a iconografia, React Hook Form/Zod valida entradas e Recharts prepara os gráficos sem dados inventados. Fontes do sistema evitam dependência de download no build.

Recomenda-se uma API FastAPI separada **neste mesmo repositório** na Fase 2. O domínio já está em Python e inclui regras de qualificação, deduplicação, geração de mensagens, histórico e planilhas. Reescrever tudo em handlers Next.js aumentaria a chance de divergência com o desktop.

O Next.js possui uma camada BFF de encaminhamento para as duas consultas de leitura. Não duplica regras comerciais, não armazena chaves em `NEXT_PUBLIC_*` e não executa prospecção em requisições de renderização. A API FastAPI implementada em `/backend` é local e somente leitura; sessão e autorização continuam pendentes para uma futura publicação.

`src/lib/api/contracts.ts` define a fronteira tipada; `client.ts` consulta leads e indicadores por HTTP. Seus resultados distinguem `ready`, `not-connected` e `error`. Prospecção e geração permanecem indisponíveis. Não há respostas de sucesso simuladas ou chamadas aos providers no fluxo da aplicação. Fixtures sintéticas são exclusivas dos testes.

### Contratos futuros sugeridos

- `GET /v1/overview`, `GET /v1/leads` com filtros e paginação no servidor.
- `POST /v1/prospecting/jobs` e consulta/cancelamento do job, com limites e idempotência.
- `GET/PATCH /v1/leads/{id}` e recursos próprios para interações e classificação de contato.
- `POST /v1/leads/{id}/drafts`, edição/aprovação e histórico de versões preservando revisão humana.
- Upload de importação e download de exportação com validação, limites e isolamento.

As seis etapas iniciais do quadro são um subconjunto visual de `core/commercial/values.py`. A futura API deve preservar **todos** os status, aliases e estados de restrição; não deve converter valores legados ao apenas ler um registro. Telefone, evidências do lead e restrições de contato devem continuar validados no servidor.

## Multiempresa e segurança da próxima fase

A organização mostrada nesta fase é contexto de apresentação, não uma fronteira de segurança. Não há login nem isolamento multiempresa implementado. Antes de publicar dados reais, implementar sessão, autorização e organização derivada da identidade autenticada no backend; nunca confiar em um `organizationId` enviado pelo navegador como autorização.

Adicionar organização a leads, interações, drafts, jobs e exportações; garantir filtros obrigatórios por organização nos repositórios, índices e testes de isolamento. Planejar PostgreSQL e migrações versionadas antes de uso multiempresa, sem migração destrutiva da base desktop. Manter segredos no servidor, auditoria, limites por organização e tarefas longas fora do ciclo HTTP. Supabase não é necessário para esta fase e não foi adicionado.

## Diferenças importantes do ambiente web

Um site comum não pode escolher livremente Edge/Chrome instalados no Windows. A preferência de navegador do desktop permanece intacta. A versão web futura abrirá um link validado `https://wa.me/` pelo contexto do navegador, sem shell e sem envio automático. A escolha do aplicativo será responsabilidade do sistema/navegador, salvo um futuro aplicativo auxiliar explicitamente autorizado.

As preferências web desta fase são locais ao perfil do navegador. Não leem nem sobrescrevem o JSON de preferências desktop. O rascunho SDR é temporário e está claramente identificado; ainda não promete persistência na carteira.

## Ordem recomendada

1. Definir contratos HTTP, organização, autorização e política de acesso antes de disponibilizar dados reais.
2. Criar FastAPI com serviços Python existentes e testes usando SQLite temporário/providers simulados.
3. Conectar leitura de leads e indicadores; validar paginação, status e erros.
4. Conectar SDR, versões e preferências de contato; garantir revisão humana e proteção de edições.
5. Adicionar jobs de prospecção, importação/exportação e limites; depois preparar hospedagem segura.

Referências de configuração: [Next.js App Router](https://nextjs.org/docs/app/getting-started/installation), [Tailwind com Next.js](https://tailwindcss.com/docs/installation/framework-guides/nextjs), [shadcn/ui com Next.js](https://ui.shadcn.com/docs/installation/next).
