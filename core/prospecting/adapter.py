"""Explicit, pure mappings; commercial decisions belong to qualification."""
from core.providers.models import LeadCandidate
from core.qualification.models import QualificationResult
from core.qualification.serialization import qualification_result_to_columns

LEAD_FIELDS = {
    "empresa": "Empresa", "cidade": "Cidade", "segmento": "Segmento",
    "telefone": "Telefone", "whatsapp": "WhatsApp", "site": "Site",
    "endereco": "Endereço", "avaliacao": "Avaliação", "google_maps": "Google Maps",
}
QUALIFICATION_FIELDS = {
    "qualification_status": "Qualification Status", "qualification_score": "Qualification Score",
    "opportunity": "Opportunity", "qualification_reasons": "Qualification Reasons",
    "qualification_evidence": "Qualification Evidence", "qualification_limitations": "Qualification Limitations",
    "rules_version": "Rules Version", "analyzed_at": "Analyzed At",
}


def candidate_to_record(candidate: LeadCandidate) -> dict:
    record = {column: getattr(candidate, field) for field, column in LEAD_FIELDS.items()}
    # The existing qualification adapter expects text ratings.
    if record["Avaliação"] is not None:
        record["Avaliação"] = str(record["Avaliação"])
    record.update(provider=candidate.provider, provider_place_id=candidate.provider_place_id)
    return record


def record_to_database(record: dict, result: QualificationResult) -> dict:
    columns = qualification_result_to_columns(result)
    return {
        **{field: record.get(column) for field, column in LEAD_FIELDS.items()},
        **{field: columns[column] for field, column in QUALIFICATION_FIELDS.items()},
        "provider": record["provider"], "provider_place_id": record["provider_place_id"],
    }
