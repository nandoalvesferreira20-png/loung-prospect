"""One explicit search followed by isolated qualification and atomic inserts."""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from time import monotonic

from core.database.lead_repository import LeadRepository
from core.providers.environment import load_environment
from core.providers.google_places import GooglePlacesProvider, GooglePlacesConfigurationError, GooglePlacesHTTPError
from core.qualification.models import QualificationResult, QualificationNote
from core.qualification.service import qualify_record
from .adapter import candidate_to_record, record_to_database


@dataclass
class ProspectingSummary:
    requested: int
    received: int = 0
    qualified: int = 0
    insufficient_data: int = 0
    qualification_errors: int = 0
    website_opportunities: int = 0
    inserted: int = 0
    duplicates: int = 0
    persistence_errors: int = 0
    requests_made: int = 0
    duration_seconds: float = 0.0
    cancelled: bool = False
    errors: list[str] = field(default_factory=list)


class ProspectingError(RuntimeError):
    def __init__(self, message, summary):
        super().__init__(message)
        self.summary = summary


def create_provider():
    load_environment()
    return GooglePlacesProvider()


def prospect(*, city, segment, limit=5, provider=None, repository=None, log=None, progress=None, cancel_event=None):
    if not isinstance(city, str) or not city.strip() or not isinstance(segment, str) or not segment.strip():
        raise ValueError("Informe cidade e segmento.")
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError("Quantidade deve ser um inteiro de 1 a 100.")
    summary = ProspectingSummary(requested=limit)
    started = monotonic()
    def cancelled():
        return cancel_event is not None and cancel_event.is_set()
    try:
        if cancelled():
            summary.cancelled = True
            return summary
        try:
            provider = provider if provider is not None else create_provider()
            if log:
                log("Consultando Google Places…")
            candidates = provider.search(city=city, segment=segment, max_results=limit)
        except Exception as error:
            if isinstance(error, GooglePlacesConfigurationError):
                message = "Chave ausente: configure GOOGLE_PLACES_API_KEY no ambiente ou .env."
            elif isinstance(error, GooglePlacesHTTPError):
                message = f"Google Places recusou a busca (HTTP {error.status})."
            else:
                message = "Falha na consulta Google Places. Confira conexão, configuração e quota."
            summary.errors.append(message)
            raise ProspectingError(message, summary) from None
        finally:
            summary.requests_made = provider.request_count if provider is not None else 0
        summary.received = len(candidates)
        if log:
            log(f"Encontrados: {summary.received}. Iniciando qualificação e persistência.")
        if cancelled():
            summary.cancelled = True
            return summary
        if not candidates:
            return summary
        try:
            repository = repository if repository is not None else LeadRepository()
        except Exception:
            message = "Não foi possível abrir o banco local."
            summary.errors.append(message)
            raise ProspectingError(message, summary) from None
        for index, candidate in enumerate(candidates, 1):
            if cancelled():
                summary.cancelled = True
                break
            record = candidate_to_record(candidate)
            try:
                result = qualify_record(record)
            except Exception:
                result = QualificationResult(status="error", analyzed_at=datetime.now(timezone.utc),
                    limitations=[QualificationNote("qualification_error", "Falha isolada na qualificação.")])
            status = result.status.value
            if status == "error":
                summary.qualification_errors += 1
                summary.errors.append(f"Lead {index}: falha de qualificação.")
            else:
                setattr(summary, status, getattr(summary, status) + 1)
            if result.opportunity == "website":
                summary.website_opportunities += 1
            try:
                inserted_id = repository.create_lead_if_new(record_to_database(record, result))
                if inserted_id is None:
                    summary.duplicates += 1
                else:
                    summary.inserted += 1
            except Exception:
                summary.persistence_errors += 1
                summary.errors.append(f"Lead {index}: falha de persistência.")
            if progress:
                progress(index, summary.received)
        if log:
            log(f"Finalizado: {summary.inserted} inseridos; {summary.duplicates} duplicados.")
        return summary
    finally:
        summary.duration_seconds = monotonic() - started
