# Bloqueadores comerciais revalidados

Data: 23/10/2026. Recomendação atual: **NO-GO**. Código presente não equivale a autorização de operação com dados reais.

## P0: fechar antes de receber cliente

| Novo ID | Origem da auditoria anterior | Evidência atual | Natureza e saída |
|---|---|---|---|
| COM-01 | SAAS-01/12 | local-request.ts: isLocalRequest; proxies; runtime.py: TrustedHost | Restrição técnica comprovada para domínio público. Definir domínio/TLS/upstream restrito, sessão e origens; testar integração |
| COM-02 | SAAS-02 | claims-fix.md:5, migration 202610220001 e writers existentes | Pendência histórica de implantação; não reprovada por teste real novo. Catálogo sanitizado, homologação isolada e plano de aplicação futura autorizado |
| COM-03 | SAAS-03 | Database.open/Connection, RLS e testes phase31/32 | Gap de garantia crítico. Provar A/B SQL e API, membership, papéis, export, jobs e IA; corrigir apenas eventual falha demonstrada em fase futura |
| COM-04 | SAAS-04 | searches.py:checkpoint/get; jobs.py:export/_purge; máscara Places | Uso/retenção/exportação não adequados de forma demonstrável ao contrato. Decisão externa e requisitos técnicos aprovados antes de prometer a fonte comercial |
| COM-05 | SAAS-05 | main.py:create_app, config.py e LOUNG_AUTH_MODE local | Risco condicional de configuração, não fallback automático encontrado. Perfil comercial deve falhar fechado com sqlite/auth local/credencial administrativa |

São **5 tarefas P0 e 10 tarefas P1 para o piloto**, detalhadas no documento 03; mais 3 P2 fora do esforço-base. COM-04 fecha decisão de uso, não dispensa as adequações de retenção/atribuição/portabilidade de COM-09 e UI de COM-11. Se o parecer exigir outra fonte/modelo, abrir novo escopo P0 e replanejar; a estimativa-base não cobre substituição do fornecedor.

## Viabilidade operacional: dez perguntas

| Capacidade solicitada | Parecer atual | Critério para mudar o parecer |
|---|---|---|
| Hospedar em produção | Bloqueado por contrato localhost e operação não homologada | COM-01/05/08/12/14/15 |
| Empresas diferentes | Desenho presente, garantia não fechada | COM-03 + onboarding COM-11 |
| Muitos usuários na mesma empresa | Membership compartilhada implementada, carga desconhecida | Aceite de carteira compartilhada e testes COM-13 |
| Impedir vazamento | Não há vazamento demonstrado; garantia insuficiente | Matriz A/B e catálogo real-equivalente COM-03 |
| Buscas simultâneas sem corrupção | Uma por org/processo; concorrentes rejeitados; réplicas não coordenadas | Limite explícito, teste de integridade; fila só se exigida |
| Custos/falhas externas | Budgets/timeouts/erros presentes, quota financeira ausente | COM-06 + testes de falha e teto |
| Guardar/proteger informações | RLS/transações presentes, retenção/direitos pendentes | COM-03/04/09 |
| Recuperar após falha | Restore não demonstrado | COM-08 e ensaio independente |
| Monitorar desempenho/erros | Logs/Server-Timing parciais | COM-12/13 e alerta exercitado |
| Atualizar com usuários ativos | Estado local torna restart disruptivo | COM-14/15; drain/manutenção explícitos ou fila posterior |

## O que é técnico e o que depende de validação externa

**Técnico confirmado:** Host público negado, snapshots sem purge persistente, só uma busca e geração por org/processo, conexões SQL por operação, lock de escrita por organização, varreduras de todos os leads em dashboard/follow-ups/métricas e consulta adicional por card do pipeline. Isso indica riscos mensuráveis; não prova latência ou corrupção sob carga.

**Histórico não revalidado ao vivo:** aplicação da correção de autoria e flag de escrita. O relatório local de migração registra committed/applied e 160 leads/17 interações, portanto não chamar tudo de dry-run. Documento mais recente de claims-fix registra GROQ_MODEL presente na inspeção anterior; não repetir o diagnóstico antigo de modelo ausente. A disponibilidade atual do modelo não foi testada.

**Contrato/privacidade:** validar finalidade/base legal, papéis controlador/operador, suboperadores/transferência, retenção, direitos, licença da fonte e exportação. Contato público não autoriza automaticamente qualquer prospecção. Revisão humana não isenta obrigações. Não se emite parecer de conformidade jurídica nem se afirma violação contratual consumada.

Fontes oficiais consultadas em 23/10/2026:

- [Políticas Places](https://developers.google.com/maps/documentation/places/web-service/policies): limitações de cache/armazenamento e atribuição; exceção para place IDs. Validar a aplicação aos campos e exports do produto com o contrato da conta.
- [Dados Groq](https://console.groq.com/docs/your-data): existem controles de retenção; configuração da conta não foi inspecionada. Não prometer zero retenção.
- [Política WhatsApp Business](https://whatsappbusiness.com/policy/): exige respeito às políticas de contato e preferências. O produto atual abre wa.me, não integra API de disparos; avaliar o canal usado pelo cliente sem presumir regras de templates/janelas da API como requisitos do link manual.
- [LGPD, texto oficial](https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2018/lei/l13709.htm) e [guia ANPD de segurança](https://www.gov.br/anpd/pt-br/centrais-de-conteudo/materiais-educativos-e-publicacoes/guia-orientativo-sobre-seguranca-da-informacao-para-agentes-de-tratamento-de-pequeno-porte): referências para finalidade, necessidade, proteção e governança; enquadramento e documentos exigem responsável externo competente.

## Escopo mínimo sem excesso de arquitetura

Manter Next/FastAPI/Supabase e regras existentes. Para um piloto, propor uma instância persistente da API, limites explícitos, onboarding controlado, cobrança conciliada manualmente e procedimentos de suporte auditados. Não exigir microserviços, broker novo, troca de banco ou billing completo sem necessidade demonstrada. Uma instância não implica capacidade comprovada ou disponibilidade sem interrupção.

Se o cliente exigir 100 buscas/gerações realmente simultâneas, várias réplicas sem interrupção ou carteira privada por vendedor, o piloto-base não atende: promover escopo correspondente e recalcular prazo antes de fechar a oferta. Não ocultar a fila ausente atrás de retries automáticos.
