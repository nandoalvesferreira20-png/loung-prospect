# Google Places Provider V1

Uso explícito, sem integração com os demais fluxos:

```python
from core.providers import GooglePlacesProvider

provider = GooglePlacesProvider(timeout=30, max_requests=10)
leads = provider.search(city="Taubaté", segment="dentista", max_results=50)
print(provider.request_count)
```

Defina `GOOGLE_PLACES_API_KEY` no ambiente. Não há carregamento de `.env`.
Não inclua a chave em código, logs ou arquivos versionados.

Endpoint: `POST https://places.googleapis.com/v1/places:searchText`.

FieldMask:
`places.id,places.displayName,places.formattedAddress,places.nationalPhoneNumber,places.websiteUri,places.rating,places.userRatingCount,places.googleMapsUri,places.location,nextPageToken`

Contrato conferido na documentação oficial em 2026-09-11:
- https://developers.google.com/maps/documentation/places/web-service/text-search
- https://developers.google.com/maps/documentation/places/web-service/reference/rest/v1/places/searchText

`pageSize` é limitado a 20. `pageToken` recebe o `nextPageToken` anterior;
query e idioma permanecem iguais. A busca para ao atingir o limite solicitado
ou acabar a paginação. Tokens repetidos e esgotamento do orçamento geram erro.
O teto documentado atualmente pelo Google é 60 resultados por consulta; pedir
mais não garante recebê-los. Os campos solicitados incluem campos da categoria
Text Search Enterprise; não há estimativa monetária no código.

Somente HTTP da biblioteca padrão (`http.client`). Sem redirects, retry,
Place Details, paralelismo ou enriquecimento. `request_count` conta tentativas,
inclusive com falha, e reinicia em cada search. Uma instância não é compartilhável
entre buscas concorrentes. A chave só é enviada no header ao endpoint fixo.

Erros de infraestrutura não viram lista vazia. Em falha de página posterior,
a busca levanta exceção e não retorna resultados parciais. O transporte é
injetável nos testes: `(payload, headers, timeout) -> (status, bytes_json)`.
Não há deduplicação nem persistência nesta camada. A cidade/segmento retornados
são os pesquisados; telefone não confirma WhatsApp.
