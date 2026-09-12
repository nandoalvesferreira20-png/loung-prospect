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
            connection.execute("CREATE INDEX IF NOT EXISTS idx_interactions_lead_time "
                               "ON lead_interactions(lead_id, created_at DESC, id DESC)")
