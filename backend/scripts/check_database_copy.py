"""Validate selected-write behavior on a temporary snapshot, never the source."""
from contextlib import closing
import hashlib
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
from uuid import uuid4

from backend.config import Settings
from backend.prospecting.storage import SelectionStore


def main():
    source = Settings.from_environment().database_path.resolve()
    before = hashlib.sha256(source.read_bytes()).hexdigest()
    parent = Path(__file__).resolve().parents[1] / ".phase22-copy"
    parent.mkdir(exist_ok=True)
    with TemporaryDirectory(dir=parent) as temporary:
        destination = Path(temporary) / "snapshot.db"
        with closing(sqlite3.connect(source.as_uri()+"?mode=ro",uri=True)) as reader, closing(sqlite3.connect(destination)) as writer:
            reader.backup(writer)
        with closing(sqlite3.connect(destination)) as connection:
            originals = connection.execute("SELECT * FROM leads ORDER BY id").fetchall()
            original_ids = {row[0] for row in originals}
        store = SelectionStore(destination, enabled=True)
        data = {"empresa":"TESTE TEMPORÁRIO FASE 2.2", "provider":"phase22-copy-test", "provider_place_id":uuid4().hex}
        assert store.save([data]) == {"inserted":1,"duplicates":0}
        assert store.save([data]) == {"inserted":0,"duplicates":1}
        with closing(sqlite3.connect(destination)) as connection:
            current = connection.execute("SELECT * FROM leads ORDER BY id").fetchall()
            assert [row for row in current if row[0] in original_ids] == originals
            assert len(current) == len(originals)+1
        backup = next((Path(temporary)/"backups").glob("*.db"))
        with closing(sqlite3.connect(backup)) as connection:
            assert connection.execute("SELECT COUNT(*) FROM leads").fetchone()[0] == len(originals)
    assert hashlib.sha256(source.read_bytes()).hexdigest() == before
    print(f"Cópia validada: {len(originals)} originais preservados; inserção, deduplicação e backup aprovados. Fonte inalterada.")


if __name__ == "__main__":
    main()
