"""Explicitly saved template messages, separate from AI review history."""
from contextlib import closing
from datetime import datetime, timezone
from .connection import connect_database


class TemplateDraftRepository:
    def __init__(self, path):
        self.path = path

    def load(self, lead_id):
        with closing(connect_database(self.path)) as connection:
            return connection.execute("SELECT * FROM template_drafts WHERE lead_id=?", (lead_id,)).fetchone()

    def save(self, lead_id, message, channel, objective, tone):
        if not message.strip():
            raise ValueError("Digite ou gere uma mensagem antes de salvar.")
        with closing(connect_database(self.path)) as connection, connection:
            if connection.execute("SELECT id FROM leads WHERE id=?", (lead_id,)).fetchone() is None:
                raise ValueError("Lead não encontrado. Reabra os detalhes.")
            connection.execute("""INSERT INTO template_drafts
                (lead_id, message, channel, objective, tone, updated_at) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(lead_id) DO UPDATE SET message=excluded.message, channel=excluded.channel,
                objective=excluded.objective, tone=excluded.tone, updated_at=excluded.updated_at""",
                (lead_id, message, channel, objective, tone, datetime.now(timezone.utc).isoformat()))
