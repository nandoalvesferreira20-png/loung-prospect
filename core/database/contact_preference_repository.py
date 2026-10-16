"""Per-lead routing overrides, independent from lead facts and saved messages."""
from contextlib import closing
from datetime import datetime, timezone
from core.sales.contact_routing import CONTACT_TYPES
from .connection import connect_database


class ContactPreferenceRepository:
    def __init__(self, path):
        self.path = path

    def get(self, lead_id):
        with closing(connect_database(self.path)) as connection:
            row = connection.execute("SELECT contact_type FROM lead_contact_preferences WHERE lead_id=?", (lead_id,)).fetchone()
            return row["contact_type"] if row else None

    def save(self, lead_id, contact_type):
        if contact_type not in CONTACT_TYPES.values():
            raise ValueError("Tipo de contato inválido.")
        with closing(connect_database(self.path)) as connection, connection:
            if connection.execute("SELECT id FROM leads WHERE id=?", (lead_id,)).fetchone() is None:
                raise ValueError("Lead não encontrado.")
            connection.execute("""INSERT INTO lead_contact_preferences (lead_id, contact_type, updated_at)
                VALUES (?, ?, ?) ON CONFLICT(lead_id) DO UPDATE SET
                contact_type=excluded.contact_type, updated_at=excluded.updated_at""",
                (lead_id, contact_type, datetime.now(timezone.utc).isoformat()))
