# Testes, capacidade e preparação para 100 contas

Data: 23/10/2026. **Nenhum teste de carga foi executado. Não há capacidade de 100 simultâneos comprovada.** O plano abaixo é futuro e usa somente ambiente isolado e dados sintéticos.

## Contas cadastradas não equivalem a concorrência

100 contas significam identidades/memberships; não implicam 100 requisições por segundo nem 100 buscas simultâneas. Uma pessoa pode gerar várias requisições; muitas contas podem estar ociosas. Definir no D1: pessoas ativas no pico, páginas e frequência de ações, volume de leads/histórico, buscas/gerações por dia e SLA esperado. Não inferir pico da quantidade de licenças.

O Registry limita 32 **organizações**, não 32 usuários. Cem membros de uma empresa usam uma entrada e compartilham locks/cache/carteira. Na mesma organização/processo, PgJobManager só aceita uma busca ativa; SdrService só uma geração. Os demais recebem 429, sem fila automática. Isso evita certa concorrência, mas não comprova capacidade nem atendimento ao cliente. Duas organizações têm managers separados; múltiplos processos têm limites separados e não devem ser habilitados para escalar sem coordenação.

## Gargalos concretos e hipóteses a medir

| Camada | Evidência de código | Hipótese/medição |
|---|---|---|
| Frontend | Listas paginadas; useReadResource aborta respostas antigas | Medir render/interação com volume e limites, sem redesenhar tabela antecipadamente |
| Polling | prospecting-workspace.tsx usa 1500ms para status e resultados durante busca; session-provider.tsx usa 60s | Cem abas vendo uma busca poderiam produzir até cerca de 133 polls/s nos dois loops, mais sessão; é cálculo de cenário, não carga observada |
| Auth/BFF | Proxy getUser e backendHeaders getUser/getSession; JWT verificado de novo no backend | Medir latência/requisições Auth, cache JWKS e tempestade de refresh; não remover validação sem necessidade |
| API/SQL | Database.open cria conexão por operação; membership abre conexão, handlers podem abrir outras | Não equiparar contas a conexões. Medir concorrência efetiva, espera, picos e retorno ao baseline |
| Escritas | postgres.py:62 advisory lock por org | Cem escritores do mesmo tenant podem esperar pelo mesmo lock; medir lock_timeout/409 e integridade |
| Dashboard | repository.py:104 materializa os leads autorizados | Tempo/memória escalam com tamanho do tenant; não assumir apenas custo da página |
| CRM | crm/service.py:200/226 varre leads; pipeline:84 chama card:61, com consulta de último evento por card | Medir número de consultas e P95; otimizar somente o caminho que falhar |
| Jobs/IA | Executor e generation_lock locais, TTL 900s | Burst retorna 429; restart perde draft; testar custo e UX; fila só se envelope exigir |
| Índices | Índices org/status, org/follow-up e filhos por lead existem; datas text/funções e OFFSET podem custar | EXPLAIN ANALYZE apenas em cópia sintética; não adicionar índice sem plano de consulta |

A [documentação Supabase de conexões](https://supabase.com/docs/guides/database/connection-management), consultada em 23/10/2026, diferencia consumidores e limites conforme compute. Não foi inspecionado o plano/compute atual; não declarar um limite numérico universal. Registrar max_connections, limites do pooler, conexões de Auth/PostgREST/reservadas e orçamento disponível à aplicação. Testar SET LOCAL/claims/RLS se adotar pooler. Pool explícito ou aumento de compute só após dimensionamento.

## Protocolo de carga proposto

Responsável COM-13: Miqueias; Marwin instrumenta COM-12; Fernando/Laís validam jornada. Pode-se usar harness HTTP local com concorrência controlada a partir das dependências de teste existentes; não exigir nova tecnologia de produção. Escolha da ferramenta de carga é detalhe de QA, não mudança da arquitetura.

1. Preparar staging descartável com PostgreSQL nativo, schema equivalente e marcador inequívoco; nunca usar DSN de produção. Fixar commit, CPU/RAM/região, instâncias, limites SQL, rede e versão das dependências.
2. Criar 100 usuários sintéticos no tenant A e tenant B sentinela, com papéis owner/admin/member e usuário sem membership. Para carga, autenticação de teste gera JWTs válidos contra chaves/issuer exclusivamente de teste; não reutilizar tokens reais. Validar o fluxo Auth real separadamente em projeto de homologação autorizado.
3. Seeds: 1 mil, 10 mil e 50 mil leads **por tenant**, com dez interações e duas mensagens por lead, estágios/fusos variados e identificadores sentinela. São volumes de ensaio, não estimativa da base atual; confirmar volume contratado. Seeds e exclusão só no banco descartável.
4. Usar providers fake com latências determinísticas, contadores e falhas 400/401/403/429/5xx/timeout. Carga não chama Google/Groq reais. Smoke pago futuro requer autorização e orçamento separados, amostra pequena e dados fictícios.
5. Executar baseline 1 usuário; degraus 5, 20, 50 e 100 VUs autenticados, 5min aquecimento e 15min estáveis por degrau no volume principal de 10 mil. Ensaios 1 mil/50 mil podem concentrar baseline e degrau contratado. Think time 3–8s, seed aleatória fixa, registrar RPS alcançado.
6. Mix inicial: 30% lista/detalhe leads; 20% dashboard; 15% pipeline; 10% follow-ups; 10% mutações CRM; 5% export permitido; 5% ações de busca; 5% SDR. Polls de busca e /api/session são adicionais e registrados à parte; não escondê-los no RPS de ações. Validar ou ajustar mix com cliente antes do aceite.
7. Rodar soak de 2h no pico acordado e burst de 5min em 100 VUs. Comparar picos e cooldown. Fazer A/B simultâneos, disputa do mesmo lead/revision, escrita em leads distintos e tentativa de export/ID cruzado.
8. Ensaiar indisponibilidade de banco/Auth/provider, revogação durante job, cancel, restart/drain, draft não salvo e recuperação de snapshots. Não matar processos de produção nem testar recuperação sobre banco real.

## Critérios mensuráveis propostos

Metas de aceite iniciais a confirmar D1, não resultados obtidos:

| Dimensão | Meta de aprovação |
|---|---|
| Leituras/listas/detalhes/dashboard | P95 <=2s e P99 <=5s medidos via BFF no pico/volume contratados; separar custo de render do servidor |
| Mutações CRM | P95 <=2s; zero perda de atualização; conflito de revisão esperado retorna 409 e não é tratado como sucesso |
| Aceitar busca / polling / rejeitar limite | P95 <=1s no cenário fake, com estado coerente; cancel solicitado <=1s e efetivo até terminar a chamada em andamento |
| Geração IA fake | Medir fila/rejeição e overhead separado da latência fake; P95 overhead <=1s; tempo total <=latência fake +2s em carga acordada |
| Falhas inesperadas | <1% por endpoint e global; zero timeout de conexão por exaustão no envelope; 401/403 negativos, 409 e 429 intencionais reportados separadamente |
| Capacidade contratada | Demanda acordada satisfeita sem 429 inesperado. Se cliente exigir execuções caras concorrentes, rejeitá-las não conta como capacidade entregue |
| Integridade e isolamento | Zero registros/contextos de B em A, zero gravação alheia, duplicação indevida, órfão ou atualização perdida; auditoria coerente |
| Conexões | Pico <=80% do orçamento atribuído à aplicação, respeitando reservas externas; após 5min de cooldown, conexões <=baseline+2 |
| Recursos | CPU e memória estáveis; uso sustentado <=80% da capacidade alocada e sem crescimento contínuo no soak; registrar limites reais |
| Lock/query | Limites SQL definidos; zero espera sem teto; picos de lock e queries lentas documentados e aprovados |
| Browser | Em desktop e mobile de referência: nenhuma ação travada por >1s sem feedback, nenhum erro JS não tratado; P95 de abrir lista/detalhe <=3s na rede definida |
| Recuperação | Alvo inicial RPO<=24h/RTO<=4h, a aceitar comercialmente; restore isolado medido e conferido; alerta em <=5min |

Se o piloto contratado for 20 simultâneos e 100 cadastrados, aprovação em 20 não permite anunciar 100 simultâneos. Se houver exigência de 100 simultâneos, o degrau 100 com mix/volume acordados é obrigatório; falha resulta NO-GO para esse contrato até correção e nova medição. Não reduzir artificialmente volume/think time para obter um gráfico verde.

## Custos: medição e cenários, sem cotação inventada

Consumo Places mensal = usuários ativos × buscas/dia × dias × requests médios/busca; custo depende de SKU/campos/conta. Exemplo de planejamento: 100 × 2 × 22 × 3 = 13.200 requests/mês; com teto de dez por busca, 44.000. Não são previsão nem tarifa. Contar também falhas cobradas pelo provedor, conforme contrato.

Groq mensal = gerações × (tokens de entrada × tarifa de entrada + tokens de saída × tarifa de saída). Exemplo 100 × 4 × 22 = 8.800 gerações/mês. O limite atual de 1600 completion tokens produziria teto teórico de 14,08 milhões de tokens de saída nesse cenário, além das entradas; consumo real deve ser capturado, não inferido do teto. Não usar esse teto como margem garantida.

Adicionar hospedagem, banco, egress, backup, monitoramento e suporte; separar custo fixo, compartilhado e variável por tenant. Modelo/campo/região e descontos alteram tarifas: obter cotação oficial da conta ao executar COM-04/06. Não foram feitas chamadas pagas ou consultados gastos reais. Nenhum plano comercial de R$79/R$149/R$299 foi validado para cem usuários.

## Testes existentes e lacunas

Auth: test_phase31_security/test_auth_tls/test_access_diagnostics; frontend auth.test.mjs. CRM: test_crm_api/test_phase32_writes/test_phase32_team. Prospecção: test_prospecting_api/test_prospecting_batch e tests/test_google_places. IA: test_sdr_api/tests/test_sales_groq. Banco: test_phase31_postgres/test_auth_schema_acl/test_stamp_claims_migration; testes nativos de owner/MVCC existentes. Ver nomes e cobertura no roadmap anterior.

Revisão atual aprovou 14 testes Python selecionados e 16 Node; tsc/lint concluídos. Sete casos com tmp_path ficaram sem validação por permissão do TEMP; registrar limitação de ambiente e usar executor isolado autorizado no futuro. Não confundir suites com mocks com integração real. Não foi calculada cobertura de linhas, executado build/carga/E2E ou provado restore.

Artefato futuro obrigatório de COM-13: commit e parâmetros, duração/seed, VUs/RPS, latência por endpoint, 429/409 separados de erros, CPU/RAM/conexões/locks/queries, custo estimado por tenant, contagens/integridade antes/depois, incidentes e conclusão por envelope. Repetir após mudança material de SQL, quotas, Auth ou topologia.
