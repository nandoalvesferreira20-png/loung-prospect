"""Date/presentation helpers and the modal controller; no SQL or scoring rules."""
from datetime import datetime, timezone

from core.commercial.service import CommercialService
from core.commercial.values import required_text
from core.qualification.rules import classify_priority


def parse_contact_date(text, *, tz=None):
    if not text.strip():
        return None
    try:
        value = datetime.strptime(text.strip(), "%d/%m/%Y %H:%M")
    except ValueError:
        raise ValueError("Informe data e hora no formato dd/mm/aaaa HH:MM.") from None
    if tz is not None:
        value = value.replace(tzinfo=tz)
    return value.astimezone(timezone.utc).isoformat()


def parse_reference_date(text):
    try:
        return datetime.strptime(text.strip(), "%d/%m/%Y").date()
    except ValueError:
        raise ValueError("Informe a data no formato dd/mm/aaaa.") from None


def format_date(value, *, tz=None):
    if not value:
        return ""
    try:
        value = datetime.fromisoformat(value)
        if value.utcoffset() is None:
            raise ValueError
        return value.astimezone(tz).strftime("%d/%m/%Y %H:%M")
    except (TypeError, ValueError):
        return "Data inválida"


def priority_label(score):
    if score is None:
        return "Não disponível"
    return {"high": "Alta", "good": "Boa", "medium": "Média", "low": "Baixa"}[classify_priority(score).value]


def day_values(row):
    return (row["empresa"], row["responsavel"] or "", row["status"],
            row["qualification_score"] if row["qualification_score"] is not None else "",
            priority_label(row["qualification_score"]), row["proxima_acao"] or "",
            format_date(row["proximo_contato"]))


def interaction_values(*, tipo, canal, descricao):
    required_text(tipo, "um tipo de interação")
    if not isinstance(descricao, str):
        raise ValueError("Descrição deve ser texto.")
    return dict(tipo=tipo, canal=canal or None, descricao=descricao)


def history_text(rows):
    if not rows:
        return "Nenhuma interação registrada."
    return "\n\n".join(f"● {format_date(row['created_at'])}\n   {row['canal'] or 'Canal não informado'} · {row['tipo']}\n\n"
                        f"   {row['descricao'] or '(Sem descrição)'}\n" for row in rows)


class CommercialLead:
    def __init__(self, repository, lead_id):
        self.repository = repository
        self.lead_id = lead_id
        self.service = CommercialService(repository.path)

    def load(self):
        row = self.repository.get_lead(self.lead_id)
        if row is None:
            raise ValueError("Lead não encontrado. Atualize a lista.")
        return row

    def history(self):
        return self.service.interactions.list_interactions(self.lead_id)

    def save(self, *, status, responsavel, observacoes, proxima_acao, proximo_contato, canal_preferencial):
        self.repository.update_commercial_followup(self.lead_id, status=status,
            responsavel=responsavel or None, observacoes=observacoes or None,
            proxima_acao=proxima_acao or None, proximo_contato=parse_contact_date(proximo_contato),
            canal_preferencial=canal_preferencial or None)

    def register(self, *, tipo, canal, descricao, update_followup=False, status="",
                 proxima_acao="", proximo_contato=""):
        values = interaction_values(tipo=tipo, canal=canal, descricao=descricao)
        if update_followup:
            values.update(status=status, proxima_acao=proxima_acao or None,
                          proximo_contato=parse_contact_date(proximo_contato))
        return self.service.register_interaction(self.lead_id, **values)
