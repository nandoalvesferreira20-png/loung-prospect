"""V1 schema initialization. No destructive migrations."""

from contextlib import closing

from .connection import (
    DEFAULT_DATABASE_PATH,
    connect_database,
)


LEADS_SCHEMA = """
CREATE TABLE IF NOT EXISTS leads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    empresa TEXT NOT NULL,
    cidade TEXT,
    segmento TEXT,

    telefone TEXT,
    whatsapp TEXT,
    email TEXT,

    site TEXT,
    endereco TEXT,

    avaliacao TEXT,
    quantidade_avaliacoes INTEGER,

    google_maps TEXT,

    qualification_status TEXT,
    qualification_score INTEGER,
    opportunity TEXT,
    qualification_reasons TEXT,
    qualification_evidence TEXT,
    qualification_limitations TEXT,
    rules_version TEXT,
    analyzed_at TEXT,

    responsavel TEXT,
    status TEXT NOT NULL DEFAULT 'Novo',
    observacoes TEXT,

    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,

    provider TEXT,
    provider_place_id TEXT
)
"""


MIGRATION_COLUMNS = {
    "whatsapp_consent": "TEXT NOT NULL DEFAULT 'Desconhecido'",
    "consent_source": "TEXT",
    "consent_at": "TEXT",
    "consent_number": "TEXT",
    "do_not_contact": "INTEGER NOT NULL DEFAULT 0",
    "provider": "TEXT",
    "provider_place_id": "TEXT",
    "quantidade_avaliacoes": "INTEGER",
    "ultimo_contato": "TEXT",
    "proximo_contato": "TEXT",
    "proxima_acao": "TEXT",
    "canal_preferencial": "TEXT",
}

INTERACTIONS_SCHEMA = """
CREATE TABLE IF NOT EXISTS lead_interactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lead_id INTEGER NOT NULL,
    tipo TEXT NOT NULL,
    canal TEXT,
    descricao TEXT,
    created_at TEXT NOT NULL
)
"""

OUTREACH_SCHEMA = """
CREATE TABLE IF NOT EXISTS outreach (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lead_id INTEGER NOT NULL,
    canal TEXT NOT NULL DEFAULT 'whatsapp',
    mensagem TEXT NOT NULL,
    angulo TEXT,
    confianca REAL,
    status TEXT NOT NULL CHECK(status IN ('GERADA','EDITADA','APROVADA','ENVIADA','RESPONDEU','CANCELADA')),
    criado_em TEXT NOT NULL,
    atualizado_em TEXT NOT NULL,
    aprovado_em TEXT,
    enviado_em TEXT,
    respondeu_em TEXT
)
"""


def initialize_database(
    path=DEFAULT_DATABASE_PATH,
) -> None:
    """Create or safely update the local SQLite schema.

    Existing rows are preserved. Missing additive columns are created
    idempotently.
    """

    with closing(
        connect_database(path)
    ) as connection:
        with connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                LEADS_SCHEMA
            )

            columns = {
                row[1]
                for row in connection.execute(
                    "PRAGMA table_info(leads)"
                )
            }

            for (
                column,
                column_type,
            ) in MIGRATION_COLUMNS.items():

                if column in columns:
                    continue

                connection.execute(
                    f"ALTER TABLE leads "
                    f"ADD COLUMN {column} {column_type}"
                )
            connection.execute(INTERACTIONS_SCHEMA)
            connection.execute(OUTREACH_SCHEMA)
            connection.execute("""CREATE TABLE IF NOT EXISTS lead_contact_preferences (
                lead_id INTEGER PRIMARY KEY, contact_type TEXT NOT NULL CHECK
                (contact_type IN ('recepcao_equipe', 'contato_direto', 'indefinido')),
                updated_at TEXT NOT NULL)""")
            connection.execute("""CREATE TABLE IF NOT EXISTS template_drafts (
                lead_id INTEGER PRIMARY KEY, message TEXT NOT NULL, channel TEXT NOT NULL,
                objective TEXT NOT NULL, tone TEXT NOT NULL, updated_at TEXT NOT NULL)""")
            connection.execute("""CREATE TABLE IF NOT EXISTS outreach_revisions (
                id INTEGER PRIMARY KEY AUTOINCREMENT, outreach_id INTEGER NOT NULL,
                lead_id INTEGER NOT NULL, mensagem TEXT NOT NULL, status TEXT NOT NULL,
                recorded_at TEXT NOT NULL)""")
            outreach_columns = {row[1] for row in connection.execute("PRAGMA table_info(outreach)")}
            for column in ("provider", "model", "revisado_em"):
                if column not in outreach_columns:
                    connection.execute(f"ALTER TABLE outreach ADD COLUMN {column} TEXT")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_outreach_lead_time ON outreach(lead_id, criado_em DESC, id DESC)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_interactions_lead_time "
                               "ON lead_interactions(lead_id, created_at DESC, id DESC)")
