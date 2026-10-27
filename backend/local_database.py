"""Versioned SQLite bootstrap. Never called by import or by read-only fixtures."""
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
from uuid import uuid4

from core.database.schema import initialize_database


def initialize_local_database(path: Path):
    path = path.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    # Snapshot existing real data before any additive schema change.
    with closing(sqlite3.connect(path, timeout=10)) as c:
        c.execute('PRAGMA busy_timeout=10000')
        version = c.execute('PRAGMA user_version').fetchone()[0]
        if version > 1:
            raise RuntimeError('SQLite mais recente que esta versao da aplicacao.')
        tables = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if version == 1:
            return
        if tables:
            if 'leads' not in tables:
                raise RuntimeError('SQLite existente incompativel; nenhum dado alterado.')
            backup = path.parent / 'backups'
            backup.mkdir(exist_ok=True)
            target = backup / f'{path.stem}-pre-local-{uuid4().hex}.db'
            with closing(sqlite3.connect(target)) as destination:
                c.backup(destination)
                if destination.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
                    raise RuntimeError('Backup SQLite invalido; migracao cancelada.')
    # Reuse the additive, idempotent desktop migration before local extensions.
    initialize_database(path)
    with closing(sqlite3.connect(path, timeout=10)) as c, c:
        c.execute('PRAGMA journal_mode=WAL')
        c.execute('BEGIN IMMEDIATE')
        c.execute('CREATE TABLE IF NOT EXISTS local_migrations (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)')
        c.execute('CREATE TABLE IF NOT EXISTS local_settings (key TEXT PRIMARY KEY, value TEXT NOT NULL, updated_at TEXT NOT NULL)')
        c.execute('''CREATE TRIGGER IF NOT EXISTS local_lead_id_update BEFORE UPDATE OF id ON leads
            WHEN NEW.id != OLD.id BEGIN SELECT RAISE(ABORT, 'identificador imutavel'); END''')
        c.execute('''CREATE TRIGGER IF NOT EXISTS local_outreach_id_update BEFORE UPDATE OF id,lead_id ON outreach
            WHEN NEW.id != OLD.id OR NEW.lead_id != OLD.lead_id
            BEGIN SELECT RAISE(ABORT, 'identificador imutavel'); END''')
        # Add referential guards to legacy tables without rebuilding/deleting rows.
        # Existing orphans are preserved; new orphans and parent deletion are rejected.
        for table in ('lead_interactions', 'outreach', 'outreach_revisions', 'lead_contact_preferences', 'template_drafts'):
            for action in ('INSERT', 'UPDATE'):
                c.execute(f'''CREATE TRIGGER IF NOT EXISTS local_{table}_{action.lower()}
                    BEFORE {action} ON {table} WHEN NOT EXISTS (SELECT 1 FROM leads WHERE id=NEW.lead_id)
                    BEGIN SELECT RAISE(ABORT, 'lead inexistente'); END''')
            c.execute(f'''CREATE TRIGGER IF NOT EXISTS local_{table}_parent_delete
                BEFORE DELETE ON leads WHEN EXISTS (SELECT 1 FROM {table} WHERE lead_id=OLD.id)
                BEGIN SELECT RAISE(ABORT, 'lead possui historico'); END''')
        for action in ('INSERT', 'UPDATE'):
            c.execute(f'''CREATE TRIGGER IF NOT EXISTS local_revision_{action.lower()}
                BEFORE {action} ON outreach_revisions WHEN NOT EXISTS
                (SELECT 1 FROM outreach WHERE id=NEW.outreach_id AND lead_id=NEW.lead_id)
                BEGIN SELECT RAISE(ABORT, 'abordagem inexistente'); END''')
        c.execute('''CREATE TRIGGER IF NOT EXISTS local_outreach_parent_delete BEFORE DELETE ON outreach
            WHEN EXISTS (SELECT 1 FROM outreach_revisions WHERE outreach_id=OLD.id)
            BEGIN SELECT RAISE(ABORT, 'abordagem possui revisoes'); END''')
        c.execute('INSERT OR IGNORE INTO local_migrations VALUES (1,?)', (datetime.now(timezone.utc).isoformat(),))
        c.execute('PRAGMA user_version=1')
