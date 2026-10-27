# Diagnóstico SQLite → PostgreSQL

## Evidência desta investigação

O relatório anterior contém 160 leads e 17 interações, nenhuma rejeição e nenhuma escrita contabilizada. Não contém a exceção original, portanto não permite atribuir retrospectivamente SQLSTATE ou constraint àquela tentativa.

Na sessão inspecionada, `LOUNG_MIGRATION_DSN` não está no ambiente do processo nem no `.env` da raiz. O código anterior acessava `os.environ['LOUNG_MIGRATION_DSN']` antes de conectar e convertia inclusive esse `KeyError` na mensagem genérica de transação. Ter `LOUNG_POSTGRES_DSN` configurado para o backend não configura a migração. O script não carregava `.env` automaticamente.

Agora `--env-file` permite ler explicitamente apenas a variável de migração; uma variável já definida no processo tem prioridade. Não há fallback para a conexão do backend. Não imprima a variável nem coloque a conexão na linha de comando.

## Diagnóstico e limites

O relatório registra `failureDiagnostic`: etapa, classe PostgreSQL, SQLSTATE, schema, tabela e constraint quando fornecidos pelo servidor. Nunca registra mensagem, DETAIL, CONTEXT, parâmetros, registros ou connection string. Erros sem configuração aparecem como `MissingMigrationConfiguration`, etapa `configuration`, SQLSTATE nulo: nenhuma conexão foi tentada.

As etapas distinguem conexão, organização, configuração de identidade, leitura do mapa, deduplicação, INSERT da tabela, INSERT do mapa e commit. Um erro em trigger durante INSERT aparece na etapa da tabela que disparou o trigger; os objetos do diagnóstico podem pertencer a `audit_events`. A execução inteira permanece em uma transação, incluindo auditoria e mapa. Contadores de escrita são zerados em falhas. Uma falha de comunicação durante commit exige verificar o destino antes de repetir: o relatório local não prova o resultado remoto.

O mapeamento continua sendo `(organization_id, source, table_name, legacy_id) → new_id`. Não mude `source-id` para contornar um erro. IDs dos filhos usam os IDs de destino dos pais, não os IDs originais. Os triggers locais usam `auth.uid()` nulo para migrações e auditoria com origem `migration`. Não foi demonstrado defeito de schema que justifique uma migration incremental.

## Verificação somente leitura no destino

Configure `LOUNG_MIGRATION_DSN` privadamente no ambiente ou em arquivo local ignorado pelo Git, separado da credencial de runtime. Substitua os valores abaixo pela organização e pelo **source-id exatos da tentativa original**. O exemplo da documentação anterior era `loung-desktop`; isso não prova qual valor foi usado no comando original.

```powershell
backend/.venv/Scripts/python.exe -m backend.scripts.check_migration_target --organization UUID_ORIGINAL --source-id SOURCE_ID_ORIGINAL --env-file .env
```

O comando abre transação `READ ONLY`, sem assumir outro papel, e consulta contagens da organização, mapa daquela origem, permissões de tabelas/sequências, triggers, FKs e hashes das funções de auditoria. Ele não importa dados. RLS também pode limitar as contagens conforme a credencial; uma contagem zero sem visibilidade suficiente não prova ausência de registros.

Compare o resultado com o estado anterior à tentativa. Mapa vazio e contagens inalteradas corroboram rollback. Sem baseline, contagens isoladas não distinguem registros preexistentes de uma importação anterior. Não exclua dados para produzir um destino vazio. A inspeção real não foi executada nesta investigação por ausência da credencial de migração.

## Repetição manual após revisão

Preserve o relatório antigo, use novos nomes para os relatórios e mantenha SQLite, organização e `source-id` originais. Faça primeiro a inspeção somente leitura acima e revise backup, rejeições, identidade e permissões.

```powershell
backend/.venv/Scripts/python.exe -m backend.scripts.migrate_sqlite --sqlite data/loung_prospect.db --organization UUID_ORIGINAL --source-id SOURCE_ID_ORIGINAL --dry-run --report backend/migration-review.json

# Executar manualmente apenas após revisar o dry-run e o destino:
backend/.venv/Scripts/python.exe -m backend.scripts.migrate_sqlite --sqlite data/loung_prospect.db --organization UUID_ORIGINAL --source-id SOURCE_ID_ORIGINAL --env-file .env --apply --confirm UUID_ORIGINAL --report backend/migration-apply-reviewed.json
```

Depois, repita a inspeção somente leitura. Confira `applied: true`, contagens e mapa; diferenças entre migrados e ignorados devem corresponder à deduplicação. Em falha, revise `failureDiagnostic` antes de qualquer nova tentativa. Não conceda privilégios ao backend, não desative triggers/RLS e não use um novo `source-id` como solução.

## Testes sintéticos

PostgreSQL isolado em memória, sem dados reais: importação e repetição, preservação de histórico, remapeamento de IDs, erro `23503 / ForeignKeyViolation` em trigger de interação que escreve auditoria, rollback integral de pais/filhos/auditoria/mapa e repetição idempotente após reparar o trigger sintético. Testes adicionais cobrem configuração ausente, arquivo explícito sem interpolação de segredos, prioridade do ambiente, sanitização de erros e inspeção somente leitura. O trigger defeituoso existe apenas no teste e é removido no `finally`.
