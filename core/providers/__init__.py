"""Prospecting provider contracts. No automatic API calls."""
from .models import LeadCandidate, LeadProvider
from .google_places import GooglePlacesProvider

__all__ = ["LeadCandidate", "LeadProvider", "GooglePlacesProvider"]
