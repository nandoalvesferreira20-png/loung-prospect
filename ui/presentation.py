"""Read-only display projections using existing score and calendar helpers."""
from datetime import datetime
from collections import Counter
from core.commercial.day import build_day
from core.qualification.rules import classify_priority
from ui.commercial_logic import format_date, priority_label
from core.commercial.values import commercial_status


def priority_tone(score):
    if score is None:
        return "neutral"
    return {"high": "accent", "good": "accent", "medium": "warning", "low": "neutral"}[classify_priority(score).value]


def status_tone(status):
    status = commercial_status(status)
    if status == "Fechado":
        return "success"
    if status in ("Não respondeu", "Retornar depois"):
        return "warning"
    if status in ("Em conversa", "Reunião agendada", "Proposta enviada"):
        return "accent"
    return "neutral"


def portfolio_values(row):
    return (row["empresa"], commercial_status(row["status"]), format_date(row["proximo_contato"]) or "—",
            priority_label(row["qualification_score"]), row["qualification_score"] if row["qualification_score"] is not None else "—",
            row["cidade"] or "—", row["segmento"] or "—", row["responsavel"] or "—")


def overview_data(rows, reference=None):
    day = build_day(rows, reference or datetime.now().date())
    priorities = {key: 0 for key in ("high", "good", "medium", "low", "unknown")}
    for row in rows:
        score = row["qualification_score"]
        priorities["unknown" if score is None else classify_priority(score).value] += 1
    return dict(total=len(rows), today=day.counts["hoje"], overdue=day.counts["atrasados"],
                meetings=day.counts["reunioes"], priorities=priorities, actions=day.rows[:8], invalid_dates=day.invalid_dates)


def overview_details(rows):
    """Bounded display data, never invented metrics or commercial decisions."""
    records = [dict(row) for row in rows]
    segments = Counter(row.get("segmento") or "Não informado" for row in records)
    opportunities = Counter(row.get("opportunity") or "Não informada" for row in records)
    ordered = lambda counts: sorted(counts.items(), key=lambda pair: (-pair[1], pair[0].casefold()))[:6]
    return {"segments": ordered(segments), "opportunities": ordered(opportunities),
            "recent": sorted(records, key=lambda row: row["id"], reverse=True)[:5]}


def empty_copy(context, has_rows):
    if has_rows:
        return ""
    return {"portfolio": "Nenhum lead encontrado. Ajuste os filtros ou importe uma planilha.",
            "day": "Nenhum lead para esta seleção. Seu dia está em dia.",
            "actions": "Nenhuma próxima ação disponível. Organize os retornos na Carteira."}[context]
