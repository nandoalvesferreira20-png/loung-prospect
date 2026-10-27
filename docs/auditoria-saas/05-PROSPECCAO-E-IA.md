# Prospecção e SDR com IA

Data: 23/10/2026. Nenhuma chamada de geração, consulta paga ou mensagem foi enviada nesta auditoria.

## Origem e mecanismo de prospecção

Fluxo web: `backend/prospecting/jobs.py:configured_provider` → `core/providers/google_places.py:GooglePlacesProvider`. Usa HTTPS fixo `places.googleapis.com/v1/places:searchText`, Places API New, API key no header server e field mask explícita. Paginação nextPageToken, até 20 por página, rejeição de token repetido, sem retry/redirect automático.

Não foi identificado Playwright na busca web. Automação/scraping Playwright permanece no legado `core/scraper.py`, usado pelo desktop; permissões de API não autorizam automaticamente scraping. `core/prospecting/service.py` e `core/qualification` qualificam resultados; ausência de site na fonte não é prova de ausência na internet.

SearchRequest aceita 1–100 resultados; orçamento de 10 chamadas e até 200 candidatos; job 120s, chamada 15s, cancelamento cooperativo. Uma pesquisa ativa por organização/processo, até 20 recentes, cache por 900s. Cancelamento não interrompe HTTP em andamento nem recupera quota consumida.

Staging SQLite `:memory:` deduplica resultados do job. Persistência deduplica por provider/place, Maps URL, empresa/endereço ou empresa/telefone, com comparação exata; RLS delimita organização, lock serializa escrita por org e índice único protege provider/place. Não há deduplicação fuzzy nem promessa de cobertura total.

Importação selecionada exige job terminado e IDs válidos, preserva existentes e usa transação. CSV/XLSX exportam resultados da busca e neutralizam fórmulas perigosas. `core/importers/excel_leads.py` é legado; não foi identificado upload Excel genérico no BFF atual.

## Retenção e adequação comercial

`backend/persistence/searches.py:checkpoint` guarda query, rows e estado em JSONB no início e no fim. Não há purge/TTL persistente identificado; `_purge` limpa somente memória. `get` pode reler snapshots depois da expiração do cache; job reconstruído não recupera finished, portanto expiresInSeconds não comprova exclusão. Leads importados permanecem no CRM, com campos de origem como nome, endereço, telefone, site e avaliações. Exports geram cópias fora do serviço.

As [políticas oficiais Places](https://developers.google.com/maps/documentation/places/web-service/policies), consultadas em 23/10/2026, restringem armazenamento/cache fora das exceções e exigem atribuição apropriada; Place IDs têm exceção específica. API paga não comprova licença geral de retenção em CRM/redistribuição. A UI contém menções textuais Google/Maps, mas não foi identificado mecanismo completo de atribuição compatível demonstrado. Validar contrato da conta, uso por campo, dados derivados, região, exports e prazos com responsável jurídico/comercial. Não se afirma infração conclusiva.

**Gate P0 SAAS-04:** decisão documentada sobre origem/licença, campos permitidos, retenção, exportação e atribuição; depois propor adequações. Nenhuma integração foi substituída.

## Groq: credenciais e dados enviados

`core/sales/config.py` lê key/model/timeout no servidor; provider pode carregar .env raiz sem sobrescrever variáveis existentes. `GroqSalesProvider.generate` usa SDK autenticado em `api.groq.com`, max_retries=0, JSON, sem tools e até 1600 completion tokens. Modelo vazio falha; não há fallback automático. Backend limita timeout a 30s. Resposta passa por validação do domínio; falha é sanitizada sem corpo/chave do SDK.

`WebAgent.evidence` usa allowlist de `core/sales/prompts.py:FIELDS`: empresa, segmento, cidade, site, avaliação, quantidade de avaliações, qualification_score e opportunity; strings de evidência até 1500 caracteres. Acrescenta tipo de contato, serviço e instrução humana. Notes/telefone/e-mail não são campos diretos desse prompt; campos livres ainda podem conter dados pessoais ou instruções hostis. Minimização não é anonimização. Histórico local auxilia o agente a evitar repetição; não foi identificado histórico global cross-tenant enviado ao provider.

`SYSTEM_PROMPT` fixa Fernando/Loung Tech e oferta de serviços. Clientes externos precisam de identidade e oferta aprovadas por organização (SAAS-08). Personalização deve ser tenant-scoped, sem permitir que configuração de cliente altere políticas globais ou contexto de outro cliente.

`SdrService` limita uma geração concorrente por org/processo e até 100 requestIds por janela de 900s; fingerprint conflitante é rejeitado. Drafts/requests ficam na instância da org. Idempotência não é durável entre réplicas/restarts. Não há ledger de tokens/custo/competência que atribua despesa financeira por cliente. Chamadas repetidas continuam consumindo quota global.

## Revisão humana e WhatsApp

UI permite gerar, editar, copiar, salvar texto revisado e aprovar explicitamente; aprovação encerra edição daquela versão e preserva histórico. `web/src/lib/sdr-whatsapp.ts:whatsappLink` valida formato telefônico e codifica o texto. O link wa.me recebe telefone/mensagem, abre nova aba e o usuário envia no WhatsApp. Não há disparo automático.

Abrir WhatsApp não exige status APROVADA: revisão é orientada na interface e envio é manual. Se aprovação formal persistida for requisito contratual, precisa decisão e teste futuros; não declarar enforcement inexistente. Não inferir contato realizado pelo clique.

Do_not_contact/recusa é verificado antes/depois da geração e ao salvar. Telefone público não comprova autorização jurídica irrestrita de contato; isso depende da finalidade e avaliação externa. Manter revisão humana e não implementar envio automático.

## Privacidade e terceiros

Google recebe consulta/credencial; Groq recebe contexto permitido e instrução; WhatsApp/Meta recebe telefone/texto ao abrir link. A [documentação de dados Groq](https://console.groq.com/docs/your-data), consultada em 23/10/2026, descreve controles de retenção na conta. A configuração efetiva, contrato, região e retenção do workspace não foram verificados. Não prometer zero retenção.

Requisitos a validar: inventário de tratamentos e finalidades, base legal por finalidade, controlador/operador/suboperadores, contrato/transferência internacional, aviso de privacidade, prazos, acesso, direitos dos titulares e encerramento. Logs devem minimizar PII; audit_events também pode conservar mensagens/descrições. Export/exclusão precisam abranger filhos e retenção de backups conforme política.

Suspensão atual é cancelamento de busca individual e flag global de escrita. Não foi identificada pausa comercial por org/provedor ou entitlement mensal. Limites por chamada não controlam custo total; ver SAAS-07/10.
