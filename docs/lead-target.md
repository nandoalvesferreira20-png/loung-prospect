# Busca por meta de leads sem site no Google

Na tela **Busca legada** (Playwright), a opção “Buscar somente leads sem site no
Google” inicia marcada. Informe quantidade e score mínimo (padrão 60). A quantidade
é uma meta **total** compartilhada entre as cidades e segmentos, não o número de
empresas abertas. Desmarcar recupera o comportamento anterior, inclusive a opção
independente de qualificação. Google Places e sua interface permanecem inalterados.

Na CLI:

```powershell
python main.py --cidades Campinas --segmentos dentista --max 30 --sem-site --min-score 60 --output exports/sem-site.xlsx
```

A CLI sem `--sem-site` continua no coletor legado, com suporte anterior a CSV.
O novo modo usa `core.scraper.run_scraper` e exporta Excel. Pela API Python, acrescentar
`only_without_website=True, min_score=60`; o default False preserva chamadas antigas.

## Seleção

1. Descobrir links incrementalmente em uma página de busca separada.
2. Eliminar links já vistos e abrir a empresa na página de inspeção.
3. Reutilizar `extract_company_data(..., verify_website=True)`.
4. Deduplicar por Empresa + Endereço, mantendo a primeira ocorrência, como antes.
5. Excluir valores de Site presentes, inclusive redes sociais e links de fallback.
6. Aceitar como candidato sem site apenas a observação explícita `not_found`.
7. Qualificar pelo serviço existente e aceitar status qualified com score >= mínimo.
8. Encerrar ao atingir a meta, cancelar ou esgotar as condições de descoberta.

`possui_site` centraliza a presença do valor. None, branco e marcadores como N/A
retornam False, mas isso **não prova ausência**. A inspeção incompleta, erro ou
metadado ausente permanece inconclusiva e é descartada no modo restrito. Não se
cria evidência `not_found` a partir de campo vazio. `SEM_SITE_CONFIRMADO` é reservado
para validação futura e nunca produzido nesta versão.

Pesos, Rules Version e prioridades V3 permanecem intactos. A prioridade exportada
usa BAIXA/MEDIA/BOA/ALTA com os limites atuais 30/50/70; não há regra paralela de
80/60. Campos comerciais originais não são modificados. Os resultados aceitos são
qualificados uma só vez e permanecem associados no summary.

## Exportação e contadores

Preserva Empresa (nome já existente), Segmento, Cidade, Telefone, Endereço, Site e
demais colunas. Acrescenta qualificação e Possui Site, Status Site, Score, Prioridade
somente no novo modo. `_website_verification` não vai ao Excel. Arquivo vazio não é
criado; cancelamento mantém exportação parcial dos leads já aceitos.

O summary mantém as chaves antigas e acrescenta meta, min_score, motivo_parada e
stats. Analisadas conta tentativas de processamento, sem duplicatas de URL que não
foram abertas. Sem_site conta candidatos com ausência verificada antes do corte de
score. Duplicadas inclui URLs repetidas entre buscas e Empresa/Endereço repetidos.
Descartadas inclui essas duplicatas, campos inconclusivos, score/status rejeitado e
falhas de processamento; por isso não é sempre analisadas menos qualificadas.

## Limites

A descoberta encerra após três rodadas sem links novos ou 12 rolagens (limite de
segurança do fluxo existente). Isso não prova que não existam outras empresas na
cidade: o resumo informa o limite da busca atual. Seletores/DOM continuam sujeitos
a mudanças do Maps. Cancelamento é checado entre operações; uma navegação em curso
pode levar até seu timeout. Nenhuma pesquisa externa adicional confirma ausência.
Testes usam páginas simuladas, dados sintéticos e arquivos temporários, sem Maps real.
