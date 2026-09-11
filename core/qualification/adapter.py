"""Translate collector records without changing or enriching their contents."""

from collections.abc import Mapping
from typing import Any

from core.validator import website_observation

from .models import ObservationStatus, QualificationInput


TEXT_FIELDS = {
    "company_name",
    "city",
    "segment",
    "source_url",
    "phone",
    "whatsapp",
    "website",
    "address",
    "lead_id",
}


NUMERIC_COMPATIBLE_FIELDS = {
    "rating",
    "user_rating_count",
}


def _normalize_text_value(
    column: str,
    value: Any,
) -> str | None:
    if value is None:
        return None

    if not isinstance(value, str):
        raise TypeError(
            f"{column} must be a string or None"
        )

    if not value.strip():
        return None

    return value


def _normalize_rating_value(
    column: str,
    value: Any,
) -> str | int | float | None:
    if value is None:
        return None

    if isinstance(value, bool):
        raise TypeError(
            f"{column} must be text, number or None"
        )

    if isinstance(
        value,
        (str, int, float),
    ):
        if (
            isinstance(value, str)
            and not value.strip()
        ):
            return None

        return value

    raise TypeError(
        f"{column} must be text, number or None"
    )


def _normalize_review_count_value(
    column: str,
    value: Any,
) -> str | int | None:
    if value is None:
        return None

    if isinstance(value, bool):
        raise TypeError(
            f"{column} must be text, integer or None"
        )

    if isinstance(
        value,
        (str, int),
    ):
        if (
            isinstance(value, str)
            and not value.strip()
        ):
            return None

        return value

    raise TypeError(
        f"{column} must be text, integer or None"
    )


def adapt_record_to_qualification_input(
    record: Mapping[str, Any],
) -> QualificationInput:
    """Map current/legacy fields into QualificationInput.

    Empty text and None become unavailable values.

    Textual collector fields remain strict strings.

    Rating and review count may come from Google Places as numeric values
    or from legacy/imported sources as strings.

    OBSERVED means present in the record, not independently verified.

    Website NOT_FOUND still requires explicit verification metadata;
    an empty website alone remains UNVERIFIED.
    """

    columns = {
        "company_name": "Empresa",
        "city": "Cidade",
        "segment": (
            "Segmento"
            if "Segmento" in record
            else "Segmento pesquisado"
        ),
        "source_url": "Google Maps",
        "phone": "Telefone",
        "whatsapp": "WhatsApp",
        "website": "Site",
        "address": "Endereço",
        "rating": "Avaliação",
        "user_rating_count": "Quantidade Avaliações",
        "lead_id": "lead_id",
    }

    values = {}
    observations = {}

    for name, column in columns.items():
        raw_value = record.get(column)

        if name in TEXT_FIELDS:
            value = _normalize_text_value(
                column,
                raw_value,
            )

        elif name == "rating":
            value = _normalize_rating_value(
                column,
                raw_value,
            )

        elif name == "user_rating_count":
            value = _normalize_review_count_value(
                column,
                raw_value,
            )

        else:
            raise RuntimeError(
                f"Unsupported qualification field: {name}"
            )

        values[name] = value

        observations[name] = (
            ObservationStatus.UNVERIFIED
            if value is None
            else ObservationStatus.OBSERVED
        )

    # Website reliability still comes from the explicit website
    # verification/provenance layer, not merely from the field value.
    observations["website"] = website_observation(
        record
    )

    return QualificationInput(
        **values,
        observations=observations,
    )