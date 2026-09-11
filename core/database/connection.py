"""Explicit local SQLite connections; importing does not create a database."""
from pathlib import Path
import sqlite3

DEFAULT_DATABASE_PATH = Path(__file__).resolve().parents[2] / "data" / "loung_prospect.db"


def connect_database(path: str | Path = DEFAULT_DATABASE_PATH) -> sqlite3.Connection:
    """Caller owns the connection and must close it."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    return connection
