"""Display-only labels. Stored values, timestamps and scores are untouched."""
from datetime import datetime
from zoneinfo import ZoneInfo

STATUS_LABELS = {"GERADA": "Gerada", "EDITADA": "Editada", "APROVADA": "Aprovada", "CANCELADA": "Descartada"}


def local_date(value, *, short=False) -> str:
    try:
        at = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if at.tzinfo is None:
            return "Data sem fuso"
        return at.astimezone(ZoneInfo("America/Sao_Paulo")).strftime("%d/%m às %H:%M" if short else "%d/%m/%Y às %H:%M")
    except (ValueError, TypeError, AttributeError):
        return "Data indisponível"


def draft_label(row) -> str:
    stamp = local_date(row["criado_em"], short=True)
    return f"#{row['id']} · {stamp} · {STATUS_LABELS.get(row['status'], row['status'])}"


def confidence_badge(value):
    if not isinstance(value, (int, float)) or not 0 <= value <= 1:
        return "Confiança não informada", "neutral"
    return f"Confiança {value:.0%}", "danger" if value < .5 else "warning" if value <= .75 else "success"


def feedback_tone(text):
    value = text.casefold()
    if "não foi possível" in value or "erro" in value:
        return "danger"
    if any(word in value for word in ("salva", "salvo", "copiado", "conversa solicitada")):
        return "success"
    return "info"
