# Integração local com Loung Sales AI

## Diagnóstico

`backend/main.py:create_app` escolhe SQLite local ou PostgreSQL SaaS explicitamente.
O padrão atual é SQLite em `data/loung_prospect.db`, substituível por
`LOUNG_DATABASE_PATH`. O modo local usa proteção de loopback, TrustedHost e bloqueio
de Origin/headers de proxy, sem login. O modo SaaS tem validação JWT Supabase e
isolamento por organização; sua existência no código não comprova serviço ativo.
Esta integração só é registrada no modo SQLite e não depende de Supabase.

`leads` contém `id`, `empresa`, `segmento`, `cidade`, `site`, `observacoes`.
Tabelas auxiliares incluem `lead_interactions`, `outreach`, `lead_contact_preferences`
e `template_drafts`; nenhuma é exportada. Rotas existentes incluem GET `/v1/leads`,
GET `/v1/lead-niches`, GET `/v1/leads/{id}`, GET `/v1/leads/{id}/edit`, POST
`/v1/leads` e PATCH `/v1/leads/{id}`. A listagem existente não contém observações
e inclui dados extras, por isso foi criada uma projeção específica.

## Contrato

GET `/v1/integrations/sales-ai/leads`, com `Authorization: Bearer <token>`.
Configure `LOUNG_SALES_AI_TOKEN` com segredo aleatório exclusivo de pelo menos
32 caracteres ASCII sem espaços. Vazio desabilita a integração (503); token
ausente/incorreto retorna 401. Reinicie o backend para ativar ou rotacionar.
Não use chaves Groq, Supabase, JWT de usuário ou credenciais administrativas.
Não coloque o token em URL, frontend, repositório ou logs.

Parâmetros:

| Parâmetro | Regra |
| --- | --- |
| `nicho` | Igualdade exata de `segmento`, com espaços externos removidos; até 500 caracteres |
| `limit` | Tamanho da página, padrão 50, mínimo 1, máximo 100 |
| `after_id` | ID exclusivo de início; padrão 0; inteiro positivo ou zero de 64 bits |
| `lead_id` | Seleção opcional: repita o parâmetro para até 100 IDs positivos de 64 bits |

Filtros são combinados por AND. Sem `lead_id`, todos os leads que correspondem
ao nicho são elegíveis. Para exportação controlada, informe os IDs revisados.
Ordenação crescente pelo ID original, sem renumeração. Continue com
`after_id=next_after_id`, preservando os filtros, até o cursor ser `null`.
Página sem resultados retorna `items: []`. Parâmetros inválidos retornam 422.
Colunas opcionais ausentes ou valores SQL NULL retornam `null`; strings vazias
são preservadas. Base indisponível/incompatível retorna 503.

```json
{
  "items": [
    {
      "lead_id": 7,
      "nome": "Clínica Árvore",
      "nicho": "Saúde",
      "cidade": "São Paulo",
      "site": "https://example.org",
      "observacoes": "Revisão humana"
    }
  ],
  "next_after_id": null
}
```

Consultas usam `ReadRepository.connect`, SQLite `mode=ro`, `query_only=ON`,
transação de leitura e parâmetros SQL. O endpoint não inicializa schema,
não altera leads e não executa provedores, Groq ou WhatsApp. O ciclo de startup
local existente continua com seu comportamento habitual de inicialização.
Páginas de requisições diferentes não são um snapshot único: revisões e novas
inserções podem ocorrer. No destino, use `lead_id` para deduplicar/upsert; ao
combinar várias instalações independentes, acrescente uma identidade de origem
no destino, pois IDs SQLite são únicos apenas dentro da própria base.

## PowerShell na raiz do projeto

Use o ambiente virtual existente do backend. Se necessário, instale dependências
com `backend/.venv/Scripts/python.exe -m pip install -r backend/requirements-dev.txt`.
As configurações abaixo não mudam o caminho nem o tipo de banco existente.
O backend não carrega automaticamente este token de um arquivo `.env`.

```powershell
# Gere uma vez e guarde em um gerenciador de segredos; não imprima o token.
$env:LOUNG_SALES_AI_TOKEN = (& backend/.venv/Scripts/python.exe -c "import secrets; print(secrets.token_urlsafe(48))")
backend/.venv/Scripts/python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Em outro terminal, carregue o MESMO token do gerenciador de segredos:

```powershell
$secureToken = Read-Host 'Token Sales AI' -AsSecureString
$env:LOUNG_SALES_AI_TOKEN = [System.Net.NetworkCredential]::new('', $secureToken).Password
$headers = @{ Authorization = "Bearer $env:LOUNG_SALES_AI_TOKEN" }
$query = 'nicho=' + [uri]::EscapeDataString('Saúde') + '&limit=50&lead_id=7&lead_id=42'
$baseUrl = 'http://127.0.0.1:8000/v1/integrations/sales-ai/leads'
$cursor = 0
$items = @()
do {
    $page = Invoke-RestMethod -Method Get -Uri ($baseUrl + '?' + $query + '&after_id=' + $cursor) -Headers $headers
    $items += @($page.items)
    $cursor = $page.next_after_id
} while ($null -ne $cursor)
$json = ConvertTo-Json -InputObject @{items=$items} -Depth 6
$file = Join-Path $PWD ('sales-ai-export-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '.json')
[System.IO.File]::WriteAllText($file, $json, [System.Text.UTF8Encoding]::new($false))
```

Revise o arquivo antes da transferência, especialmente `observacoes`, que é
texto livre e pode conter informações sensíveis. Mantenha-o fora do controle
de versão. Este comando apenas lê leads e cria um arquivo local.

## Conectar ao n8n Cloud sem publicar o backend

O HTTP Request do n8n Cloud não alcança o loopback da sua máquina. Preserve
`--host 127.0.0.1`; não abra portas, não remova os bloqueios e não configure
túnel público para este backend.

Fluxo recomendado: exportação revisada local → POST HTTPS de saída → Webhook
autenticado no n8n Cloud → Split Out de `body.items` → processamento Sales AI.
Configure um Webhook com método POST e Header Auth, nome `X-Loung-Export-Token`,
usando um segundo segredo exclusivo no gerenciador de credenciais do n8n.
Use a URL de teste enquanto escuta eventos; após ativar/publicar o workflow,
use a URL de produção. Veja a [documentação oficial do Webhook](https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.webhook/).

Após revisar o JSON, execute manualmente (nenhum envio foi executado pelo projeto):

```powershell
$webhook = Read-Host 'URL HTTPS do webhook n8n'
if (([uri]$webhook).Scheme -ne 'https') { throw 'Exige HTTPS' }
$webhookSecret = Read-Host 'Segredo do webhook' -AsSecureString
$outHeaders = @{ 'X-Loung-Export-Token' = [System.Net.NetworkCredential]::new('', $webhookSecret).Password }
Invoke-RestMethod -Method Post -Uri $webhook -Headers $outHeaders -ContentType 'application/json; charset=utf-8' -Body ([System.IO.File]::ReadAllBytes($file)) -MaximumRedirection 0
```

O token de leitura local não é enviado ao n8n. No destino, valide o contrato e
deduplique por origem/`lead_id` antes de reprocessar. Não configure nós de envio
WhatsApp neste fluxo. Para Supabase novo, crie uma credencial restrita apenas à
tabela de destino necessária; nenhuma chave administrativa do Prospect é exigida.
Para automatização futura, um processo local agendado pode fazer essa mesma
transferência de saída, com seleção explícita e segredos protegidos.

## Testes

Não usam a base real; fixtures criam SQLite temporário e verificam autenticação,
serialização, seleção, nicho, cursor, limites, bloqueios de rede e hash do banco.

```powershell
# Para a suíte PostgreSQL, em terminal separado (somente banco sintético em memória):
node web/scripts/phase31-postgres.mjs
# Backend, incluindo os testes novos:
backend/.venv/Scripts/python.exe backend/scripts/run_offline_tests.py backend/tests -q -p no:cacheprovider --basetemp=temp/sales-ai-tests
# Suíte principal: requer também as dependências de requirements-dev.txt da raiz.
backend/.venv/Scripts/python.exe backend/scripts/run_offline_tests.py tests -q -p no:cacheprovider --basetemp=temp/sales-ai-core-tests
```

Validação realizada em 10/11/2026:

- Suíte principal: **814 aprovados**. Neste workspace, as dependências estão
  distribuídas entre `.venv` e `backend/.venv`; a execução reutilizou ambos sem
  instalar pacotes, acrescentando `.venv/Lib/site-packages` ao `sys.path` do Python
  do backend.
- Regressão local (`test_sales_ai`, `test_api`, `test_local_mode`, `test_crm_api`,
  `test_sdr_api`, `test_prospecting_api`): **120 aprovados**, incluindo os **8 novos**.
- Suíte completa do backend com PGlite sintético: **198 aprovados, 21 ignorados,
  1 falha e 34 erros**. Problemas nos cenários PostgreSQL de equipe/migrações:
  `organization_members.organization_id` ausente, função `team_roster` duplicada
  e falhas de protocolo/conexão. A suíte completa não está verde. Os cenários
  de migração compartilham/mutam o servidor sintético; requerem investigação
  separada, sem mudanças no banco do operador.
- Aviso de depreciação existente: TestClient Starlette com httpx.
- `git diff --check` sem erros. Nenhum commit, push, deploy ou envio ao n8n/WhatsApp.

Para repetir apenas a regressão local:

```powershell
backend/.venv/Scripts/python.exe backend/scripts/run_offline_tests.py backend/tests/test_sales_ai.py backend/tests/test_api.py backend/tests/test_local_mode.py backend/tests/test_crm_api.py backend/tests/test_sdr_api.py backend/tests/test_prospecting_api.py -q -p no:cacheprovider --basetemp=temp/sales-ai-local-regression
```
