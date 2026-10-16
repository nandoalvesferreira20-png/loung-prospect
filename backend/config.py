"""Explicit process configuration; never load or modify desktop .env files."""
from dataclasses import dataclass
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Settings:
    database_path: Path
    writes_enabled: bool = False

    @classmethod
    def from_environment(cls):
        value = Path(os.environ.get("LOUNG_DATABASE_PATH", str(ROOT / "data/loung_prospect.db")))
        return cls(value if value.is_absolute() else ROOT / value,
                   os.environ.get("LOUNG_ENABLE_WRITES") == "1")
