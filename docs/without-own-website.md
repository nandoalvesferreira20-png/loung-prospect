# Sem site próprio — Digital Presence V4

O filtro antigo excluía qualquer Site preenchido antes da classificação digital.
Agora o filtro usa exclusivamente classify_digital_presence e DigitalPresenceType:
NOT_FOUND, SOCIAL_MEDIA e THIRD_PARTY_PLATFORM são elegíveis; OWN_WEBSITE,
UNVERIFIED e ERROR ficam fora. O score mínimo e todos os pesos/prioridades Rules V3
permanecem iguais. V4 é a evolução do filtro/classificador, não uma nova Rules Version.

`--sem-site` e `only_without_website` continuam compatíveis, agora com esse significado.
Na UI, a opção se chama “Sem site próprio”. Desligada, mantém a busca normal.
A mesma política central é aplicada ao Playwright e ao Places; não há mudança de
paginação, fonte, limite ou verificação de DOM. Não houve execução de navegador.

A presença se refere apenas à URL observada: Instagram, Facebook/fb.com, TikTok,
LinkedIn, YouTube/youtu.be, X/twitter.com e Threads são redes sociais.
Linktree, Beacons, bio.site, Google Sites e Carrd são plataformas externas, assim
como os hosts compartilhados Wix/WordPress/Canva e providers já suportados.
Acrescentados domínios explícitos iFood, Rappi, Tripadvisor (.com/.com.br) e
Restaurant Guru (.com/.com.br); não há wildcard de TLD especulativo.

Canva reutiliza o domínio canva.site já cadastrado: restaurante.my.canva.site
corresponde por sufixo delimitado por ponto. canva.site.example.net não corresponde.
Não inferimos nada a partir da palavra Canva no path ou de outros links canva.com.
Matching é sempre pelo hostname, nunca por substring na URL completa.
Domínios próprios continuam OWN_WEBSITE mesmo se construídos com Wix/WordPress/etc.;
não há detecção de tecnologia ou confirmação de titularidade.

NOT_FOUND requer observação explícita da fonte. URLs inválidas e campos não
verificados não se tornam ausência. Fonte que apresenta apenas rede social ou
plataforma externa NÃO comprova que a empresa não tenha outro site na internet.

Excel mantém colunas e URL original. No modo filtrado, Possui Site=False significa
site próprio não observado; Status Site distingue “Sem site próprio — Instagram”,
“Sem site próprio — Canva Sites” e SEM_SITE_NO_GOOGLE. Não rotulamos redes sociais
como ausência total de presença digital. Contadores com_site/sem_site passam a
significar próprio observado/elegível sem próprio; demais contagens seguem iguais.
Nenhuma migration ou alteração de dados existentes na carteira.

Testes cobrem hosts suportados, subdomínios enganosos, observações conservadoras,
score mínimo e 60 candidatos sintéticos com 17 elegíveis. Não há chamadas externas.
