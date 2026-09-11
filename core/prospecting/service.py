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
)
from core.qualification.models import (
    QualificationNote,
    QualificationResult,
)
from core.qualification.rules import classify_priority
from core.qualification.service import qualify_record

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

    summary = ProspectingSummary(
        requested=limit
    )

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
                    "Consultando Google Places…"
                )

            candidates = provider.search(
                city=city,
                segment=segment,
                max_results=limit,
            )

        except Exception as error:
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

        summary.received = len(
            candidates
        )

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

        for index, candidate in enumerate(
            candidates,
            1,
        ):
            if cancelled():
                summary.cancelled = True
                break

            record = candidate_to_record(
                candidate
            )

            # ----------------------------------------------
            # Qualification
            # ----------------------------------------------

            try:
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

            # ----------------------------------------------
            # SQLite persistence
            # ----------------------------------------------

            try:
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

                else:
                    summary.inserted += 1

            except Exception:
                summary.persistence_errors += 1

                summary.errors.append(
                    f"Lead {index}: "
                    "falha de persistência."
                )

            if progress:
                progress(
                    index,
                    summary.received,
                )

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
        summary.duration_seconds = (
            monotonic()
            - started
        )