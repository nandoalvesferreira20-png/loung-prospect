"""Synthetic CRM fixture only: no production DB, no external integrations."""
from contextlib import asynccontextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from datetime import datetime, timedelta, timezone
import sqlite3
from backend.config import Settings
from backend.main import create_app as production_app
from core.database.schema import initialize_database
from backend.tests.test_sdr_api import Provider


def create_app():
    parent=Path(__file__).resolve().parents[1]/".phase24-ui"
    parent.mkdir(exist_ok=True)
    temporary=TemporaryDirectory(dir=parent)
    path=Path(temporary.name)/"synthetic.db"
    initialize_database(path)
    with sqlite3.connect(path) as connection:
        for index in range(1,13):
            connection.execute("INSERT INTO leads(empresa,segmento,cidade,telefone,status,created_at,updated_at) VALUES(?,?,'São Paulo','(11) 99999-1234','Novo','2026-01-01','2026-01-01')",(f"TESTE Novo {index:02}","Clínica odontológica" if index%2 else "Fotógrafos"))
        connection.execute("INSERT INTO leads(empresa,status,created_at,updated_at,observacoes,proximo_contato) VALUES('TESTE Legado','Reunião marcada','2026-01-01','2026-01-01','Observação anterior preservada',?)",((datetime.now(timezone.utc)-timedelta(days=2)).isoformat(),))
        connection.execute("INSERT INTO leads(empresa,status,created_at,updated_at) VALUES('TESTE Personalizado','Etapa especial','2026-01-01','2026-01-01')")
    def forbid():
        raise AssertionError("External prospecting forbidden")
    app=production_app(Settings(path,True),provider_factory=forbid,sdr_provider_factory=Provider)
    original=app.router.lifespan_context
    @asynccontextmanager
    async def lifespan(application):
        async with original(application): yield
        temporary.cleanup()
    app.router.lifespan_context=lifespan
    @app.get("/__test/metrics")
    def metrics():
        with sqlite3.connect(path) as connection:
            return {"signature":"phase24-synthetic-only","leads":connection.execute("SELECT count(*) FROM leads").fetchone()[0],"activities":connection.execute("SELECT count(*) FROM lead_interactions").fetchone()[0],"backups":len(list((path.parent/"backups").glob("*.db")))}
    @app.post("/__test/conflict/{lead_id}")
    def conflict(lead_id: int):
        with sqlite3.connect(path) as connection:
            connection.execute("UPDATE leads SET updated_at=? WHERE id=?",(datetime.now(timezone.utc).isoformat(),lead_id))
        return {"ok":True}
    @app.post("/__test/reset")
    def reset():
        with sqlite3.connect(path) as connection:
            connection.execute("DELETE FROM lead_interactions")
            connection.execute("DELETE FROM outreach")
            connection.execute("UPDATE leads SET status=CASE id WHEN 13 THEN 'Reunião marcada' WHEN 14 THEN 'Etapa especial' ELSE 'Novo' END,updated_at='2026-01-01',proximo_contato=NULL,proxima_acao=NULL,ultimo_contato=NULL")
            connection.execute("UPDATE leads SET proximo_contato=? WHERE id=13",((datetime.now(timezone.utc)-timedelta(days=2)).isoformat(),))
        return {"ok":True}
    return app
