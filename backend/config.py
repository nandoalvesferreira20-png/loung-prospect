"""Explicit local/SaaS configuration; never implicitly load credentials."""
from dataclasses import dataclass, field
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLOUD_MARKERS = ("VERCEL", "RENDER", "RAILWAY_ENVIRONMENT", "WEBSITE_INSTANCE_ID", "K_SERVICE", "FLY_APP_NAME", "AWS_EXECUTION_ENV")

@dataclass(frozen=True)
class Settings:
    database_path: Path
    writes_enabled: bool = False
    storage_backend: str = "sqlite"
    postgres_dsn: str = ""
    supabase_url: str = ""
    auth_audience: str = "authenticated"
    mode: str | None = None
    initialize_local: bool = False
    sales_ai_token: str = field(default="", repr=False)

    def validate(self):
        if self.sales_ai_token and (len(self.sales_ai_token) < 32 or not self.sales_ai_token.isascii() or any(c.isspace() for c in self.sales_ai_token)):
            raise ValueError("LOUNG_SALES_AI_TOKEN exige pelo menos 32 caracteres ASCII sem espacos.")
        mode = self.mode or ("local" if self.storage_backend == "sqlite" else "saas")
        if mode not in ("local", "saas"):
            raise ValueError("LOUNG_AUTH_MODE deve ser local ou saas")
        if (mode == "local") != (self.storage_backend == "sqlite"):
            raise ValueError("Modo local exige SQLite; modo saas exige PostgreSQL autenticado.")
        if mode == "local":
            if any(os.environ.get(key) for key in CLOUD_MARKERS):
                raise ValueError("Modo local sem login proibido em hospedagem publica.")
            if self.postgres_dsn:
                raise ValueError("Remova LOUNG_POSTGRES_DSN do ambiente local; use um arquivo separado para SaaS.")
            if not str(self.database_path).lower().endswith((".db", ".sqlite", ".sqlite3")) or str(self.database_path).startswith(("\\\\", "//")):
                raise ValueError("LOUNG_DATABASE_PATH deve ser um arquivo SQLite local.")
        return self

    @classmethod
    def from_environment(cls):
        mode = os.environ.get("LOUNG_AUTH_MODE", "local")
        value = Path(os.environ.get("LOUNG_DATABASE_PATH", str(ROOT / "data/loung_prospect.db")))
        return cls(value if value.is_absolute() else ROOT / value,
                   os.environ.get("LOUNG_ENABLE_WRITES", "1" if mode == "local" else "0") == "1",
                   os.environ.get("LOUNG_STORAGE_BACKEND", "sqlite" if mode == "local" else "postgres"),
                   os.environ.get("LOUNG_POSTGRES_DSN", ""),
                   os.environ.get("SUPABASE_URL", ""),
                   os.environ.get("SUPABASE_AUTH_AUDIENCE", "authenticated"), mode, mode == "local",
                   os.environ.get("LOUNG_SALES_AI_TOKEN", "")).validate()
