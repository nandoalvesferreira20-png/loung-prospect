# Estado atual do Loung Prospect

Revisão: 23/10/2026, America/Sao_Paulo. Diagnóstico sem implementação. Base: todos os nove documentos de `docs/auditoria-saas/`, releitura do código atual e verificações locais descritas abaixo. Não foram consultados banco real, processos em produção, arquivos de ambiente reais ou contas de provedores.

## Como interpretar os estados

**PRONTA E VALIDADA** refere-se somente ao escopo exato do teste informado, não à homologação comercial. **IMPLEMENTADA, MAS NÃO VALIDADA** significa código presente sem prova integrada atual. **PARCIALMENTE IMPLEMENTADA** indica parte do comportamento necessário ausente. **NÃO IMPLEMENTADA** significa não localizada no inventário/código/schema revisados. **BLOQUEADA** indica impedimento concreto ou falta de evidência obrigatória para liberar o uso.

## Matriz funcional

| Funcionalidade | Estado | Evidência atual e limite |
|---|---|---|
| Validador JWT, escopo unitário | PRONTA E VALIDADA | authorization.py:35 e test_phase31_security: token válido, claims inválidas, assinatura/algoritmo; passaram nesta revisão |
| Contratos e proteção de origem BFF, escopo local | PRONTA E VALIDADA | 16 testes auth/prospecting/team em web/scripts passaram com fetch/identidades simulados; não validam domínio público |
| Login, refresh, recovery e logout completos | IMPLEMENTADA, MAS NÃO VALIDADA | auth-form.tsx, auth/confirm/route.ts, proxy.ts, session-provider.tsx; SDK exercitado com transporte fake; e-mail/HTTPS reais não homologados |
| Dashboard e métricas | IMPLEMENTADA, MAS NÃO VALIDADA | dashboard-data.tsx consome /api/overview; repository.py:104 e crm/service.py:226 consultam dados; sem números fictícios de fallback identificados; carga/E2E não medidos |
| Leitura/pesquisa/paginação de leads | IMPLEMENTADA, MAS NÃO VALIDADA | repository.py:81–101, proxies e leads-table; testes existentes, sem SQL integrado nesta revisão |
| Criar/editar/importar leads no ambiente real | BLOQUEADA | persistence/leads.py e storage.py implementam; histórico de claims-fix registra trigger não implantado/escrita zero; estado efetivo atual não consultado |
| Pipeline e follow-ups | PARCIALMENTE IMPLEMENTADA | crm/service.py:84/200/226; revisão otimista e histórico presentes; escrita real pendente; não há deal separado de lead |
| Busca Google Places | PARCIALMENTE IMPLEMENTADA | GooglePlacesProvider, JobManager e PgJobManager; só uma busca por org/processo, sem fila compartilhada; licença, retenção e produção não homologadas |
| Resultados, importação e snapshots | PARCIALMENTE IMPLEMENTADA | persistence/searches.py: checkpoint inicial/final e fallback SQL; expiração do cache não apaga snapshot; import depende da escrita |
| Exportação CSV/Excel | IMPLEMENTADA, MAS NÃO VALIDADA | prospecting/jobs.py:174: export de busca, neutraliza fórmulas; testes de export existem mas não foram executados agora; direito contratual não comprovado |
| SDR/Groq | PARCIALMENTE IMPLEMENTADA | sdr/service.py:103, groq_provider.py:generate; draft/histórico e revisão presentes; identidade fixa Fernando/Loung, sem quota financeira por cliente |
| WhatsApp | IMPLEMENTADA, MAS NÃO VALIDADA | sdr-whatsapp.ts e app/sdr/page.tsx: link wa.me com texto, envio manual; não exige APROVADA para abrir; fluxo real não acionado |
| Organizações/memberships | PARCIALMENTE IMPLEMENTADA | schema e middleware; carteira compartilhada; criação/convites manuais e seleção implícita da primeira org |
| Isolamento multiempresa efetivo | BLOQUEADA | RLS/FKs/ContextVar reais no código; sem catálogo atual e suíte negativa A/B integrada não há aceite de segurança |
| Papéis/equipe | IMPLEMENTADA, MAS NÃO VALIDADA | persistence/team.py e team_operations.sql: owner/admin/member, último owner, revalidação SQL; testes nativos não executados |
| Histórico/auditoria | PARCIALMENTE IMPLEMENTADA | triggers, atividades e actor enrichment; implantação pendente de verificação e retenção de payload a decidir |
| Preferências/configurações | PARCIALMENTE IMPLEMENTADA | configuracoes/page.tsx grava displayName/startPage no localStorage, não configura identidade SDR no servidor; cartões de integração são informativos |
| Administração exclusiva Loung/assinaturas | NÃO IMPLEMENTADA | Não localizada nos schemas/rotas; owner do cliente não é superadmin da plataforma |
| Rate limit e custo por cliente | NÃO IMPLEMENTADA | Existem budgets por busca e locks, mas não ledger, reserva ou teto de competência por org |
| Hospedagem centralizada e continuidade | BLOQUEADA | BFF rejeita Host público; API/launcher em loopback; sem release/restore comprovados |

O cliente de 100 pessoas precisa de escopo explícito: carteira compartilhada entre membros não implementa carteira privada por vendedor ou hierarquia de equipes. Esse requisito não foi informado. Se o cliente exigir restrição por vendedor/equipe, reestimar autorização e testes antes de contratar; não prometer esse comportamento.

## Revalidação dos quatro bloqueios anteriores

| Achado anterior | Resultado desta revisão |
|---|---|
| Localhost | Continua. Reprodutor puro carregou isLocalRequest: localhost=true, https://prospect.example.test=false. Proxies ainda restringem upstream a HTTP loopback |
| Escrita/autoria | Código corretivo existe; nenhuma nova evidência de aplicação. Documento mais recente ainda registra não aplicado. Não declarar falha real atual reproduzida |
| Isolamento não verificado | Continua como lacuna de garantia; testes locais adicionais não acessam banco nem substituem A/B SQL |
| Places retenção/export | Continua no código: snapshots guardam rows e não há purge persistente identificado; requisito contratual atual confirmado na fonte oficial, aplicação ao contrato exige parecer externo |

Comparação de hashes de 418 arquivos anteriores à documentação original não identificou mudança de conteúdo desde aquela análise. A nova revisão também capturou baseline de 427 arquivos existentes para preservar código e auditoria anterior.

## Provisórios, mocks e dados fictícios

- Mocks de provedores, usuários e fetch aparecem em backend/tests, tests e web/scripts. São fixtures de validação, não evidência de integração real.
- create_app aceita injeção de provider_factory/sdr_provider_factory para testes; caminho padrão importa providers reais. Não foi encontrada seleção automática de provider fake em produção no código revisado.
- Configurações têm preferências apenas no navegador e cartões estáticos de explicação. Isso não é cadastro comercial persistido nem diagnóstico ao vivo de disponibilidade.
- Dashboard/grafico recebem API; estados indisponíveis exibem travessão/empty state. Textos locais/desktop remanescentes não significam métrica fictícia.
- SQLite legado/Playwright desktop e staging :memory: são distintos. A presença de SQLite em staging não é fallback do banco comercial.
- Busca por mock/fixture/TODO/FIXME/demo não prova ausência absoluta de provisórios; a classificação acima é limitada aos caminhos inspecionados.

## Verificações desta revisão

| Verificação | Resultado |
|---|---|
| Pytest selecionado sem tmp_path/rede/banco | 14 passed, 9 deselected; um aviso Starlette/httpx |
| node --test scripts/auth.test.mjs scripts/prospecting.test.mjs scripts/team.test.mjs, em web | 16 passed; mensagens de erro Auth são cenários fake esperados |
| tsc --noEmit --incremental false | Sem diagnóstico; comando concluído |
| eslint . --max-warnings=0 | Sem diagnóstico; comando concluído com exit 0 |
| isLocalRequest em memória | Host público recusado, local aceito |
| Seleção ampliada pytest com tmp_path | 14 passaram e 7 erros de setup por WinError 5 no diretório temporário; repetição em diretório temporário UUID também bloqueada; não são sete falhas funcionais comprovadas |

O conjunto conclusivo de Python é a seleção limpa de 14 casos; não somar execuções repetidas como cobertura adicional. Nenhuma porcentagem de cobertura de linhas foi calculada. TypeScript/lint não substituem build. Não foram executados build, E2E, carga, testes PostgreSQL/PGlite, migrations ou restauração. Os arquivos existentes de teste SQL incluem DDL/grants/escritas e precisam de ambiente descartável inequívoco futuro.

Mapa de testes e plano para 100 contas: [06-TESTES-E-ESCALABILIDADE.md](06-TESTES-E-ESCALABILIDADE.md).
