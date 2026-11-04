# Loung Prospect

Ferramenta local de prospecção comercial: **Next.js + FastAPI + SQLite**, sem login. Cada máquina tem uma base independente. Google Places pesquisa estabelecimentos; Groq gera abordagens SDR; Leads, CRM, Pipeline, histórico e follow-ups ficam no SQLite. O WhatsApp é aberto com o texto revisado e o envio é manual.

Não há instalador nem deploy público nesta versão. Frontend e backend devem executar somente em `127.0.0.1`. Supabase, PostgreSQL, organização e JWT não são necessários no modo local.

## Requisitos

- Windows com PowerShell ou macOS com Terminal.
- Git, Python 3.11+ e Node.js `^22.19.0 || >=24.6.0`, conforme `web/package.json`.
- Chaves Google Places e Groq para usar essas integrações. CRM e SQLite funcionam sem elas; buscas e geração exigem internet.

## Clonar e instalar

Substitua `URL_DO_REPOSITORIO` pela URL do seu repositório:

```text
git clone URL_DO_REPOSITORIO loung-prospect
cd loung-prospect
```

Windows:

```powershell
py -3 -m venv backend/.venv
backend/.venv/Scripts/python.exe -m pip install -r backend/requirements.txt
if (!(Test-Path .env)) { Copy-Item .env.example .env }
if (!(Test-Path web/.env.local)) { Copy-Item web/.env.example web/.env.local }
cd web
npm.cmd ci
cd ..
```

macOS:

```bash
python3 -m venv backend/.venv
backend/.venv/bin/python -m pip install -r backend/requirements.txt
cp -n .env.example .env
cp -n web/.env.example web/.env.local
cd web
npm ci
cd ..
```

Arquivos de ambiente existentes são preservados. No `.env` do backend, configure:

```dotenv
LOUNG_AUTH_MODE=local
LOUNG_STORAGE_BACKEND=sqlite
LOUNG_DATABASE_PATH=data/loung_prospect.db
LOUNG_ENABLE_WRITES=1
GOOGLE_PLACES_API_KEY=
GROQ_API_KEY=
GROQ_MODEL=openai/gpt-oss-20b
GROQ_TIMEOUT=30
```

Preencha as chaves sem versioná-las. No `web/.env.local`, use `LOUNG_AUTH_MODE=local` e `LOUNG_API_URL=http://127.0.0.1:8000`. Chaves Google/Groq ficam exclusivamente no backend; não use `NEXT_PUBLIC_` para elas.

## Executar

Terminal 1, na raiz, Windows:

```powershell
backend/.venv/Scripts/python.exe -m backend.scripts.run_api --env-file .env
```

No macOS:

```bash
backend/.venv/bin/python -m backend.scripts.run_api --env-file .env
```

Terminal 2:

```text
cd web
npm run dev
```

No PowerShell, use `npm.cmd run dev` se `npm.ps1` estiver bloqueado. Abra **http://127.0.0.1:3000/**. O backend atende em **http://127.0.0.1:8000/health**. Para build local: `npm run build` e `npm start` em `web`; os scripts mantêm o bind loopback.

## Dados e uso

- **Prospecção:** pesquise no Google Places, selecione resultados e importe leads deduplicados; exporte CSV ou Excel.
- **Leads e Pipeline:** crie/edite fichas, registre atividades, altere etapas e agende follow-ups.
- **SDR:** escolha lead, serviço e orientação; gere com Groq, revise e salve no histórico. O botão WhatsApp apenas abre a conversa com o texto preenchido.
- **SQLite:** `data/loung_prospect.db` por padrão; caminhos relativos são resolvidos pela raiz. Base nova começa vazia. Base existente recebe backup antes da migração local aditiva. Nunca compartilhe esse arquivo em unidade de rede.
- **Backups e privacidade:** preserve `data/backups/`; bancos, WAL/SHM, ambientes, logs e exportações comerciais ficam fora do Git. Testes usam bases temporárias.

## Problemas comuns

| Sintoma | Verificação |
| --- | --- |
| API indisponível | Inicie o backend e confira `/health` e `LOUNG_API_URL`. |
| Login ou exigência de PostgreSQL | Confira `LOUNG_AUTH_MODE=local` nos dois processos e `LOUNG_STORAGE_BACKEND=sqlite`; reinicie após alterar configuração. |
| Valores do `.env` não são usados | Variáveis exportadas no terminal têm precedência. Use o relatório offline abaixo no mesmo terminal do backend. |
| Groq falha por TLS no Windows | Atualize as dependências e reinicie o backend; o cliente usa os certificados confiáveis nativos, mantendo validação TLS. Veja o diagnóstico Groq. |
| Google Places retorna erro | Confira chave, API habilitada, faturamento e quota. A interface distingue falhas de pesquisa de resultados vazios. |
| SQLite ocupado ou conflito 409 | Aguarde a escrita e atualize a ficha; use uma instância de backend por base. Não apague a base ou seus arquivos WAL/SHM para resolver bloqueios. |

Diagnóstico Groq sem chamada externa nem exposição de chaves, Windows:

```powershell
backend/.venv/Scripts/python.exe -m backend.scripts.check_groq_config --env-file .env
```

No macOS, use `backend/.venv/bin/python`. Consulte [guia local completo](docs/local/README.md), [diagnóstico Groq](docs/local/GROQ_DIAGNOSIS.md), [auditoria de arquitetura](docs/local/AUDIT.md) e [limpeza do repositório](docs/local/CLEANUP_REPORT.md).

## Arquitetura e desenvolvimento

`core/` contém regras compartilhadas; `backend/` oferece a API; `web/` contém Next.js/BFF. Instale `backend/requirements-dev.txt` para testes da API e `requirements-dev.txt` para testes dos serviços de negócio e da CLI. Em `web`: `npm test`, `npm run typecheck`, `npm run lint`, `npm run build`.

A implementação SaaS foi preservada em `backend/persistence/`, `supabase/` e nas rotas/componentes de autenticação. Ela **não é uma dependência de configuração do modo local**. A implementação histórica permanece versionada, sem ativação no modo local. Veja a [classificação arquivo a arquivo](docs/local/CLEANUP_INVENTORY.json) e o [procedimento de retorno ao SaaS](docs/local/README.md#retorno-ao-saas).


A aplicação é exclusivamente Web local. `main.py` mantém somente a CLI de prospecção sem interface gráfica. A GUI Python e o empacotamento PyInstaller foram removidos. Consulte o [mapa de dependências](docs/local/DESKTOP_REMOVAL_MAP.json), o [relatório da remoção](docs/local/DESKTOP_REMOVAL_REPORT.md) e a [documentação histórica](docs/desktop-history.md).

Para executar toda a suíte Python em um único ambiente, instale ambos os arquivos de desenvolvimento:

```text
python -m pip install -r requirements-dev.txt -r backend/requirements-dev.txt
python -m backend.scripts.run_offline_tests tests backend/tests
```
