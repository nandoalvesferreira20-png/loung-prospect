"""Translate collector records without changing or enriching their contents."""

from collections.abc import Mapping
from typing import Any

from .models import ObservationStatus, QualificationInput


def adapt_record_to_qualification_input(
    record: Mapping[str, Any],
) -> QualificationInput:
    """Map current/legacy text fields; ignore unknown columns.

    Empty/whitespace-only strings and None become unavailable values. Nonempty
    strings are kept exactly as received; other known-field types are rejected.
    OBSERVED means present in the record, not independently verified (including
    WhatsApp). No absent value is classified as NOT_FOUND.

    The current Segmento key wins even when empty. Only an explicit lead_id is
    copied as an identifier; its stability is the caller's responsibility.
    """
    columns = {
        "company_name": "Empresa",
        "city": "Cidade",
        "segment": "Segmento" if "Segmento" in record else "Segmento pesquisado",
        "source_url": "Google Maps",
        "phone": "Telefone",
        "whatsapp": "WhatsApp",
        "website": "Site",
        "address": "Endereço",
        "rating": "Avaliação",
        "lead_id": "lead_id",
    }
    values = {}
    observations = {}
    for name, column in columns.items():
        value = record.get(column)
        if value is not None and not isinstance(value, str):
            raise TypeError(f"{column} must be a string or None")
        if value is not None and not value.strip():
            value = None
        values[name] = value
        observations[name] = (
            ObservationStatus.UNVERIFIED if value is None
            else ObservationStatus.OBSERVED
        )
    return QualificationInput(**values, observations=observations)
