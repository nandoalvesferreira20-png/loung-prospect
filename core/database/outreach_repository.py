"""Draft persistence. Approval is an explicit action, never a sent interaction."""
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from .connection import DEFAULT_DATABASE_PATH, connect_database
from .schema import initialize_database
from .lead_repository import LeadNotFoundError
from core.sales.models import OutreachStatus, SalesGeneration, validate_message


class OutreachRepository:
    def __init__(self, path=DEFAULT_DATABASE_PATH):
        self.path = Path(path)
        initialize_database(self.path)

    def create(self, lead_id, result: SalesGeneration, *, provider=None, model=None):
        if not isinstance(result, SalesGeneration):
            raise ValueError("Resultado de geração inválido.")
        now = datetime.now(timezone.utc).isoformat()
        with closing(connect_database(self.path)) as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            self._require_lead(connection, lead_id)
            cursor = connection.execute(
                "INSERT INTO outreach (lead_id, canal, mensagem, angulo, confianca, status, criado_em, atualizado_em, provider, model) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (lead_id, "whatsapp", result.mensagem, result.angulo, result.confianca, OutreachStatus.GENERATED.value, now, now, provider, model))
            return cursor.lastrowid

    @staticmethod
    def _require_lead(connection, lead_id):
        if connection.execute("SELECT id FROM leads WHERE id = ?", (lead_id,)).fetchone() is None:
            raise LeadNotFoundError("Lead não encontrado.")

    def history(self, lead_id):
        with closing(connect_database(self.path)) as connection:
            return connection.execute("SELECT * FROM outreach WHERE lead_id = ? ORDER BY criado_em DESC, id DESC", (lead_id,)).fetchall()

    def update(self, lead_id, outreach_id, *, status, message=None):
        status = OutreachStatus(status)
        if status not in (OutreachStatus.EDITED, OutreachStatus.APPROVED, OutreachStatus.CANCELLED):
            raise ValueError("Transição não disponível nesta versão.")
        if status != OutreachStatus.CANCELLED:
            validate_message(message)
        now = datetime.now(timezone.utc).isoformat()
        with closing(connect_database(self.path)) as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            self._require_lead(connection, lead_id)
            row = connection.execute("SELECT * FROM outreach WHERE id = ? AND lead_id = ?", (outreach_id, lead_id)).fetchone()
            if row is None:
                raise ValueError("Abordagem não encontrada para este lead.")
            if row["status"] not in (OutreachStatus.GENERATED.value, OutreachStatus.EDITED.value):
                raise ValueError("Versão encerrada. Gere outra abordagem para preservar o histórico.")
            connection.execute("UPDATE outreach SET mensagem = ?, status = ?, atualizado_em = ?, aprovado_em = ? WHERE id = ? AND lead_id = ?",
                (row["mensagem"] if status == OutreachStatus.CANCELLED else message, status.value, now,
                 now if status == OutreachStatus.APPROVED else None, outreach_id, lead_id))
