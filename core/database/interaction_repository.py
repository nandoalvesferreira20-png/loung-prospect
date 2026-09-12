"""Append-only interaction history. Parent existence checked in each transaction."""
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from .connection import DEFAULT_DATABASE_PATH, connect_database
from .schema import initialize_database
from .lead_repository import LeadNotFoundError
from core.commercial.values import required_text


class InteractionRepository:
    def __init__(self, path=DEFAULT_DATABASE_PATH):
        self.path = Path(path)
        initialize_database(self.path)

    @staticmethod
    def _insert(connection, lead_id, *, tipo, canal, descricao, created_at):
        required_text(tipo, "um tipo de interação")
        if canal is not None and not isinstance(canal, str):
            raise ValueError("Canal deve ser texto ou vazio.")
        if not isinstance(descricao, str):
            raise ValueError("Descrição deve ser texto.")
        if connection.execute("SELECT id FROM leads WHERE id = ?", (lead_id,)).fetchone() is None:
            raise LeadNotFoundError(f"Lead not found: {lead_id}")
        cursor = connection.execute(
            "INSERT INTO lead_interactions (lead_id, tipo, canal, descricao, created_at) VALUES (?, ?, ?, ?, ?)",
            (lead_id, tipo, canal, descricao, created_at))
        return cursor.lastrowid

    def create_interaction(self, lead_id, *, tipo, canal=None, descricao=""):
        with closing(connect_database(self.path)) as connection:
            with connection:
                connection.execute("BEGIN IMMEDIATE")
                return self._insert(connection, lead_id, tipo=tipo, canal=canal, descricao=descricao,
                                    created_at=datetime.now(timezone.utc).isoformat())

    def list_interactions(self, lead_id):
        """Newest first; ID breaks timestamp ties deterministically."""
        with closing(connect_database(self.path)) as connection:
            return connection.execute("SELECT * FROM lead_interactions WHERE lead_id = ? "
                                      "ORDER BY created_at DESC, id DESC", (lead_id,)).fetchall()

    def get_last_interaction(self, lead_id):
        with closing(connect_database(self.path)) as connection:
            return connection.execute("SELECT * FROM lead_interactions WHERE lead_id = ? "
                                      "ORDER BY created_at DESC, id DESC LIMIT 1", (lead_id,)).fetchone()

    def count_interactions(self, lead_id):
        with closing(connect_database(self.path)) as connection:
            return connection.execute("SELECT COUNT(*) FROM lead_interactions WHERE lead_id = ?", (lead_id,)).fetchone()[0]
