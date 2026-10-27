"""Explicit selected-only insertion. Never calls initialize_database."""
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
from threading import RLock
from uuid import uuid4

from core.database.lead_repository import FIELDS, LeadRepository


class StorageError(Exception):
    pass


class SelectionStore:
    def __init__(self, path: Path, enabled=False):
        self.path = path.resolve()
        self.enabled = enabled
        self.lock = RLock()
        self.backed_up = False

    def connect(self, mode="ro"):
        connection = sqlite3.connect(self.path.as_uri()+f"?mode={mode}", uri=True, timeout=5)
        try:
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA busy_timeout=5000")
            connection.execute("PRAGMA foreign_keys=ON")
            columns = {row[1] for row in connection.execute("PRAGMA table_info(leads)")}
            if not {*FIELDS, "id", "created_at", "updated_at"}.issubset(columns):
                raise StorageError("Schema incompatível com importação. Atualize pelo desktop; a API não executa migrações.")
            if mode == "ro":
                connection.execute("PRAGMA query_only=ON")
            return connection
        except Exception:
            connection.close()
            raise

    def existing(self, rows):
        try:
            with closing(self.connect()) as connection:
                connection.execute("BEGIN")
                return [LeadRepository.find_existing(connection, row) is not None for row in rows]
        except sqlite3.Error:
            raise StorageError("Base indisponível ou ocupada. Tente novamente.") from None

    def _backup(self):
        directory = self.path.parent / "backups"
        directory.mkdir(exist_ok=True)
        target = directory / f"{self.path.stem}-pre-web-{datetime.now(timezone.utc):%Y%m%dT%H%M%S}-{uuid4().hex}.db"
        # A separate read connection sees committed data while the writer holds
        # BEGIN IMMEDIATE, preventing desktop writes during this snapshot.
        with closing(self.connect()) as source, closing(sqlite3.connect(target)) as destination:
            source.backup(destination)
            if destination.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                raise StorageError("Não foi possível validar o backup. Nenhum lead foi salvo.")

    def save(self, rows):
        if not self.enabled:
            raise StorageError("Gravação desabilitada. Configure LOUNG_ENABLE_WRITES=1 no backend após validar a cópia de teste.")
        try:
            with self.lock:
                pending_backup = False
                with closing(self.connect("rw")) as connection, connection:
                    connection.execute("BEGIN IMMEDIATE")
                    inserted, duplicates = 0, 0
                    for row in rows:
                        if not isinstance(row.get("empresa"), str) or not row["empresa"].strip():
                            raise StorageError("Resultado sem nome de empresa válido.")
                        if LeadRepository.find_existing(connection, row) is not None:
                            duplicates += 1
                            continue
                        if not self.backed_up and not pending_backup:
                            self._backup()
                            pending_backup = True
                        LeadRepository._insert(connection, row)
                        inserted += 1
                # Only mark the first-write backup after a successful commit.
                self.backed_up = self.backed_up or pending_backup
                return {"inserted":inserted, "duplicates":duplicates}
        except (sqlite3.Error, OSError):
            raise StorageError("Não foi possível salvar. A transação foi revertida; verifique bloqueios, schema e permissão de backup.") from None
