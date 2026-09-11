"""V1 schema initialization. No destructive migrations."""
from contextlib import closing

from .connection import DEFAULT_DATABASE_PATH, connect_database

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
    updated_at TEXT NOT NULL
)
"""


def initialize_database(path=DEFAULT_DATABASE_PATH) -> None:
    with closing(connect_database(path)) as connection:
        with connection:
            connection.execute(LEADS_SCHEMA)
