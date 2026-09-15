"""One explicit search followed by isolated qualification, persistence and optional export."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from time import monotonic

import pandas as pd

from core.database.lead_repository import LeadRepository
from core.exporter import export_excel
from core.providers.environment import load_environment
from core.providers.google_places import (
    GooglePlacesConfigurationError,
    GooglePlacesHTTPError,
    GooglePlacesProvider,
    GooglePlacesSafetyLimitError,
    build_query,
)
from core.qualification.models import (
    QualificationNote,
    QualificationResult,
)
from core.qualification.rules import classify_priority
from core.qualification.service import qualify_record
from core.lead_filter import DEFAULT_MIN_SCORE, WebsiteStatus, classificar_status_site, accepted_columns, new_search_stats, meets_min_score
from .limits import MAX_CANDIDATES_SCANNED, ProspectingStopReason, STOP_MESSAGES
from core.providers.search_query import normalize_neighborhood
from core.lead_filter import record_presence, is_without_own_website
from core.qualification.digital_presence import DigitalPresenceType

from .adapter import (
    candidate_to_record,
    record_to_database,
    record_to_export,
)


@dataclass
class ProspectingSummary:
    requested: int
    received: int = 0

    qualified: int = 0
    insufficient_data: int = 0
    qualification_errors: int = 0

    # Commercial priority
    high_priority: int = 0
    good_priority: int = 0
    medium_priority: int = 0
    low_priority: int = 0

    # Opportunity analysis
    website_opportunities: int = 0
    needs_review: int = 0

    # Persistence
    inserted: int = 0
    duplicates: int = 0
    persistence_errors: int = 0

    # Excel export
    exported_rows: int = 0
    exported_file: str | None = None
    export_error: bool = False

    # Execution
    requests_made: int = 0
    duration_seconds: float = 0.0
    cancelled: bool = False
    stats: dict | None = None
    stop_reason: str | None = None
    stop_code: ProspectingStopReason | None = None
    pages_fetched: int = 0
    rejected_score: int = 0
    rejected_unverified: int = 0

    @property
    def target(self):
        return self.requested

    @property
    def accepted(self):
        return self.inserted

    @property
    def candidates_scanned(self):
        return self.stats["analisadas"] if self.stats is not None else self.received

    @property
    def rejected_with_website(self):
        return self.stats["com_site"] if self.stats is not None else 0

    errors: list[str] = field(
        default_factory=list
    )


class ProspectingError(RuntimeError):
    def __init__(
        self,
        message,
        summary,
    ):
        super().__init__(message)
        self.summary = summary


def create_provider():
    load_environment()
    return GooglePlacesProvider()


def prospect(
    *,
    city,
    segment,
    limit=5,
    provider=None,
    repository=None,
    log=None,
    progress=None,
    cancel_event=None,
    export_path=None,
    only_without_website=False,
    min_score=DEFAULT_MIN_SCORE,
    max_candidates_scanned=MAX_CANDIDATES_SCANNED,
    neighborhood=None,
):
    """
    Search, qualify and persist Google Places leads.

    When export_path is supplied, every processed lead is also exported
    to Excel, including leads already present in SQLite.

    The Excel export represents the current search result, while SQLite
    remains the persistent lead workspace.
    """

    if (
        not isinstance(city, str)
        or not city.strip()
        or not isinstance(segment, str)
        or not segment.strip()
    ):
        raise ValueError(
            "Informe cidade e segmento."
        )

    if (
        type(limit) is not int
        or not 1 <= limit <= 100
    ):
        raise ValueError(
            "Quantidade deve ser um inteiro de 1 a 100."
        )

    neighborhood = normalize_neighborhood(neighborhood)
    search_context = {"neighborhood": neighborhood} if neighborhood else {}
    if only_without_website and (type(min_score) is not int or not 0 <= min_score <= 100):
        raise ValueError("Score mínimo deve ser inteiro entre 0 e 100.")
    if only_without_website and (type(max_candidates_scanned) is not int or max_candidates_scanned < 1):
        raise ValueError("Limite de candidatos deve ser inteiro positivo.")
    summary = ProspectingSummary(
        requested=limit
    )
    if only_without_website:
        summary.stats = new_search_stats()

    started = monotonic()

    # Rows generated from this specific search.
    export_rows = []

    def cancelled():
        return (
            cancel_event is not None
            and cancel_event.is_set()
        )

    try:
        # --------------------------------------------------
        # Cancellation before search
        # --------------------------------------------------

        if cancelled():
            summary.cancelled = True
            return summary

        # --------------------------------------------------
        # Google Places search
        # --------------------------------------------------

        try:
            provider = (
                provider
                if provider is not None
                else create_provider()
            )

            if log:
                log(
                    f"Consultando Google Places: {build_query(city, segment, neighborhood)}…"
                )

            if only_without_website:
                candidates = provider.iter_search(city=city, segment=segment, max_results=None, should_stop=cancelled, **search_context)
            else:
                candidates = provider.search(city=city, segment=segment, max_results=limit, **search_context)

        except Exception as error:
            if only_without_website:
                summary.stop_code = ProspectingStopReason.PROVIDER_ERROR
            if isinstance(
                error,
                GooglePlacesConfigurationError,
            ):
                message = (
                    "Chave ausente: configure "
                    "GOOGLE_PLACES_API_KEY "
                    "no ambiente ou .env."
                )

            elif isinstance(
                error,
                GooglePlacesHTTPError,
            ):
                message = (
                    "Google Places recusou "
                    f"a busca (HTTP {error.status})."
                )

            else:
                message = (
                    "Falha na consulta Google Places. "
                    "Confira conexão, configuração "
                    "e quota."
                )

            summary.errors.append(
                message
            )

            raise ProspectingError(
                message,
                summary,
            ) from None

        finally:
            summary.requests_made = (
                provider.request_count
                if provider is not None
                else 0
            )

        if not only_without_website:
            summary.received = len(candidates)

        if log:
            log(
                f"Encontrados: {summary.received}. "
                "Iniciando qualificação e persistência."
            )

        # --------------------------------------------------
        # Post-search cancellation
        # --------------------------------------------------

        if cancelled():
            summary.cancelled = True
            return summary

        if not candidates:
            return summary

        # --------------------------------------------------
        # SQLite repository
        # --------------------------------------------------

        try:
            repository = (
                repository
                if repository is not None
                else LeadRepository()
            )

        except Exception:
            message = (
                "Não foi possível abrir "
                "o banco local."
            )

            summary.errors.append(
                message
            )

            raise ProspectingError(
                message,
                summary,
            ) from None

        # --------------------------------------------------
        # Lead processing
        # --------------------------------------------------

        seen_ids, seen_companies = set(), set()
        def safe_candidates():
            count = 0
            page_number = 0
            def page_log():
                if log and page_number:
                    log(f"Página {page_number} | Analisados {summary.received} | Aceitos {summary.inserted}/{limit} | Com site {summary.rejected_with_website} | Duplicados {summary.duplicates}")
            try:
                iterator = iter(candidates)
                while not cancelled():
                    if count >= max_candidates_scanned:
                        summary.stop_code = ProspectingStopReason.SAFETY_LIMIT_REACHED
                        return
                    try:
                        candidate = next(iterator)
                    except StopIteration:
                        return
                    current_page = getattr(provider, "pages_fetched", 0)
                    if current_page != page_number:
                        page_log()
                        page_number = current_page
                    count += 1
                    yield candidate
            except GooglePlacesSafetyLimitError:
                summary.stop_code = ProspectingStopReason.SAFETY_LIMIT_REACHED
            except Exception:
                summary.stop_code = ProspectingStopReason.PROVIDER_ERROR
                summary.errors.append(STOP_MESSAGES[summary.stop_code])
            finally:
                page_log()

        for index, candidate in enumerate(
            safe_candidates() if only_without_website else candidates,
            1,
        ):
            if cancelled():
                summary.cancelled = True
                break

            record = candidate_to_record(
                candidate, website_evidence=only_without_website,
            )
            if only_without_website:
                summary.received += 1
                stats = summary.stats
                stats["analisadas"] += 1
                identity = (candidate.empresa, candidate.endereco) if candidate.empresa and candidate.endereco else None
                if (candidate.provider_place_id and candidate.provider_place_id in seen_ids) or (identity is not None and identity in seen_companies):
                    stats["duplicadas"] += 1
                    stats["descartadas"] += 1
                    summary.duplicates += 1
                    continue
                if candidate.provider_place_id:
                    seen_ids.add(candidate.provider_place_id)
                if identity is not None:
                    seen_companies.add(identity)
                presence = record_presence(record)
                if not is_without_own_website(presence):
                    if presence.presence_type == DigitalPresenceType.OWN_WEBSITE:
                        stats["com_site"] += 1
                    else:
                        summary.rejected_unverified += 1
                    stats["descartadas"] += 1
                    continue
                stats["sem_site"] += 1

            # ----------------------------------------------
            # Qualification
            # ----------------------------------------------

            try:
                if cancelled():
                    summary.cancelled = True
                    break
                result = qualify_record(
                    record
                )

            except Exception:
                result = QualificationResult(
                    status="error",
                    analyzed_at=datetime.now(
                        timezone.utc
                    ),
                    limitations=[
                        QualificationNote(
                            "qualification_error",
                            (
                                "Falha isolada "
                                "na qualificação."
                            ),
                        )
                    ],
                )

            status = result.status.value
            if only_without_website and not meets_min_score(result, min_score):
                summary.stats["descartadas"] += 1
                if status == "qualified" and result.score is not None:
                    summary.rejected_score += 1
                else:
                    summary.rejected_unverified += 1
                if status == "error":
                    summary.qualification_errors += 1
                continue

            if status == "error":
                summary.qualification_errors += 1

                summary.errors.append(
                    f"Lead {index}: "
                    "falha de qualificação."
                )

            else:
                setattr(
                    summary,
                    status,
                    getattr(
                        summary,
                        status,
                    )
                    + 1,
                )

            # ----------------------------------------------
            # Opportunity counters
            # ----------------------------------------------

            if result.opportunity == "website":
                summary.website_opportunities += 1

            elif result.opportunity == "needs_review":
                summary.needs_review += 1

            # ----------------------------------------------
            # Commercial priority counters
            # ----------------------------------------------

            if result.score is not None:
                priority = classify_priority(
                    result.score
                )

                if priority.value == "high":
                    summary.high_priority += 1

                elif priority.value == "good":
                    summary.good_priority += 1

                elif priority.value == "medium":
                    summary.medium_priority += 1

                elif priority.value == "low":
                    summary.low_priority += 1

            # ----------------------------------------------
            # Excel row
            #
            # Important:
            # append BEFORE SQLite dedupe.
            #
            # The Excel represents THIS SEARCH, therefore
            # duplicates already stored in SQLite still
            # belong in the exported spreadsheet.
            # ----------------------------------------------

            export_rows.append(
                record_to_export(
                    record,
                    result,
                )
            )
            if only_without_website:
                export_rows[-1].update(accepted_columns(result, presence))

            # ----------------------------------------------
            # SQLite persistence
            # ----------------------------------------------

            try:
                if cancelled():
                    summary.cancelled = True
                    export_rows.pop()
                    break
                inserted_id = (
                    repository.create_lead_if_new(
                        record_to_database(
                            record,
                            result,
                        )
                    )
                )

                if inserted_id is None:
                    summary.duplicates += 1
                    if only_without_website:
                        summary.stats["duplicadas"] += 1
                        summary.stats["descartadas"] += 1
                        export_rows.pop()
                        continue

                else:
                    summary.inserted += 1

            except Exception:
                summary.persistence_errors += 1

                summary.errors.append(
                    f"Lead {index}: "
                    "falha de persistência."
                )
                if only_without_website:
                    summary.stats["descartadas"] += 1
                    export_rows.pop()
                    continue

            if only_without_website:
                summary.stats["qualificadas"] += 1

            if progress:
                progress(
                    summary.inserted if only_without_website else index,
                    limit if only_without_website else summary.received,
                )
            if only_without_website and summary.inserted >= limit:
                break

        # --------------------------------------------------
        # Excel export
        # --------------------------------------------------

        if (
            export_path is not None
            and export_rows
        ):
            try:
                output_path = Path(
                    export_path
                )

                dataframe = pd.DataFrame(
                    export_rows
                )

                saved_path = export_excel(
                    dataframe,
                    output_path,
                    log=log if log else print,
                )

                summary.exported_rows = len(
                    export_rows
                )

                summary.exported_file = str(
                    saved_path.resolve()
                )

                if log:
                    log(
                        f"Excel exportado: "
                        f"{summary.exported_rows} leads."
                    )

            except Exception:
                summary.export_error = True

                summary.errors.append(
                    "Falha ao exportar a planilha Excel."
                )

                if log:
                    log(
                        "Falha ao exportar a planilha Excel."
                    )

        # --------------------------------------------------
        # Final log
        # --------------------------------------------------

        if log:
            log(
                f"Finalizado: "
                f"{summary.inserted} inseridos; "
                f"{summary.duplicates} duplicados."
            )

        return summary

    finally:
        if only_without_website:
            summary.requests_made = provider.request_count if provider is not None else 0
            summary.pages_fetched = getattr(provider, "pages_fetched", 0) if provider is not None else 0
            summary.cancelled = summary.cancelled or cancelled()
            summary.stop_code = (ProspectingStopReason.CANCELLED if summary.cancelled else
                ProspectingStopReason.TARGET_REACHED if summary.inserted >= limit else summary.stop_code or
                ProspectingStopReason.SOURCE_EXHAUSTED)
            summary.stop_reason = STOP_MESSAGES[summary.stop_code]
            if log:
                log(f"Meta {limit} | Aceitos {summary.inserted} | {summary.stats} | {summary.stop_reason}")
        summary.duration_seconds = (
            monotonic()
            - started
        )
