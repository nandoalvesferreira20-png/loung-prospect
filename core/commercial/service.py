"""Explicit manual interaction + follow-up updates in one SQLite transaction."""
from contextlib import closing
from datetime import datetime, timezone

from core.database.connection import DEFAULT_DATABASE_PATH, connect_database
from core.database.lead_repository import LeadRepository
from core.database.interaction_repository import InteractionRepository
from .values import commercial_values

_UNSET = object()


class CommercialService:
    def __init__(self, path=DEFAULT_DATABASE_PATH):
        self.interactions = InteractionRepository(path)
        self.path = self.interactions.path

    def register_interaction(self, lead_id, *, tipo, canal=None, descricao="", status=_UNSET,
                             proxima_acao=_UNSET, proximo_contato=_UNSET, canal_preferencial=_UNSET):
        """Omitted updates are preserved; explicit None clears optional values.

        Every manual interaction, including Observação, marks the registration
        time as ultimo_contato. It does not claim or trigger message delivery.
        """
        supplied = {key: value for key, value in dict(status=status, proxima_acao=proxima_acao,
                    proximo_contato=proximo_contato, canal_preferencial=canal_preferencial).items()
                    if value is not _UNSET}
        values = commercial_values(supplied)
        with closing(connect_database(self.path)) as connection:
            with connection:
                connection.execute("BEGIN IMMEDIATE")
                now = datetime.now(timezone.utc).isoformat()
                interaction_id = self.interactions._insert(connection, lead_id, tipo=tipo,
                    canal=canal, descricao=descricao, created_at=now)
                LeadRepository._update_commercial(connection, lead_id,
                    {**values, "ultimo_contato": now}, timestamp=now)
                return interaction_id
