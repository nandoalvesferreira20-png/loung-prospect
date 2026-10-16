# Loung Prospect Web — Fase 2.4

Pipeline Kanban, perfil comercial `/leads/[id]`, histórico, observações e Meu Dia
funcionais. Escrita opt-in com backup e proteção contra conflitos. Sem mudanças
no schema/desktop. Veja [Fase 2.4](docs/phase-2-4.md) para regras e validação.

Frontend independente dentro do repositório existente. A aplicação desktop continua em `main.py` / `app.py`; nenhum módulo Python precisa ser movido para executar a web.

## Executar localmente

Requer Node.js 20.9 ou superior e npm. Validado com Node 24.

```powershell
cd web
npm ci
npm run dev
```

Abra http://127.0.0.1:3000. O servidor fica vinculado ao loopback nesta fase local sem autenticação. Se a porta estiver ocupada, o Next informa outra porta. Para uma porta explícita: `npm run dev -- --port 3100`.

```powershell
npm run lint
npm run typecheck
npm run build
npm run start
```

Não é necessário configurar `.env` nem iniciar a aplicação desktop. Para consultar dados, inicie também o backend conforme [backend/README.md](../backend/README.md). Sem ele, a interface mostra indisponibilidade e permite tentar novamente. As dependências JavaScript e o lockfile pertencem exclusivamente a esta pasta. Não há outro repositório Git.

## O que funciona nesta fase

- Dashboard, Prospecção, Leads, SDR Inteligente, Pipeline e Configurações, com navegação responsiva e indicação da página ativa.
- Menu móvel com diálogo acessível, fechamento por Escape e controle de foco; atalho para pular ao conteúdo.
- Prospecção real por Google Places via BFF/FastAPI e motor Python existente: nicho, localização, bairro, quantidade e filtro sem site próprio/score. Jobs em segundo plano, andamento sem porcentagens inventadas, cancelamento, resultados paginados, seleção, importação deduplicada e exportação CSV/Excel.
- A pesquisa nunca grava automaticamente. Importação exige `LOUNG_ENABLE_WRITES=1` no processo backend, com backup antes da primeira inserção. Consulte o relatório 2.2 antes de habilitar.
- Tabela de leads reais com busca, etapas, seleção local e paginação pelo servidor. Etapas personalizadas e aliases legados são preservados. Não há registros simulados na aplicação.
- Dashboard com total, contatos para hoje, retornos atrasados e reuniões, distribuição atual por etapa e seleção de próximas ações seguindo as regras do desktop.
- SDR funcional: seleção de lead real, classificação automática/manual, serviço, geração Groq, regeneração, edição, cópia e WhatsApp em nova aba com texto preenchido. Histórico compatível, salvamento revisado/aprovado opt-in e proteção contra substituição de texto não salvo. Veja [Fase 2.3](docs/phase-2-3.md).
- Kanban estrutural com etapas comerciais. Sem movimentação fictícia ou dados de demonstração.
- Nome de exibição e atalho preferido em `localStorage`, chave `loung-prospect:web:preferences:v1`. O atalho pode ser aberto na própria tela de configurações. Bloqueios de armazenamento e clipboard têm feedback.
- Gráfico Recharts com distribuição real por etapa, estados de carregamento, erro e página não encontrada.

O travessão nos indicadores significa **dado indisponível**, não zero leads. O frontend não lê SQLite diretamente: consulta o BFF Next, que acessa o FastAPI local. O navegador não chama Google Places/Groq diretamente nem recebe credenciais. Não há autenticação nesta fase; mantenha a aplicação em ambiente local.

## Organização

```text
src/app/                 # App Router, páginas e estados de rota
src/components/          # Shell, estados vazios, tabela e gráfico
src/components/ui/       # Primitivas shadcn/ui adaptadas ao produto
src/lib/api/             # Contratos tipados, cliente HTTP, hook e BFF local
src/lib/utils.ts         # Composição de classes (cn)
docs/architecture.md     # Inventário Python e decisão de backend
scripts/check_ui.py      # Verificação local usando Playwright Python existente
scripts/check_read_api.py # Integração com FastAPI usando banco sintético
scripts/check_prospecting.py # Fluxo completo com transporte Google simulado
```

As primitivas locais seguem o modelo de código aberto shadcn/ui: Radix, CVA, `cn`, variáveis Tailwind e componentes pertencentes ao projeto. `components.json` mantém os aliases e a configuração para adicionar componentes conforme necessário; não foi instalado um pacote completo de componentes sem uso.

## Validação visual e funcional

Com o servidor em execução, a partir da raiz do repositório:

```powershell
.venv\Scripts\python.exe web\scripts\check_ui.py http://localhost:3000
```

O script usa o Playwright já disponível no ambiente Python, com Edge ou Chrome instalado, sem instalar bibliotecas no desktop. Os artefatos ficam em `web/test-results/` (ignorados pelo Git). Ele visita as seis rotas em três resoluções, testa menu móvel, validação do formulário, preferências e editor, e rejeita erros JavaScript e requisições a serviços externos.

Para validação manual sem consumo, use a fixture sintética documentada na Fase 2.2. O teste geral valida apenas entradas inválidas do formulário e não inicia pesquisa. Na configuração real, enviar critérios válidos em Prospecção consulta o Google e pode consumir quota; a gravação continua exigindo seleção e configuração explícitas. A edição/cópia no SDR não envia mensagens.

Para testar a leitura de ponta a ponta, use o servidor sintético e os comandos em [backend/README.md](../backend/README.md). O teste recusa uma base sem a assinatura sintética, evitando usar leads reais em capturas e filtros automatizados.

Veja a decisão arquitetural em [docs/architecture.md](docs/architecture.md) e o relatório atual em [docs/phase-2-2.md](docs/phase-2-2.md). Os relatórios [phase-2-1.md](docs/phase-2-1.md) e [validation.md](docs/validation.md) preservam as validações históricas anteriores.
