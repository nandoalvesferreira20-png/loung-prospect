"""Commercial lead scoring rules.

Rules V3 separate two concepts:

1. Qualification score:
   commercial priority based on observable signals.

2. Opportunity:
   a specific opportunity supported by the current evidence.

A company may have a high commercial score even when no specific website
opportunity can be confirmed automatically.

Scores are priority indicators, never sale probabilities.
No action or contact is automatically authorized.
"""

from enum import Enum
from types import MappingProxyType

from core.diagnostics import trace

from .digital_presence import (
    DigitalPresenceType,
    classify_digital_presence,
)

from .models import (
    ObservationStatus,
    QualificationInput,
    QualificationNote,
    QualificationResult,
    QualificationStatus,
)


RULES_VERSION = "3.0.0"


WEIGHTS = MappingProxyType(
    {
        # Digital presence
        "website_not_found": 30,
        "social_media_only": 25,
        "third_party_presence": 20,
        "own_website": 5,

        # Contact
        "phone_observed": 20,
        "whatsapp_observed": 10,

        # Reputation
        "rating_4_plus": 10,
        "reviews_20_49": 5,
        "reviews_50_99": 10,
        "reviews_100_plus": 20,

        # Data completeness
        "address_observed": 5,
    }
)


class CommercialPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    GOOD = "good"
    HIGH = "high"


def classify_priority(score: int) -> CommercialPriority:
    """Convert score into an internal commercial priority bucket."""

    score = max(0, min(100, score))

    if score >= 70:
        return CommercialPriority.HIGH

    if score >= 50:
        return CommercialPriority.GOOD

    if score >= 30:
        return CommercialPriority.MEDIUM

    return CommercialPriority.LOW


def _parse_rating(value) -> float | None:
    """Safely interpret a rating from legacy or current sources."""

    if value is None:
        return None

    if isinstance(value, bool):
        return None

    if isinstance(value, str):
        value = value.strip()

        if not value:
            return None

        # Accept common Brazilian decimal representation.
        value = value.replace(",", ".")

    try:
        rating = float(value)
    except (TypeError, ValueError):
        return None

    if not 0 <= rating <= 5:
        return None

    return rating


def _parse_user_rating_count(value) -> int | None:
    """Safely interpret the number of reviews."""

    if value is None:
        return None

    if isinstance(value, bool):
        return None

    if isinstance(value, str):
        value = value.strip()

        if not value:
            return None

        # Be conservative: do not try to interpret arbitrary text.
        if not value.isdigit():
            return None

    try:
        count = int(value)
    except (TypeError, ValueError):
        return None

    if count < 0:
        return None

    return count


def evaluate_rules(
    lead: QualificationInput,
) -> QualificationResult:
    """Evaluate supplied observations without changing the input.

    No contact is performed or authorized by this function.
    """

    reasons: list[QualificationNote] = []
    evidence: list[QualificationNote] = []
    limitations: list[QualificationNote] = []

    score = 0

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def present(name: str) -> bool:
        value = getattr(lead, name)

        if value is None:
            return False

        if isinstance(value, str):
            return bool(value.strip())

        return True

    def observed(name: str) -> bool:
        return (
            present(name)
            and lead.observation_status(name)
            == ObservationStatus.OBSERVED
        )

    def note(
        code: str,
        text: str,
        name: str | None = None,
    ) -> QualificationNote:
        return QualificationNote(
            code=code,
            description=text,
            field_name=name,
            source_url=lead.source_url,
        )

    # ------------------------------------------------------------------
    # Identity / minimum context
    # ------------------------------------------------------------------

    identity_ready = True

    for name, label in (
        ("company_name", "Nome"),
        ("segment", "Segmento"),
    ):
        if observed(name):
            evidence.append(
                note(
                    f"{name}_observed",
                    f"{label} observado: {getattr(lead, name)}",
                    name,
                )
            )
        else:
            identity_ready = False

            limitations.append(
                note(
                    f"{name}_unavailable",
                    (
                        f"{label} preenchido e observado é necessário "
                        "para contextualizar a análise."
                    ),
                    name,
                )
            )

    # ------------------------------------------------------------------
    # Digital presence
    # ------------------------------------------------------------------

    website_state = lead.observation_status("website")

    presence = classify_digital_presence(
        lead.website,
        website_state,
    )

    trace(
        "DIGITAL_PRESENCE",
        company=lead.company_name,
        presence=presence,
    )

    presence_resolved = presence.presence_type in {
        DigitalPresenceType.NOT_FOUND,
        DigitalPresenceType.SOCIAL_MEDIA,
        DigitalPresenceType.THIRD_PARTY_PLATFORM,
        DigitalPresenceType.OWN_WEBSITE,
    }

    opportunity = "needs_review"

    # Website explicitly not found
    if presence.presence_type == DigitalPresenceType.NOT_FOUND:
        weight = WEIGHTS["website_not_found"]

        evidence.append(
            note(
                "website_not_found",
                (
                    "Website não identificado na fonte consultada. "
                    "Isso não comprova ausência no mundo real."
                ),
                "website",
            )
        )

        reasons.append(
            note(
                "website_not_found",
                (
                    "Website não identificado na fonte consultada; "
                    f"sinal comercial para revisão (+{weight})."
                ),
                "website",
            )
        )

        limitations.append(
            note(
                "website_absence_unconfirmed",
                (
                    "Não encontrar website na fonte consultada não "
                    "comprova que a empresa não possua outro site."
                ),
                "website",
            )
        )

        score += weight
        opportunity = "website"

    # Social media as digital presence
    elif (
        presence.presence_type
        == DigitalPresenceType.SOCIAL_MEDIA
    ):
        weight = WEIGHTS["social_media_only"]

        provider = presence.provider or "rede social"

        evidence.append(
            note(
                "social_media_presence",
                (
                    f"Presença observada em {provider}: "
                    f"{presence.url}. {presence.reason}"
                ),
                "website",
            )
        )

        reasons.append(
            note(
                "social_media_presence",
                (
                    "Presença digital observada em rede social, sem "
                    "website independente confirmado por esta evidência "
                    f"(+{weight})."
                ),
                "website",
            )
        )

        limitations.append(
            note(
                "independent_website_unconfirmed",
                (
                    "A presença observada em rede social não comprova "
                    "que a empresa não possua outro website."
                ),
                "website",
            )
        )

        score += weight
        opportunity = "website"

    # Third-party platform
    elif (
        presence.presence_type
        == DigitalPresenceType.THIRD_PARTY_PLATFORM
    ):
        weight = WEIGHTS["third_party_presence"]

        provider = presence.provider or "plataforma externa"

        evidence.append(
            note(
                "third_party_platform",
                (
                    f"Presença observada em {provider}: "
                    f"{presence.url}. {presence.reason}"
                ),
                "website",
            )
        )

        reasons.append(
            note(
                "third_party_platform",
                (
                    "Presença digital observada em plataforma externa, "
                    "sem website independente confirmado por esta "
                    f"evidência (+{weight})."
                ),
                "website",
            )
        )

        limitations.append(
            note(
                "independent_website_unconfirmed",
                (
                    "A presença observada em plataforma externa não "
                    "comprova que a empresa não possua outro website."
                ),
                "website",
            )
        )

        score += weight
        opportunity = "website"

    # Independent website
    elif (
        presence.presence_type
        == DigitalPresenceType.OWN_WEBSITE
    ):
        weight = WEIGHTS["own_website"]

        evidence.append(
            note(
                "own_website_observed",
                (
                    f"URL observada: {presence.url}. "
                    f"{presence.reason}"
                ),
                "website",
            )
        )

        reasons.append(
            note(
                "own_website_observed",
                (
                    "Website independente observado; a empresa continua "
                    "sendo um potencial lead comercial, mas a oportunidade "
                    "específica exige revisão "
                    f"(+{weight})."
                ),
                "website",
            )
        )

        limitations.append(
            note(
                "website_not_inspected",
                (
                    "Conteúdo, funcionamento, conversão e qualidade "
                    "do website não foram avaliados."
                ),
                "website",
            )
        )

        score += weight
        opportunity = "needs_review"

    # Unverified / error / inconsistent
    else:
        if (
            presence.presence_type
            == DigitalPresenceType.ERROR
        ):
            code = "website_error"
            text = (
                "A observação de website contém erro; "
                "é necessária revisão."
            )

        elif website_state in (
            ObservationStatus.NOT_FOUND,
            ObservationStatus.OBSERVED,
        ):
            code = "website_inconsistent"
            text = (
                f"{presence.reason} É necessária revisão."
            )

        else:
            code = "website_unverified"
            text = (
                "Website não verificado; nenhuma conclusão "
                "sobre sua existência ou qualidade."
            )

        limitations.append(
            note(
                code,
                text,
                "website",
            )
        )

    # ------------------------------------------------------------------
    # Contact signals
    # ------------------------------------------------------------------

    if observed("phone"):
        weight = WEIGHTS["phone_observed"]

        evidence.append(
            note(
                "phone_observed",
                f"Telefone observado: {lead.phone}",
                "phone",
            )
        )

        reasons.append(
            note(
                "phone_observed",
                (
                    "Telefone disponível como canal de contato "
                    f"(+{weight})."
                ),
                "phone",
            )
        )

        score += weight

    # WhatsApp only scores when actually OBSERVED.
    if observed("whatsapp"):
        weight = WEIGHTS["whatsapp_observed"]

        evidence.append(
            note(
                "whatsapp_observed",
                f"WhatsApp observado: {lead.whatsapp}",
                "whatsapp",
            )
        )

        reasons.append(
            note(
                "whatsapp_observed",
                (
                    "Canal de WhatsApp explicitamente observado "
                    f"(+{weight})."
                ),
                "whatsapp",
            )
        )

        score += weight

    elif present("whatsapp"):
        limitations.append(
            note(
                "whatsapp_unverified",
                (
                    "Existe valor informado para WhatsApp, mas ele não "
                    "foi confirmado como canal observado."
                ),
                "whatsapp",
            )
        )

    # ------------------------------------------------------------------
    # Reputation signals
    # ------------------------------------------------------------------

    parsed_rating = _parse_rating(lead.rating)

    if observed("rating") and parsed_rating is not None:
        evidence.append(
            note(
                "rating_observed",
                f"Avaliação observada: {parsed_rating:.1f}",
                "rating",
            )
        )

        if parsed_rating >= 4.0:
            weight = WEIGHTS["rating_4_plus"]

            reasons.append(
                note(
                    "rating_4_plus",
                    (
                        "Avaliação igual ou superior a 4,0 "
                        f"(+{weight})."
                    ),
                    "rating",
                )
            )

            score += weight

    elif present("rating") and parsed_rating is None:
        limitations.append(
            note(
                "rating_invalid",
                (
                    "O valor de avaliação recebido não pôde ser "
                    "interpretado com segurança."
                ),
                "rating",
            )
        )

    # ------------------------------------------------------------------
    # Review count
    # ------------------------------------------------------------------

    review_count = _parse_user_rating_count(
        lead.user_rating_count
    )

    if (
        observed("user_rating_count")
        and review_count is not None
    ):
        evidence.append(
            note(
                "user_rating_count_observed",
                (
                    f"Quantidade de avaliações observada: "
                    f"{review_count}"
                ),
                "user_rating_count",
            )
        )

        if review_count >= 100:
            code = "reviews_100_plus"

        elif review_count >= 50:
            code = "reviews_50_99"

        elif review_count >= 20:
            code = "reviews_20_49"

        else:
            code = None

        if code is not None:
            weight = WEIGHTS[code]

            reasons.append(
                note(
                    code,
                    (
                        f"Volume de avaliações observado: "
                        f"{review_count} (+{weight})."
                    ),
                    "user_rating_count",
                )
            )

            score += weight

    elif (
        present("user_rating_count")
        and review_count is None
    ):
        limitations.append(
            note(
                "user_rating_count_invalid",
                (
                    "A quantidade de avaliações recebida não pôde "
                    "ser interpretada com segurança."
                ),
                "user_rating_count",
            )
        )

    # ------------------------------------------------------------------
    # Address
    # ------------------------------------------------------------------

    if observed("address"):
        weight = WEIGHTS["address_observed"]

        evidence.append(
            note(
                "address_observed",
                f"Endereço observado: {lead.address}",
                "address",
            )
        )

        reasons.append(
            note(
                "address_observed",
                (
                    "Endereço disponível como sinal adicional de "
                    f"contexto comercial (+{weight})."
                ),
                "address",
            )
        )

        score += weight

    # ------------------------------------------------------------------
    # General limitations
    # ------------------------------------------------------------------

    if present("phone") and not observed("phone"):
        limitations.append(
            note(
                "phone_unverified",
                (
                    "Existe valor de telefone, mas ele não foi "
                    "confirmado como observado."
                ),
                "phone",
            )
        )

    limitations.append(
        note(
            "human_review_required",
            (
                "Resultado destinado à revisão humana; "
                "não autoriza contato automaticamente."
            ),
        )
    )

    # ------------------------------------------------------------------
    # Final result
    # ------------------------------------------------------------------

    score = max(
        0,
        min(
            100,
            score,
        ),
    )

    priority = classify_priority(score)

    # Keep priority visible without modifying QualificationResult schema.
    evidence.append(
        note(
            "commercial_priority",
            (
                f"Prioridade comercial derivada do score: "
                f"{priority.value}."
            ),
        )
    )

    sufficient = (
        identity_ready
        and presence_resolved
    )

    status = (
        QualificationStatus.QUALIFIED
        if sufficient
        else QualificationStatus.INSUFFICIENT_DATA
    )

    if not sufficient:
        opportunity = "needs_review"

    return QualificationResult(
        status=status,
        score=score,
        opportunity=opportunity,
        reasons=reasons,
        evidence=evidence,
        limitations=limitations,
        rules_version=RULES_VERSION,
    )