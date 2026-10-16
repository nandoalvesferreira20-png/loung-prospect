"""Exercise SDR persistence on a temporary SQLite snapshot, never on the source."""
from contextlib import closing
import hashlib
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
from uuid import uuid4
from fastapi.testclient import TestClient
from backend.config import Settings
from backend.main import create_app
from backend.tests.test_sdr_api import Provider


def contents(connection):
    names = [r[0] for r in connection.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
    return {name: connection.execute('SELECT * FROM "' + name.replace('"', '""') + '" ORDER BY rowid').fetchall() for name in names}


def main():
    source = Settings.from_environment().database_path.resolve()
    before = hashlib.sha256(source.read_bytes()).hexdigest()
    parent = Path(__file__).resolve().parents[1] / ".phase23-copy"
    parent.mkdir(exist_ok=True)
    with TemporaryDirectory(dir=parent) as temporary:
        target = Path(temporary) / "snapshot.db"
        with closing(sqlite3.connect(source.as_uri() + "?mode=ro", uri=True)) as reader, closing(sqlite3.connect(target)) as writer:
            reader.backup(writer)
        with closing(sqlite3.connect(target)) as connection:
            originals = contents(connection)
            schema = connection.execute("SELECT sql FROM sqlite_master ORDER BY name").fetchall()
        with TestClient(create_app(Settings(target, True), sdr_provider_factory=Provider)) as client:
            candidates = client.get("/v1/leads?pageSize=100").json()["items"]
            lead = next(item for item in candidates if not client.get(f"/v1/sdr/leads/{item['id']}").json()["blocked"])
            lead_id = lead["id"]
            history = client.get(f"/v1/sdr/history/{lead_id}").json()
            assert history["available"], "History schema unavailable; no migration performed"
            draft = client.post("/v1/sdr/generate", json={"leadId":lead_id,"requestId":str(uuid4())}).json()
            body = {"draftId":draft["draftId"],"message":"TESTE TEMPORARIO: revisao apenas na copia.","status":"APROVADA"}
            saved = client.post("/v1/sdr/history", json=body)
            assert saved.status_code == 200, "Snapshot save failed"
            saved_id = saved.json()["id"]
        with closing(sqlite3.connect(target)) as connection:
            current = contents(connection)
            assert connection.execute("SELECT sql FROM sqlite_master ORDER BY name").fetchall() == schema
            for name, rows in originals.items():
                if name == "outreach":
                    assert [row for row in current[name] if row[0] != saved_id] == rows
                else:
                    assert current[name] == rows, f"Unexpected mutation: {name}"
        assert len(list((target.parent / "backups").glob("*.db"))) == 1
    assert hashlib.sha256(source.read_bytes()).hexdigest() == before
    print(f"SDR: copia de {len(originals['leads'])} leads validada; schema e todos os registros anteriores preservados. Banco fonte inalterado.")


if __name__ == "__main__":
    main()
