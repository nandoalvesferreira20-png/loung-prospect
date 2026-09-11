"""Local persistence, initialized only through explicit calls."""
from .connection import connect_database
from .schema import initialize_database
from .lead_repository import LeadRepository, LeadNotFoundError

__all__ = ["connect_database", "initialize_database", "LeadRepository", "LeadNotFoundError"]
