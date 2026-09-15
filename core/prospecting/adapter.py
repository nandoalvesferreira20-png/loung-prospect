"""Explicit, pure mappings; commercial decisions belong to qualification."""

from core.providers.models import LeadCandidate
from core.validator import WEBSITE_VERIFICATION_KEY, PlacesWebsiteVerification
from core.qualification.models import QualificationResult
from core.qualification.rules import classify_priority
from core.qualification.serialization import (
    qualification_result_to_columns,
)


LEAD_FIELDS = {
    "empresa": "Empresa",
    "cidade": "Cidade",
    "segmento": "Segmento",
    "telefone": "Telefone",
    "whatsapp": "WhatsApp",
    "site": "Site",
    "endereco": "Endereço",
    "avaliacao": "Avaliação",
    "quantidade_avaliacoes": "Quantidade Avaliações",
    "google_maps": "Google Maps",
}


QUALIFICATION_FIELDS = {
    "qualification_status": "Qualification Status",
    "qualification_score": "Qualification Score",
    "opportunity": "Opportunity",
    "qualification_reasons": "Qualification Reasons",
    "qualification_evidence": "Qualification Evidence",
    "qualification_limitations": "Qualification Limitations",
    "rules_version": "Rules Version",
    "analyzed_at": "Analyzed At",
}


def candidate_to_record(
    candidate: LeadCandidate,
    *, website_evidence=False,
) -> dict:
    """Convert a provider LeadCandidate into the legacy qualification record."""

    record = {
        column: getattr(candidate, field)
        for field, column in LEAD_FIELDS.items()
    }

    # Preserve compatibility with legacy qualification/import flows.
    if record["Avaliação"] is not None:
        record["Avaliação"] = str(
            record["Avaliação"]
        )

    if record["Quantidade Avaliações"] is not None:
        record["Quantidade Avaliações"] = str(
            record["Quantidade Avaliações"]
        )

    record.update(
        provider=candidate.provider,
        provider_place_id=candidate.provider_place_id,
    )

    if website_evidence and candidate.provider == "google_places":
        record[WEBSITE_VERIFICATION_KEY] = PlacesWebsiteVerification(candidate.site)
    return record


def record_to_database(
    record: dict,
    result: QualificationResult,
) -> dict:
    """Convert a qualified record into the SQLite persistence format."""

    columns = qualification_result_to_columns(
        result
    )

    return {
        **{
            field: record.get(column)
            for field, column in LEAD_FIELDS.items()
        },
        **{
            field: columns[column]
            for field, column in QUALIFICATION_FIELDS.items()
        },
        "provider": record["provider"],
        "provider_place_id": record[
            "provider_place_id"
        ],
    }


def record_to_export(
    record: dict,
    result: QualificationResult,
) -> dict:
    """Build one human-readable Excel row for a processed lead."""

    qualification = qualification_result_to_columns(
        result
    )

    priority = ""

    if result.score is not None:
        priority = classify_priority(
            result.score
        ).value

    return {
        "Empresa": record.get("Empresa"),
        "Cidade": record.get("Cidade"),
        "Segmento": record.get("Segmento"),
        "Telefone": record.get("Telefone"),
        "WhatsApp": record.get("WhatsApp"),
        "Site": record.get("Site"),
        "Endereço": record.get("Endereço"),
        "Avaliação": record.get("Avaliação"),
        "Quantidade Avaliações": record.get(
            "Quantidade Avaliações"
        ),
        "Google Maps": record.get("Google Maps"),

        "Qualification Status": qualification.get(
            "Qualification Status"
        ),
        "Qualification Score": qualification.get(
            "Qualification Score"
        ),
        "Priority": priority,
        "Opportunity": qualification.get(
            "Opportunity"
        ),
        "Qualification Reasons": qualification.get(
            "Qualification Reasons"
        ),
        "Qualification Evidence": qualification.get(
            "Qualification Evidence"
        ),
        "Qualification Limitations": qualification.get(
            "Qualification Limitations"
        ),
        "Rules Version": qualification.get(
            "Rules Version"
        ),
        "Analyzed At": qualification.get(
            "Analyzed At"
        ),

        "Provider": record.get("provider"),
        "Provider Place ID": record.get(
            "provider_place_id"
        ),
    }
