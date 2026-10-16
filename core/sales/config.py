"""Single environment entry point for SDR credentials; never prints values."""
import os
from core.providers.environment import load_environment


def groq_settings(*, load=True):
    if load:
        load_environment()
    return dict(key=os.getenv("GROQ_API_KEY", ""), model=os.getenv("GROQ_MODEL", ""),
                timeout=os.getenv("GROQ_TIMEOUT", "60"))


def create_groq_provider(*, load=True):
    from .groq_provider import GroqSalesProvider
    return GroqSalesProvider(**groq_settings(load=load))
