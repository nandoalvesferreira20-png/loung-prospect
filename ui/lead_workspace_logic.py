"""Workspace presentation helpers; no SQL or automatic contact."""
from urllib.parse import urlsplit

from core.importers import import_leads_from_excel

STATUSES = ("Novo", "Em análise", "Contatado", "Respondeu", "Reunião", "Proposta", "Fechado", "Perdido")
LIST_FIELDS = ("qualification_score", "empresa", "cidade", "segmento", "opportunity", "responsavel", "status")


def parse_min_score(text):
    if not text.strip():
        return None
    try:
        value = int(text)
    except ValueError:
        raise ValueError("Score mínimo deve ser inteiro de 0 a 100.") from None
    if not 0 <= value <= 100:
        raise ValueError("Score mínimo deve ser inteiro de 0 a 100.")
    return value


def valid_url(value):
    if not isinstance(value, str) or any(c.isspace() for c in value):
        return False
    try:
        parsed = urlsplit(value)
        parsed.port
        return bool(parsed.scheme in ("http", "https") and parsed.hostname
                    and not parsed.username and not parsed.password and "\\" not in value)
    except ValueError:
        return False


def counts(rows):
    statuses = [row["status"] for row in rows]
    return dict(total=len(rows), novos=statuses.count("Novo"), contatados=statuses.count("Contatado"),
                responderam=statuses.count("Respondeu"), reuniao=statuses.count("Reunião"))


def list_values(row):
    return tuple("" if row[field] is None else row[field] for field in LIST_FIELDS)


class LeadWorkspace:
    def __init__(self, repository):
        self.repository = repository

    def list(self, *, status="", segmento="", responsavel="", score="", search=""):
        filters = {key: value for key, value in (("status", status), ("segmento", segmento), ("responsavel", responsavel)) if value}
        minimum = parse_min_score(score)
        if minimum is not None:
            filters["score_minimo"] = minimum
        rows = self.repository.list_leads(**filters)
        term = search.strip().casefold()
        return [row for row in rows if not term or any(term in str(row[field] or "").casefold() for field in ("empresa", "cidade"))]

    def import_file(self, path):
        return import_leads_from_excel(path, self.repository)

    def save(self, lead_id, status, responsible, notes):
        if not status.strip():
            raise ValueError("Informe um status.")
        self.repository.update_details(lead_id, status=status, responsavel=responsible or None, observacoes=notes or None)
