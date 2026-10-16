"""Manual conversation links and tracking. Legacy consent data stays intact."""
from contextlib import closing
from datetime import datetime, timezone
import re
from urllib.parse import urlencode

from core.commercial.values import utc_iso, STATUSES, commercial_status
from core.database.connection import connect_database
from core.database.interaction_repository import InteractionRepository
from core.sales.models import validate_message

SDR_STATUSES = STATUSES
CONSENTS = ("Desconhecido", "Autorizado", "Recusado", "Revogado")
DDDS = set("11 12 13 14 15 16 17 18 19 21 22 24 27 28 31 32 33 34 35 37 38 41 42 43 44 45 46 47 48 49 51 53 54 55 61 62 63 64 65 66 67 68 69 71 73 74 75 77 79 81 82 83 84 85 86 87 88 89 91 92 93 94 95 96 97 98 99".split())


def normalize_phone(value):
    """Brazilian DDD + subscriber, or an explicitly international +number.

    Validates syntax, not ownership/WhatsApp availability. No carrier-prefix
    guessing, missing DDD guessing, extensions or insertion of a ninth digit.
    """
    if value is None or (isinstance(value, str) and not value.strip()):
        raise ValueError("Telefone não informado. Cadastre um telefone com DDD ou +DDI para este lead.")
    if not isinstance(value, str) or not re.fullmatch(r"\+?[0-9()\s.\-]+", value.strip()):
        raise ValueError("Telefone inválido. Informe um número com DDD ou +DDI.")
    value = value.strip()
    digits = re.sub(r"[^0-9]", "", value)
    if value.startswith("+") and not digits.startswith("55"):
        if 8 <= len(digits) <= 15 and not digits.startswith("0"):
            return digits
        raise ValueError("Número internacional inválido.")
    if len(digits) in (12, 13) and digits.startswith("55"):
        digits = digits[2:]
    elif value.startswith("+"):
        raise ValueError("Número brasileiro incompleto.")
    if (len(digits) not in (10, 11) or digits[:2] not in DDDS
            or (len(digits) == 11 and digits[2] != "9")
            or (len(digits) == 10 and digits[2] not in "2345")):
        raise ValueError("Telefone brasileiro inválido; confira DDD e número.")
    return "55" + digits


def blocked(lead):
    row = dict(lead)
    return bool(row.get("do_not_contact") or row.get("status", "").strip().casefold() == "não contatar"
                or row.get("whatsapp_consent") in ("Recusado", "Revogado"))


def whatsapp_url(lead, message):
    row = dict(lead)
    if blocked(row):
        raise ValueError("Contato bloqueado: este lead não deve receber novas abordagens.")
    number = normalize_phone((row.get("whatsapp") or "").strip() or row.get("telefone"))
    validate_message(message)
    return f"https://wa.me/{number}?" + urlencode({"text": message})


class ContactService:
    def __init__(self, repository):
        self.repository = repository

    def save_tracking(self, lead_id, *, status, responsible, notes, contact_at=None):
        """Save SDR commercial fields without touching any legacy consent column."""
        status = commercial_status(status)
        if not all(isinstance(value, str) for value in (status, responsible, notes)) or not status.strip():
            raise ValueError("Informe uma etapa válida, responsável e observações em texto.")
        contacted = utc_iso(contact_at or None)
        now = datetime.now(timezone.utc)
        if contacted and datetime.fromisoformat(contacted) > now:
            raise ValueError("O contato realizado não pode ter data futura.")
        with closing(connect_database(self.repository.path)) as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT * FROM leads WHERE id=?", (lead_id,)).fetchone()
            if row is None:
                raise ValueError("Lead não encontrado.")
            if blocked(row) and status != "Não contatar":
                raise ValueError("Lead bloqueado para contato. Mantenha a etapa Não contatar.")
            if status not in STATUSES and status != commercial_status(row["status"]):
                raise ValueError("Etapa comercial inválida.")
            if status == "Contato realizado" and not (contacted or row["ultimo_contato"]):
                raise ValueError("Informe a data do contato realizado manualmente.")
            connection.execute("""UPDATE leads SET status=?, responsavel=?, observacoes=?,
                ultimo_contato=?, updated_at=?, do_not_contact=? WHERE id=?""",
                (status, responsible or None, notes or None, contacted or row["ultimo_contato"], now.isoformat(),
                 int(bool(row["do_not_contact"]) or status == "Não contatar"), lead_id))
            InteractionRepository._insert(connection, lead_id, tipo="Atualização SDR", canal="whatsapp",
                descricao=f"Etapa: {status}; responsável: {responsible or 'não informado'}; observações: {notes}",
                created_at=now.isoformat())

    def save(self, lead_id, *, status, consent, source, authorized_at, responsible, notes, contact_at=None):
        original_status = status
        status = commercial_status(status)
        current = self.repository.get_lead(lead_id)
        if (status not in STATUSES and (current is None or original_status != current["status"])) or consent not in CONSENTS:
            raise ValueError("Status ou consentimento inválido.")
        if not all(isinstance(value, str) for value in (source, responsible, notes)):
            raise ValueError("Origem, responsável e observações devem ser texto.")
        if status == "Não contatar" and consent == "Autorizado":
            consent = "Revogado"
        now = datetime.now(timezone.utc)
        at = utc_iso(authorized_at or None)
        contacted = utc_iso(contact_at or None)
        if any(value and datetime.fromisoformat(value) > now for value in (at, contacted)):
            raise ValueError("Autorização e contato não podem ter data futura.")
        if consent == "Autorizado" and (not source.strip() or not at):
            raise ValueError("Informe origem e data da autorização explícita.")
        if status == "Contato realizado" and not (contacted or (current is not None and current["ultimo_contato"])):
            raise ValueError("Informe a data do contato realizado manualmente.")
        with closing(connect_database(self.repository.path)) as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT * FROM leads WHERE id = ?", (lead_id,)).fetchone()
            if row is None:
                raise ValueError("Lead não encontrado.")
            refused = consent in ("Recusado", "Revogado") or status == "Não contatar"
            # An old refusal remains effective even if another screen changes status.
            if blocked(row) and not refused:
                raise ValueError("Lead bloqueado por recusa. Não é possível reativá-lo nesta versão.")
            number = normalize_phone((row["whatsapp"] or "").strip() or row["telefone"]) if consent == "Autorizado" and not refused else None
            if refused:
                status = "Não contatar"
            connection.execute("""UPDATE leads SET status=?, whatsapp_consent=?, consent_source=?,
                consent_at=?, consent_number=?, do_not_contact=?, responsavel=?, observacoes=?,
                ultimo_contato=?, updated_at=? WHERE id=?""",
                (status, consent, source.strip() or None, at, number, int(refused), responsible or None,
                 notes or None, contacted or row["ultimo_contato"], now.isoformat(), lead_id))
            description = (f"Status: {status}; consentimento: {consent}; origem: {source.strip() or 'não informada'}; "
                f"autorização: {at or 'não informada'}; responsável: {responsible or 'não informado'}; "
                f"contato manual: {contacted or 'não informado'}; observações: {notes or ''}")
            InteractionRepository._insert(connection, lead_id, tipo="Atualização SDR", canal="whatsapp",
                descricao=description, created_at=now.isoformat())

    def preview_url(self, lead_id, message):
        row = self.repository.get_lead(lead_id)
        if row is None:
            raise ValueError("Lead não encontrado.")
        return whatsapp_url(row, message)
