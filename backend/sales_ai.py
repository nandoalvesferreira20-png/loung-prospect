"""Local-only, read-only projection for controlled Sales AI exports."""
import secrets
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from .repository import ReadRepository


class SalesLead(BaseModel):
    lead_id: int
    nome: str
    nicho: str | None
    cidade: str | None
    site: str | None
    observacoes: str | None


class SalesPage(BaseModel):
    items: list[SalesLead]
    next_after_id: int | None


def create_router(repository: ReadRepository, token: str):
    router = APIRouter(prefix="/v1/integrations/sales-ai", tags=["sales-ai"])
    bearer = HTTPBearer(auto_error=False)

    def authenticate(credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]):
        if not token:
            raise HTTPException(503, "Integracao Sales AI desabilitada.")
        supplied = credentials.credentials if credentials else ""
        if not secrets.compare_digest(supplied.encode("utf-8"), token.encode("utf-8")):
            raise HTTPException(401, "Token de integracao invalido.", headers={"WWW-Authenticate": "Bearer"})

    @router.get("/leads", response_model=SalesPage, dependencies=[Depends(authenticate)])
    def leads(
        nicho: Annotated[str, Query(max_length=500)] = "",
        limit: Annotated[int, Query(ge=1, le=100)] = 50,
        after_id: Annotated[int, Query(ge=0, le=9223372036854775807)] = 0,
        lead_id: Annotated[list[int] | None, Query(max_length=100)] = None,
    ):
        if lead_id and any(value <= 0 or value > 9223372036854775807 for value in lead_id):
            raise HTTPException(422, "IDs devem ser inteiros positivos de 64 bits.")
        with repository.connect() as (connection, columns):
            # All identifiers below are server constants; values are bound parameters.
            mapping = {"id": "lead_id", "empresa": "nome", "segmento": "nicho",
                       "cidade": "cidade", "site": "site", "observacoes": "observacoes"}
            projection = ", ".join(
                f'"{source}" AS "{target}"' if source in columns else f'NULL AS "{target}"'
                for source, target in mapping.items()
            )
            clauses, values = ["id > ?"], [after_id]
            if nicho.strip():
                if "segmento" in columns:
                    clauses.append("segmento = ?")
                    values.append(nicho.strip())
                else:
                    clauses.append("0")
            if lead_id:
                clauses.append("id IN (" + ",".join("?" for _ in lead_id) + ")")
                values.extend(lead_id)
            rows = connection.execute(
                f'SELECT {projection} FROM leads WHERE {" AND ".join(clauses)} ORDER BY id ASC LIMIT ?',
                [*values, limit + 1],
            ).fetchall()
            items = [SalesLead(**dict(row)) for row in rows[:limit]]
            return SalesPage(items=items, next_after_id=items[-1].lead_id if len(rows) > limit else None)

    return router
