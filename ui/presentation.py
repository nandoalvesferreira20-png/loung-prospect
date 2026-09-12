"""Read-only display projections using existing score and calendar helpers."""
from datetime import datetime
from core.commercial.day import build_day
from core.qualification.rules import classify_priority
from ui.commercial_logic import format_date, priority_label


def priority_tone(score):
    if score is None:
        return "neutral"
    return {"high": "accent", "good": "success", "medium": "warning", "low": "neutral"}[classify_priority(score).value]


def status_tone(status):
    if status == "Fechado":
        return "success"
    if status in ("Não respondeu", "Retornar depois"):
        return "warning"
    if status in ("Em conversa", "Reunião agendada", "Proposta enviada"):
        return "accent"
    return "neutral"


def portfolio_values(row):
    return (row["empresa"], row["qualification_score"] if row["qualification_score"] is not None else "—",
            priority_label(row["qualification_score"]), row["cidade"] or "—", row["segmento"] or "—",
            row["responsavel"] or "—", row["status"], format_date(row["proximo_contato"]) or "—")


def overview_data(rows, reference=None):
    day = build_day(rows, reference or datetime.now().date())
    priorities = {key: 0 for key in ("high", "good", "medium", "low", "unknown")}
    for row in rows:
        score = row["qualification_score"]
        priorities["unknown" if score is None else classify_priority(score).value] += 1
    return dict(total=len(rows), today=day.counts["hoje"], overdue=day.counts["atrasados"],
                meetings=day.counts["reunioes"], priorities=priorities, actions=day.rows[:8], invalid_dates=day.invalid_dates)


def empty_copy(context, has_rows):
    if has_rows:
        return ""
    return {"portfolio": "Nenhum lead encontrado. Ajuste os filtros ou importe uma planilha.",
            "day": "Nenhum lead para esta seleção. Seu dia está em dia.",
            "actions": "Nenhuma próxima ação disponível. Organize os retornos na Carteira."}[context]
