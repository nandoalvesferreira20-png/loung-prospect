"""Provider-independent candidate contract."""
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class LeadCandidate:
    provider: str
    provider_place_id: str | None = None
    empresa: str | None = None
    cidade: str | None = None
    segmento: str | None = None
    telefone: str | None = None
    whatsapp: str | None = None
    site: str | None = None
    endereco: str | None = None
    avaliacao: float | None = None
    quantidade_avaliacoes: int | None = None
    google_maps: str | None = None
    latitude: float | None = None
    longitude: float | None = None


class LeadProvider(Protocol):
    def search(self, *, city: str, segment: str, max_results: int = 50) -> list[LeadCandidate]: ...
