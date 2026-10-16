"""Synthetic database server exclusively for local browser integration checks."""
from contextlib import asynccontextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
import sqlite3
from backend.config import Settings
from backend.main import create_app as production_app
from core.database.schema import initialize_database


def create_app():
    parent = Path(__file__).resolve().parents[1] / ".test-tmp"
    parent.mkdir(exist_ok=True)
    temporary = TemporaryDirectory(prefix="ui-", dir=parent)
    path = Path(temporary.name) / "synthetic.db"
    initialize_database(path)
    with sqlite3.connect(path) as connection:
        connection.executemany("INSERT INTO leads(empresa,segmento,status,telefone,cidade,qualification_score,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?)", [
            (f"Teste empresa {i:02}", "Clínica odontológica" if i == 1 else None,
             "Reunião marcada" if i == 1 else "Contatado" if i == 2 else "Novo",
             "(11) 99999-0000" if i == 1 else None, "São Paulo", 100-i,"2026-01-01","2026-01-01") for i in range(1,25)
        ])
    app = production_app(Settings(path))
    @asynccontextmanager
    async def lifespan(_app):
        yield
        temporary.cleanup()
    app.router.lifespan_context = lifespan
    return app
