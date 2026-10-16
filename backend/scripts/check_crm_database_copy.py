"""Run commercial mutations exclusively on a disposable read-only-source snapshot."""
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory
import hashlib
import sqlite3
from fastapi.testclient import TestClient
from backend.config import Settings
from backend.main import create_app


def snapshot(connection):
    names=[r[0] for r in connection.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
    return {name:connection.execute('SELECT * FROM "'+name.replace('"','""')+'" ORDER BY rowid').fetchall() for name in names}


def main():
    source=Settings.from_environment().database_path.resolve()
    checksum=hashlib.sha256(source.read_bytes()).hexdigest()
    parent=Path(__file__).resolve().parents[1]/".phase24-copy"
    parent.mkdir(exist_ok=True)
    with TemporaryDirectory(dir=parent) as temporary:
        target=Path(temporary)/"snapshot.db"
        with closing(sqlite3.connect(source.as_uri()+"?mode=ro",uri=True)) as reader, closing(sqlite3.connect(target)) as writer:
            reader.backup(writer)
        with closing(sqlite3.connect(target)) as connection:
            before=snapshot(connection)
            schema=connection.execute("SELECT sql FROM sqlite_master ORDER BY name").fetchall()
            fields=[r[1] for r in connection.execute("PRAGMA table_info(leads)")]
        with TestClient(create_app(Settings(target,True))) as client:
            lead_id=before["leads"][0][0]
            def revision(): return client.get(f"/v1/crm/leads/{lead_id}").json()["lead"]["revision"]
            response=client.patch(f"/v1/leads/{lead_id}/stage",json={"stage":"Em conversa","revision":revision()})
            assert response.status_code == 200
            response=client.post(f"/v1/leads/{lead_id}/activities",json={"kind":"Observação","description":"TESTE SOMENTE NA COPIA","revision":revision()})
            assert response.status_code == 200
            response=client.post(f"/v1/leads/{lead_id}/followups",json={"dueAt":"2026-12-20T09:00:00-03:00","note":"Retorno na copia","revision":revision()})
            assert response.status_code == 200
            response=client.patch(f"/v1/followups/{lead_id}",json={"action":"complete","revision":revision()})
            assert response.status_code == 200
        with closing(sqlite3.connect(target)) as connection:
            after=snapshot(connection)
            assert schema == connection.execute("SELECT sql FROM sqlite_master ORDER BY name").fetchall()
            for table,rows in before.items():
                if table == "leads":
                    for previous,current in zip(rows,after[table],strict=True):
                        if previous[0] == lead_id:
                            assert all(previous[i] == current[i] for i,name in enumerate(fields) if name not in {"status","updated_at","proximo_contato","proxima_acao"})
                        else: assert previous == current
                elif table == "lead_interactions":
                    assert after[table][:len(rows)] == rows and len(after[table]) == len(rows)+4
                else: assert after[table] == rows
            assert connection.execute("PRAGMA quick_check").fetchone()[0] == "ok"
        backups=list((target.parent/"backups").glob("*.db"))
        assert len(backups) == 1
        with closing(sqlite3.connect(backups[0])) as connection:
            assert snapshot(connection) == before
    assert hashlib.sha256(source.read_bytes()).hexdigest() == checksum
    print(f"CRM: copia de {len(before['leads'])} leads validada; registros anteriores, schema e backup preservados. Banco original inalterado.")


if __name__ == "__main__": main()
