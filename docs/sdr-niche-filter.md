# Filtro por nicho no SDR Web local

## Arquivos alterados

- `backend/repository.py`: leitura dos nichos e filtro SQL compartilhado.
- `backend/main.py`: rotas locais de leitura.
- `web/src/lib/api/contracts.ts`: parâmetro opcional tipado.
- `web/src/lib/api/proxy.ts`: repasse seguro do parâmetro e da rota de nichos.
- `web/src/app/api/lead-niches/route.ts`: BFF das opções.
- `web/src/app/sdr/page.tsx`: seletores, estado, contagem e proteção da seleção.
- `backend/tests/test_sdr_niches.py`: regressões SQLite sintéticas.
- `web/scripts/local.test.mjs`: regressões de cliente e BFF.
- `web/scripts/check_sdr_niches.py`: novo teste de navegador.
- `web/scripts/check_sdr.py`: ajuste do teste existente para troca de filtros.
- `docs/sdr-niche-filter.md`: documentação e validação manual.

## Comportamento

O seletor **Filtrar por nicho** usa exclusivamente valores distintos de
`leads.segmento` no SQLite configurado pelo backend. A consulta de opções
`GET /v1/lead-niches` é somente leitura e ignora NULL, strings vazias e
valores compostos apenas por espaços em branco. Os valores são preservados
literalmente, sem reclassificação, alteração de capitalização ou gravação.
Schemas legados sem `segmento` retornam uma lista de opções vazia.

O SDR continua usando `GET /v1/leads`, agora com o parâmetro opcional `niche`.
Ausente ou vazio mantém o contrato anterior. Valores preenchidos são comparados
exatamente por parâmetro SQL, combinados com `q` e `stage` antes do COUNT,
LIMIT e OFFSET. Nichos inexistentes retornam total zero e lista vazia.

A interface carrega as opções ao entrar e ao usar **Atualizar leads**, sem
reconsultá-las em cada busca, página ou geração. Alterar busca, nicho ou status
volta à primeira página e limpa o lead selecionado. A proteção existente de
mensagens não salvas permite salvar, descartar ou cancelar essa troca.
Geração, edição, revisão e salvamento preservam filtros e página.

Nenhum prompt, fluxo Groq, regra de WhatsApp, autenticação ou configuração de
Supabase foi alterado. Não há migrações nem alterações nos leads existentes.

## Validação manual

1. Inicie o backend e o frontend locais normalmente e abra `/sdr`.
2. Confira **Todos os nichos** como padrão e compare a contagem com a carteira.
3. Selecione um nicho existente. Confira os segmentos dos resultados e a contagem.
4. Combine com nome e status, inclusive uma combinação sem resultados.
5. Em um nicho com mais de oito leads, navegue entre páginas. Troque o nicho e
   confirme o retorno à primeira página e a limpeza da seleção.
6. Selecione um lead, gere e edite uma mensagem. Confira que o nicho, o status,
   a busca e a página permanecem. Salve ou aprove a versão, se desejado.
7. Com texto não salvo, tente trocar o nicho. Cancele e confira a preservação
   do texto e do filtro; depois teste salvar ou descartar e continuar.
8. Abra o WhatsApp manualmente e confira destinatário e texto antes de enviar.

## Testes automatizados

Resultado da validação: 979 testes Python aprovados e 13 ignorados por
exigirem PostgreSQL; cinco suítes exclusivas de PostgreSQL foram excluídas
da execução local após a tentativa completa aguardar o serviço legado.
A suíte direcionada de SQLite/SDR/Groq/modo local passou com 92 testes.
Os 23 testes JavaScript, TypeScript (`typecheck`), lint e build passaram.
Ambos os scripts de navegador passaram, incluindo quatro resoluções.
Groq foi simulado e WhatsApp interceptado nos testes de fluxo; não houve
chamada comercial real nem envio de mensagem. Há um aviso preexistente de
depreciação do `fastapi.testclient`/`httpx`.

- `backend/tests/test_sdr_niches.py`: SQLite sintético; opções distintas,
  valores ausentes/vazios, schema legado, igualdade literal, tentativa de SQL
  injection, busca, status, contagem, paginação e integridade do arquivo.
- `web/scripts/local.test.mjs`: codificação e repasse dos filtros pelo cliente
  e BFF local; inclui as regressões existentes de modo local e WhatsApp.
- `web/scripts/check_sdr_niches.py`: navegador contra `sdr_fixture_server`,
  Groq simulado, persistência dos filtros, ausência de consultas repetidas,
  confirmação de rascunho e WhatsApp interceptado; nunca envia mensagens.
- `web/scripts/check_sdr.py`: regressão completa existente de SDR e quatro
  resoluções, ajustada para selecionar novamente após mudar filtros.

Para os testes de navegador, execute o backend sintético em 8100 e o frontend
em 3100 com `LOUNG_API_URL=http://127.0.0.1:8100`. Os scripts verificam a
assinatura da fixture antes de interagir. Use Python com Playwright e Edge.
