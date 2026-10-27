# Auditoria da arquitetura anterior

O Git contém alterações prévias extensas, incluindo autenticação, PostgreSQL e melhorias de interface. Nenhum commit, branch ou descarte foi executado. Recomenda-se um commit manual ou uma cópia integral antes de integrar este trabalho.

- `web/src/proxy.ts`: Supabase SSR, cookies e redirecionamentos. O caminho local existente não validava ambiente ou origem.
- `web/src/lib/auth/server.ts`: injeta JWT no BFF; havia um caminho local parcial. `SessionGate` consulta `/api/session` e o menu reconhece role local.
- BFF em `web/src/lib/api`: valida contratos, origem e destino loopback. Criação/edição passam por `team-proxy`.
- `backend/config.py`: ambiente usava PostgreSQL por padrão; Settings explícito já suportava SQLite.
- `backend/persistence/runtime.py`: JWT criptográfico, membership por requisição, organization_id via ContextVar, RLS e transações PostgreSQL. Preservado.
- `backend/main.py`: aplicação SQLite reutiliza leitura, CRM, prospecção e SDR; faltavam bootstrap independente do desktop e CRUD manual.
- `core/database/schema.py`: schema desktop aditivo com leads, interações, preferências, SDR, revisões e rascunhos. Sem migrations versionadas ou FKs nas tabelas antigas.
- `SelectionStore`: BEGIN IMMEDIATE, deduplicação por identidade, busy timeout e backup antes da primeira escrita. CRM e SDR reutilizam lock, backup e revisão otimista.
- Pipeline: status do lead; movimentos e follow-ups em `lead_interactions`. Preferências da interface ficavam em localStorage.
- Google Places: JobManager com worker limitado, importação selecionada e CSV/XLSX. Resultados de pesquisa são transitórios.
- Groq: SdrService gera rascunhos com revisão manual. WhatsApp é aberto por ação do usuário, sem envio automático.
- SQLite anterior: `data/loung_prospect.db`. Não foi usado nos testes nem importado do Supabase.

Alterações necessárias: seleção explícita de modo; proteção de acesso local; bootstrap/migrations SQLite; CRUD transacional; sessão local sem Supabase; configurações e exemplos de ambiente; documentação e testes offline. Migrations Supabase, código SaaS e desktop foram preservados.
