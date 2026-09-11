"""Optional local .env loading, without replacing existing environment values."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def load_environment():
    env_file = ROOT / ".env"
    if env_file.is_file():
        from dotenv import load_dotenv
        load_dotenv(env_file, override=False, interpolate=False)
