# Execução local do Loung Prospect

O padrão é `LOUNG_AUTH_MODE=local`: Next.js + BFF + FastAPI + SQLite, sem login, Supabase ou PostgreSQL. Dashboard, Leads, CRM, Pipeline, Meu Dia, Google Places, CSV/Excel e SDR Groq reutilizam os componentes e serviços existentes.

## Preparação

Use Python 3.11+ e Node conforme `web/package.json` (`^22.19.0 || >=24.6.0`). Não é necessário instalar o desktop, Playwright ou PostgreSQL para executar a versão web.

O repositório já tinha alterações não commitadas. Preserve um ponto de recuperação manual: revise `git status`, faça um commit quando desejar ou copie o diretório completo para outro local. Nenhum commit foi criado automaticamente.

Se já possui `.env` ou `web/.env.local`, preserve-os e compare com os exemplos; não os sobrescreva. Utilize um arquivo separado para o backend local, por exemplo `.env.local`. Não copie DSNs ou chaves Supabase para ele. O launcher carrega o arquivo indicado; variáveis exportadas no processo têm precedência.

Windows / PowerShell, na raiz (comandos de cópia somente se o destino ainda não existir):

```powershell
py -3 -m venv backend/.venv
backend/.venv/Scripts/python.exe -m pip install -r backend/requirements.txt
Copy-Item .env.example .env.local
Copy-Item web/.env.example web/.env.local
cd web
npm.cmd ci
cd ..
```

macOS / Terminal, na raiz:

```bash
python3 -m venv backend/.venv
backend/.venv/bin/python -m pip install -r backend/requirements.txt
cp -n .env.example .env.local
cp -n web/.env.example web/.env.local
cd web
npm ci
cd ..
```

Preencha `GOOGLE_PLACES_API_KEY`, `GROQ_API_KEY` e um `GROQ_MODEL` disponível na sua conta em `.env.local`. Chaves ficam no backend. Nunca use prefixo `NEXT_PUBLIC_` para elas. Sem as chaves, CRM e SQLite funcionam; a integração correspondente informa o erro quando acionada. O launcher lista integrações não configuradas.

## Iniciar

Windows, terminal 1 na raiz:

```powershell
backend/.venv/Scripts/python.exe -m backend.scripts.run_api --env-file .env.local
```

macOS, terminal 1 na raiz:

```bash
backend/.venv/bin/python -m backend.scripts.run_api --env-file .env.local
```

Terminal 2, Windows:

```powershell
cd web
npm.cmd run dev
```

Terminal 2, macOS:

```bash
cd web
npm run dev
```

Abra **http://127.0.0.1:3000/**. Backend: http://127.0.0.1:8000/health. Os scripts fixam loopback. Para build local: `npm run build` e `npm start` em `web` (Windows: `npm.cmd`). Não use host público, túneis, proxy reverso ou encaminhamento de portas. O modo sem login rejeita hosts/origens externos, peers remotos no FastAPI e ambientes conhecidos de hospedagem pública; não é um modo de publicação.

## Banco e migrações

- Padrão: `data/loung_prospect.db`, relativo à raiz. Altere `LOUNG_DATABASE_PATH` para outro arquivo SQLite local se desejar uma base independente.
- O bootstrap ocorre no ciclo de inicialização do servidor configurado pelo ambiente. Importar módulos não cria nem migra a base. Testes fornecem bases temporárias.
- Base nova começa vazia. Base existente recebe snapshot validado em `data/backups/*-pre-local-*.db` antes da primeira migração local. A migração desktop é aditiva e idempotente; extensões locais usam `local_migrations` e `PRAGMA user_version=1`. Uma interrupção permite retomar as operações aditivas.
- Nenhum lead remoto é copiado. Não há acesso ao Supabase no modo local.
- Pipeline, notas e follow-ups usam leads/interações; SDR e revisões usam outreach/outreach_revisions; preferências de contato existentes são preservadas; configurações da interface são salvas em `local_settings` via BFF.
- Escritas usam transações, busy timeout e locks. CRUD manual usa revisão otimista: edição concorrente retorna 409. Importações deduplicam por provider/place ID, Maps, empresa/endereço ou empresa/telefone. Nomes iguais sozinhos não provam duplicidade.
- WAL permite leituras concorrentes. Não execute várias instâncias do backend sobre a mesma base. Não compartilhe SQLite em unidade de rede.
- Triggers impedem novos filhos sem lead, revisões sem abordagem correspondente e exclusões de pais com histórico, sem reconstruir tabelas antigas. Eventuais órfãos legados são preservados para inspeção manual. Não existe endpoint de exclusão de leads.
- Bancos, WAL, backups, ambientes e logs não devem ser versionados. Para backup manual, pare o servidor ou use a API de backup SQLite; não copie só o arquivo principal durante uma escrita WAL.

## Retorno ao SaaS

Código em `backend/persistence`, autenticação em `web/src/lib/auth`, páginas de login e migrations `supabase/migrations` permanecem preservados. Exemplos anteriores estão em [saas-env-examples](saas-env-examples).

Use um arquivo separado no backend com `LOUNG_AUTH_MODE=saas`, `LOUNG_STORAGE_BACKEND=postgres`, `SUPABASE_URL`, DSN de aplicação e `LOUNG_ENABLE_WRITES` conforme a política anterior. No frontend, configure `LOUNG_AUTH_MODE=saas` e as variáveis públicas Supabase dos exemplos anteriores. Reinicie ambos os processos. O backend recusa combinações local/PostgreSQL e SaaS/SQLite; o frontend seleciona modo em runtime. JWT, membership, organization_id e RLS continuam no caminho SaaS, sem fallback SQLite. Não execute migrations remotas como parte desta transição.

## Validação e limites

Use `backend/requirements-dev.txt` para testes da API e `requirements-dev.txt` para testes do desktop. Rode `python -m backend.scripts.run_offline_tests backend/tests` e, em `web`, `npm test`, `npm run typecheck`, `npm run lint`, `npm run build`. A suíte local cobre bootstrap sem Supabase, migração/backup, CRUD, concorrência, Pipeline, follow-ups, SDR simulado, reinício e bloqueios de rede. A regressão existente cobre Places simulado, importação/deduplicação, CSV e Excel.

Pesquisas e rascunhos SDR ainda não salvos são transitórios e expiram. Mensagens salvas e revisões persistem. Dados pertencem a cada máquina. Google Places e Groq exigem internet e credenciais válidas; “local” descreve execução e persistência.

Veja [AUDIT.md](AUDIT.md) e [VALIDATION.md](VALIDATION.md).
