"""Small lead repository. Filters use exact matches, no business taxonomy."""
from collections.abc import Mapping
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .connection import DEFAULT_DATABASE_PATH, connect_database
from .schema import initialize_database

FIELDS = (
    "empresa", "cidade", "segmento", "telefone", "whatsapp", "email", "site",
    "endereco", "avaliacao", "google_maps", "qualification_status",
    "qualification_score", "opportunity", "qualification_reasons",
    "qualification_evidence", "qualification_limitations", "rules_version",
    "analyzed_at", "responsavel", "status", "observacoes",
)
_UNSET = object()


class LeadNotFoundError(LookupError):
    pass


class LeadRepository:
    """Initialize explicitly on construction, then open/close per operation.

    create_lead returns the inserted integer ID; get_lead returns Row or None.
    Updates raise LeadNotFoundError. Omitted filters are unrestricted; explicit
    None matches SQL NULL. Timestamps are managed by the repository.
    """
    def __init__(self, path=DEFAULT_DATABASE_PATH):
        self.path = Path(path)
        initialize_database(self.path)

    def create_lead(self, data: Mapping[str, Any]) -> int:
        unknown = set(data) - set(FIELDS)
        if unknown:
            raise ValueError(f"Unknown lead fields: {sorted(unknown)}")
        now = datetime.now(timezone.utc).isoformat()
        values = [data.get(field, "Novo" if field == "status" else None) for field in FIELDS]
        # Column names and SQL structure are internal constants; all data is bound.
        columns = ", ".join((*FIELDS, "created_at", "updated_at"))
        placeholders = ", ".join("?" for _ in range(len(FIELDS) + 2))
        with closing(connect_database(self.path)) as connection:
            with connection:
                cursor = connection.execute(f"INSERT INTO leads ({columns}) VALUES ({placeholders})", [*values, now, now])
                return cursor.lastrowid

    def get_lead(self, lead_id):
        with closing(connect_database(self.path)) as connection:
            return connection.execute("SELECT * FROM leads WHERE id = ?", (lead_id,)).fetchone()

    def list_leads(self, *, status=_UNSET, segmento=_UNSET, responsavel=_UNSET, score_minimo=_UNSET):
        clauses, values = [], []
        for field, value in (("status", status), ("segmento", segmento), ("responsavel", responsavel)):
            if value is _UNSET:
                continue
            clauses.append(f"{field} IS NULL" if value is None else f"{field} = ?")
            if value is not None:
                values.append(value)
        if score_minimo is not _UNSET:
            clauses.append("qualification_score IS NULL" if score_minimo is None else "qualification_score >= ?")
            if score_minimo is not None:
                values.append(score_minimo)
        query = "SELECT * FROM leads"
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY qualification_score DESC, id ASC"
        with closing(connect_database(self.path)) as connection:
            return connection.execute(query, values).fetchall()

    def _update(self, lead_id, field, value):
        if field not in ("status", "observacoes", "responsavel"):
            raise ValueError("Unsupported update field")
        with closing(connect_database(self.path)) as connection:
            with connection:
                cursor = connection.execute(
                    f"UPDATE leads SET {field} = ?, updated_at = ? WHERE id = ?",
                    (value, datetime.now(timezone.utc).isoformat(), lead_id),
                )
                if cursor.rowcount == 0:
                    raise LeadNotFoundError(f"Lead not found: {lead_id}")

    def update_status(self, lead_id, status):
        self._update(lead_id, "status", status)

    def update_notes(self, lead_id, observacoes):
        self._update(lead_id, "observacoes", observacoes)

    def update_responsible(self, lead_id, responsavel):
        self._update(lead_id, "responsavel", responsavel)

    def count_leads(self) -> int:
        with closing(connect_database(self.path)) as connection:
            return connection.execute("SELECT COUNT(*) FROM leads").fetchone()[0]
