"""SQLite read adapter. No schema initialization, writes or provider imports.

The desktop repository constructor performs migrations, so it is deliberately
not instantiated here. Only pure domain rules are shared with the desktop.
"""
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path
import sqlite3
import unicodedata

from core.commercial.day import build_day
from core.commercial.values import STATUSES, commercial_status
from core.sales.contact_routing import classify_contact
from .models import Lead, LeadPage, Overview, StageCount


class DatabaseUnavailable(Exception):
    pass


def fold(value):
    return "".join(c for c in unicodedata.normalize("NFKD", str(value or "")).casefold() if c.isalnum() and not unicodedata.combining(c))


class ReadRepository:
    def __init__(self, path: Path):
        self.path = path.resolve()

    @contextmanager
    def connect(self):
        connection = None
        try:
            connection = sqlite3.connect(self.path.as_uri() + "?mode=ro", uri=True, timeout=2)
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA query_only=ON")
            connection.create_function("commercial_status", 1, commercial_status, deterministic=True)
            connection.create_function("fold", 1, fold, deterministic=True)
            connection.execute("BEGIN")  # Consistent count/list/overview snapshot.
            columns = {row[1] for row in connection.execute("PRAGMA table_info(leads)")}
            if not {"id", "empresa", "status"}.issubset(columns):
                raise DatabaseUnavailable("Schema de leads incompatível.")
            yield connection, columns
        except (sqlite3.Error, OSError) as error:
            raise DatabaseUnavailable("Não foi possível consultar a base local.") from error
        finally:
            if connection is not None:
                connection.close()

    @staticmethod
    def source(connection, columns):
        fields = ["id", "empresa", "telefone", "cidade", "segmento", "site", "status", "qualification_score", "proximo_contato", "proxima_acao"]
        selected = [f'l."{name}"' if name in columns else f'NULL AS "{name}"' for name in fields]
        preference_columns = {row[1] for row in connection.execute("PRAGMA table_info(lead_contact_preferences)")}
        join = ""
        if {"lead_id", "contact_type"}.issubset(preference_columns):
            selected.append("p.contact_type AS contact_type")
            join = " LEFT JOIN lead_contact_preferences p ON p.lead_id=l.id"
        else:
            selected.append("NULL AS contact_type")
        return f"SELECT {', '.join(selected)} FROM leads l{join}"

    @staticmethod
    def lead(row):
        raw = dict(row)
        role = raw.get("contact_type")
        if role not in {"recepcao_equipe", "contato_direto", "indefinido"}:
            role = classify_contact(raw.get("segmento"))
        score = raw.get("qualification_score")
        try:
            score = int(score) if score is not None else None
        except (TypeError, ValueError):
            score = None
        return Lead(id=raw["id"], company=raw["empresa"], phone=raw.get("telefone"),
                    niche=raw.get("segmento"), website=raw.get("site"), location=raw.get("cidade"),
                    stage=commercial_status(raw.get("status")) or "Não informado",
                    originalStage=raw.get("status"), score=score,
                    contactRole={"recepcao_equipe":"reception", "contato_direto":"direct", "indefinido":"unknown"}[role],
                    nextContact=raw.get("proximo_contato"), nextAction=raw.get("proxima_acao"))

    def list_leads(self, *, q="", stage="", page=1, page_size=20):
        with self.connect() as (connection, columns):
            source = self.source(connection, columns)
            clauses, values = [], []
            if q:
                clauses.append("instr(fold(coalesce(empresa,'') || ' ' || coalesce(telefone,'') || ' ' || coalesce(segmento,'') || ' ' || coalesce(cidade,'')), ?) > 0" if fold(q) else "0")
                if fold(q):
                    values.append(fold(q))
            if stage:
                clauses.append("coalesce(NULLIF(commercial_status(status),''),'Não informado') = ?")
                values.append(commercial_status(stage))
            where = " WHERE " + " AND ".join(clauses) if clauses else ""
            total = connection.execute(f"SELECT COUNT(*) FROM ({source}){where}", values).fetchone()[0]
            rows = connection.execute(f"SELECT * FROM ({source}){where} ORDER BY CAST(qualification_score AS REAL) DESC, id ASC LIMIT ? OFFSET ?", [*values, page_size, (page-1)*page_size]).fetchall()
            available = {commercial_status(row[0]) or "Não informado" for row in connection.execute("SELECT DISTINCT status FROM leads")}
            stages = list(dict.fromkeys([*STATUSES, *sorted(available)]))
            return LeadPage(items=[self.lead(row) for row in rows], total=total, page=page, pageSize=page_size, stages=stages)

    def get_lead(self, lead_id):
        with self.connect() as (connection, columns):
            row = connection.execute(f"SELECT * FROM ({self.source(connection, columns)}) WHERE id=?", (lead_id,)).fetchone()
            return self.lead(row) if row is not None else None

    def overview(self, reference: date | None = None, *, tz=None):
        reference = reference or (datetime.now(tz).date() if tz else date.today())
        with self.connect() as (connection, columns):
            rows = [dict(row) for row in connection.execute(self.source(connection, columns))]
        # Keep desktop follow-up semantics and legacy meeting aliases intact.
        # Coerce legacy scores for sorting without mutating stored values.
        for row in rows:
            row["qualification_score"] = self.lead(row).score
        day = build_day(rows, reference, tz=tz)
        counts = {}
        for row in rows:
            stage = commercial_status(row["status"]) or "Não informado"
            counts[stage] = counts.get(stage, 0) + 1
        return Overview(total=len(rows), today=day.counts["hoje"], overdue=day.counts["atrasados"], meetings=day.counts["reunioes"],
                        referenceDate=reference.isoformat(), invalidDates=day.invalid_dates,
                        stageCounts=[StageCount(stage=stage,count=count) for stage,count in sorted(counts.items())],
                        actions=[self.lead(next(source for source in rows if source["id"] == row["id"])) for row in day.rows[:8]])
