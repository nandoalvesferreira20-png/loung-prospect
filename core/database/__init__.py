"""Local persistence, initialized only through explicit calls."""
from .connection import connect_database
from .schema import initialize_database
from .lead_repository import LeadRepository, LeadNotFoundError
from .interaction_repository import InteractionRepository

__all__ = ["connect_database", "initialize_database", "LeadRepository", "LeadNotFoundError", "InteractionRepository"]
