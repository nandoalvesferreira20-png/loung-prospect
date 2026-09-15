# Google Places: meta de leads sem site

## Bairro opcional

Cidade e segmento continuam obrigatórios; Bairro (opcional) começa vazio.
`neighborhood=None` em search, iter_search e prospect preserva a consulta anterior.
Somente strip é aplicado ao bairro; acentos, hífens e espaços internos são mantidos.

Exemplos de textQuery:
- Sem bairro: `restaurante em São Bernardo do Campo`.
- Com bairro: `restaurante em Rudge Ramos, São Bernardo do Campo`.

```powershell
python main.py --fonte google_places --cidades "São Bernardo do Campo" --segmentos restaurante --bairro "Rudge Ramos" --sem-site --max 20
```

Bairro participa da consulta original, inclusive nas páginas seguintes. Não há
filtro textual de endereço, geocoding, consultas automáticas ou multi-bairro.
O Google pode retornar estabelecimentos próximos ou com endereço diferente do
texto informado. Bairro não é um dado confirmado do lead: não substitui Cidade,
não vira coluna no banco/Excel nem parte da chave de deduplicação. O filtro
Sem site próprio e deduplicação transacional continuam iguais, inclusive entre
uma busca geral e outra por bairro. Futuras consultas separadas poderão reutilizar
o mesmo parâmetro e builder; não existe loop multi-bairro nesta versão.

Na tela Prospecção (Google Places), “Buscar somente leads sem site no Google”
controla o mesmo modo da busca Playwright. Inicia ligado, com score mínimo 60.
Desmarcar mantém o fluxo normal, inclusive empresas com websiteUri.

```powershell
python main.py --fonte google_places --cidades Campinas --segmentos dentista --max 20 --sem-site --min-score 60 --output exports/places-sem-site.xlsx
```

A CLI Places usa o serviço existente: qualifica, insere na carteira SQLite e
exporta Excel. Usa a configuração de chave e .env já existentes. Aceita uma
cidade e um segmento, quantidade de 1 a 100. Sem --fonte, a CLI anterior continua
inalterada; sem --sem-site, Places mantém a busca normal.

O FieldMask já incluía places.websiteUri e permanece completo, sem wildcard.
Somente websiteUri alimenta LeadCandidate.site. Espaços e marcadores vazios são
normalizados com possui_site. Não são consultados outros campos, DOM, sites ou
fontes externas. No modo restrito, candidate_to_record registra evidência da
resposta solicitada pela API: ausência é SEM_SITE_NO_GOOGLE, nunca ausência
confirmada na internet. A conversão normal continua com a semântica anterior.

GooglePlacesProvider.search mantém retorno em lista e limite original.
iter_search reutiliza a mesma implementação de HTTP, parsing e paginação,
mas entrega candidatos incrementalmente. O serviço para de consumir quando
alcança a meta de inserções aceitas. Sem limite de candidatos, usa páginas de
20 e o orçamento já existente (10 requests por padrão), sem recomeçar buscas.
Tokens repetidos e falhas encerram com mensagem, preservando inserções e Excel
parcial. Uma página já recebida pode conter candidatos que não serão utilizados.

Deduplicação considera Place ID, Empresa/Endereço na busca e duplicatas na
carteira. Duplicatas, rejeições por site/score e falhas de persistência não contam
para a meta restrita. O modo normal preserva exportação de resultados mesmo
quando já presentes na carteira. Os contadores stats têm os mesmos nomes do
Playwright. qualified e as distribuições do resumo anterior continuam contando
avaliações; stats.qualificadas/inserted indicam a meta efetivamente aceita.

Excel restrito acrescenta as mesmas colunas Status Site, Possui Site, Score e
Prioridade do modo Playwright. Os campos atuais e prioridades V3 são preservados.
Não há alteração de pesos, histórico, ações comerciais ou status existentes.

Cancelamento é observado antes de requests e entre candidatos; requisição em
curso aguarda o timeout existente. A meta não é garantida: depende da paginação,
da quota e dos candidatos que passam no filtro. Testes não acessam API real.

A validação externa solicitada em etapa anterior permanece pendente da escolha
da fonte e não participa deste modo, que usa exclusivamente websiteUri.

## Sprint target-based: limites da fonte e encerramento

O código já tinha iteração incremental. O gargalo de aproximadamente 60 também
existe na fonte: a documentação oficial do Text Search (New) informa máximo de
60 resultados entre todas as páginas, sujeito a mudança:
https://developers.google.com/maps/documentation/places/web-service/text-search
Não há novas consultas, subdivisão geográfica ou tentativa de contornar isso.
Ampliar descoberta exigiria uma etapa futura explícita de planejamento de consultas,
deduplicação entre consultas e orçamento global. Não foi implementada nesta sprint.

`limits.py` centraliza 10 requests (preservado) e 200 candidatos analisados por
execução. O segundo é uma proteção independente, não uma promessa de cobertura.
`max_candidates_scanned` pode ser reduzido na chamada de prospect; max_requests
continua configurável no provider. Não há prefetch nem recomeço automático.
Uma request pode trazer mais candidatos que os necessários para finalizar a meta.

`stop_reason` mantém texto compatível; `stop_code` é enum estável:
target_reached, source_exhausted, safety_limit_reached, cancelled, provider_error.
Limite interno e esgotamento não entram na lista de erros. Tokens repetidos e
respostas inválidas são erros do provider. Falhas isoladas de persistência continuam
registradas e não completam a meta. `pages_fetched` conta páginas válidas; requests
inclui tentativas HTTP malsucedidas. `target`, `accepted`, `candidates_scanned` e
`rejected_with_website` são propriedades sobre contagens existentes, sem estado duplicado.
`rejected_score` e `rejected_unverified` detalham rejeições.

Logs resumem cada página; UI exibe Meta de leads e progresso inserted/requested.
Encerramento com fonte esgotada mantém progresso real, sem sugerir meta atingida.
O consumo pode chegar ao orçamento quando houver tokens; normalmente a fonte
encerra antes. Nenhuma quota foi consumida durante desenvolvimento/testes.

Os cenários sintéticos com 150+ candidatos testam a orquestração caso um provider
retorne mais páginas; não representam capacidade garantida da API atual.
O teste antigo de orçamento foi ajustado somente para exigir safety_limit_reached
sem erro, em vez da antiga mensagem que misturava limite e falha do provider.
