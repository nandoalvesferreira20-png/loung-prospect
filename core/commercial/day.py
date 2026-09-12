"""Daily follow-up selection using existing repository filters and datetime."""
from dataclasses import dataclass
from datetime import date, datetime

from .values import TERMINAL_STATUSES


@dataclass
class DaySummary:
    rows: list
    counts: dict[str, int]
    invalid_dates: int = 0


def build_day(rows, reference: date, *, tz=None):
    """Reference is a local calendar day. tz=None uses the OS local timezone.

    Blocks overlap; the list is their deduplicated union. Terminal statuses are
    excluded from overdue only, per the requested definition of today's block.
    """
    counts = dict(atrasados=0, hoje=0, novos=0, reunioes=0, propostas=0)
    selected = []
    invalid_dates = 0
    for source in rows:
        row = dict(source)
        due = None
        if row.get("proximo_contato"):
            try:
                due = datetime.fromisoformat(row["proximo_contato"])
                if due.utcoffset() is None:
                    raise ValueError
                due = due.astimezone(tz)
            except (ValueError, TypeError):
                due = None
                invalid_dates += 1
        overdue = due is not None and due.date() < reference and row["status"] not in TERMINAL_STATUSES
        today = due is not None and due.date() == reference
        flags = dict(atrasados=overdue, hoje=today, novos=row["status"] == "Novo",
                     reunioes=row["status"] == "Reunião agendada", propostas=row["status"] == "Proposta enviada")
        for key, included in flags.items():
            counts[key] += int(included)
        if any(flags.values()):
            score = row.get("qualification_score")
            key = (0 if overdue else 1 if today else 2,
                   due.timestamp() if overdue or today else 0,
                   -(score if score is not None else -1), row["id"])
            selected.append((key, row))
    selected.sort(key=lambda item: item[0])
    return DaySummary([row for _, row in selected], counts, invalid_dates)


def get_my_day(repository, reference=None, *, responsavel="", tz=None):
    reference = reference or datetime.now(tz).date()
    filters = {"responsavel": responsavel} if responsavel else {}
    return build_day(repository.list_leads(**filters), reference, tz=tz)
