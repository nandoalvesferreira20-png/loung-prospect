"""Explicit offline browser-test fixture. Own temporary DB and simulated Groq."""
from contextlib import asynccontextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from time import sleep
import sqlite3
from backend.config import Settings
from backend.main import create_app as production_app
from backend.tests.test_sdr_api import Provider
from core.database.schema import initialize_database


def create_app():
    parent = Path(__file__).resolve().parents[1] / ".phase23-ui"
    parent.mkdir(exist_ok=True)
    temporary = TemporaryDirectory(dir=parent)
    path = Path(temporary.name) / "synthetic.db"
    initialize_database(path)
    with sqlite3.connect(path) as connection:
        connection.executemany("INSERT INTO leads (empresa,segmento,telefone,status,created_at,updated_at) VALUES (?,?,?,'Novo','2026-01-01','2026-01-01')", [
            ("TESTE Clínica Árvore", "Clínica odontológica", "(11) 99999-1234"),
            ("TESTE Fotógrafo", "Fotógrafos", "+351 912 345 678"),
            ("TESTE Sem telefone", "Desconhecido", None),
            ("TESTE Telefone inválido", None, "1234"),
            ("TESTE Recusa", "Restaurante", "(11) 99999-0000"),
        ])
        connection.execute("UPDATE leads SET whatsapp_consent='Recusado' WHERE id=5")
    provider = Provider()
    original_generate = provider.generate
    def generate(**kwargs):
        sleep(0.4)
        if kwargs["evidence"].get("instrucao_adicional") == "falha simulada":
            raise TimeoutError("synthetic-sensitive-value")
        return original_generate(**kwargs)
    provider.generate = generate
    app = production_app(Settings(path, True), sdr_provider_factory=lambda: provider)
    original_lifespan = app.router.lifespan_context
    @asynccontextmanager
    async def lifespan(application):
        async with original_lifespan(application):
            yield
        temporary.cleanup()
    app.router.lifespan_context = lifespan
    @app.get("/__test/metrics")
    def metrics():
        return {"signature": "phase23-synthetic-only", "calls": len(provider.calls),
                "backups": len(list((path.parent / "backups").glob("*.db")))}
    return app
