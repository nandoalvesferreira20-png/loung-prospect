"""SDR list presentation, no AI calls or writes while browsing."""
from contextlib import closing
from core.database.connection import connect_database
from core.sales.contact import blocked
from core.commercial.values import commercial_status


def effective_status(row):
    if blocked(row):
        return "Não contatar"
    return commercial_status(row["status"])


def list_sales_leads(repository, *, search="", segment="", status=""):
    with closing(connect_database(repository.path)) as connection:
        rows = [dict(row) for row in connection.execute("""SELECT l.*, o.status AS draft_status,
            o.mensagem AS draft_message FROM leads l LEFT JOIN outreach o ON o.id = (
                SELECT id FROM outreach WHERE lead_id=l.id AND status != 'CANCELADA'
                ORDER BY criado_em DESC, id DESC LIMIT 1)
            ORDER BY l.qualification_score DESC, l.id ASC""")]
    for row in rows:
        row["display_status"] = effective_status(row)
    return filter_sales_leads(rows, search=search, segment=segment, status=status)


def filter_sales_leads(rows, *, search="", segment="", status=""):
    segment = "" if segment == "Todos os segmentos" else segment
    status = "" if status == "Todas as etapas" else status
    return [row for row in rows if search.strip().casefold() in row["empresa"].casefold()
            and (not segment.strip() or segment.strip().casefold() == (row["segmento"] or "").strip().casefold())
            and (not status or commercial_status(status) == commercial_status(row["display_status"]))]


def sales_counts(rows):
    return {"leads": len(rows), "generated": sum(bool(r.get("draft_message")) for r in rows),
        "reviewed": sum(r.get("draft_status") in ("EDITADA", "APROVADA") for r in rows),
        "contacted": sum(bool(r.get("ultimo_contato")) or commercial_status(r["status"]) == "Contato realizado" for r in rows),
        "interested": sum(r["status"] == "Interessado" for r in rows),
        "pending": sum(r.get("draft_status") == "GERADA" for r in rows),
        "meetings": sum(commercial_status(r["status"]) == "Reunião agendada" for r in rows)}
