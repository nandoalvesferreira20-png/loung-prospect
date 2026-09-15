"""Selection policy for a Maps search; qualification remains in its service."""
from enum import Enum

from core.validator import website_observation
from core.qualification.models import ObservationStatus
from core.qualification.rules import classify_priority
from core.qualification.digital_presence import classify_digital_presence, DigitalPresenceType

DEFAULT_MIN_SCORE = 60


def new_search_stats():
    return dict(analisadas=0, com_site=0, sem_site=0, duplicadas=0, descartadas=0, qualificadas=0)


def meets_min_score(result, minimum):
    return result.status == "qualified" and result.score is not None and result.score >= minimum


class WebsiteStatus(str, Enum):
    PRESENT = "POSSUI_SITE"
    NOT_FOUND_IN_GOOGLE = "SEM_SITE_NO_GOOGLE"
    CONFIRMED_ABSENT = "SEM_SITE_CONFIRMADO"  # reserved; never produced here
    UNVERIFIED = "NAO_VERIFICADO"
    ERROR = "ERRO_VERIFICACAO"


def possui_site(empresa):
    """A supplied link counts as present, including generic/social links.

    False means no usable field value, not proof of website absence.
    """
    value = empresa.get("Site", empresa.get("site"))
    return isinstance(value, str) and value.strip().casefold() not in {
        "", "none", "null", "nan", "n/a", "não disponível", "-", "—",
    }


def classificar_status_site(empresa):
    if possui_site(empresa):
        return WebsiteStatus.PRESENT
    observation = website_observation(empresa)
    return {
        ObservationStatus.NOT_FOUND: WebsiteStatus.NOT_FOUND_IN_GOOGLE,
        ObservationStatus.ERROR: WebsiteStatus.ERROR,
    }.get(observation, WebsiteStatus.UNVERIFIED)


def record_presence(record):
    return classify_digital_presence(record.get("Site"), website_observation(record))


def is_without_own_website(presence):
    return presence.presence_type in {
        DigitalPresenceType.NOT_FOUND, DigitalPresenceType.SOCIAL_MEDIA,
        DigitalPresenceType.THIRD_PARTY_PLATFORM,
    }


def accepted_columns(result, presence=None):
    """Export aliases, preserving V3's existing priority thresholds."""
    labels = {"low": "BAIXA", "medium": "MEDIA", "good": "BOA", "high": "ALTA"}
    status = WebsiteStatus.NOT_FOUND_IN_GOOGLE.value
    if presence is not None and presence.presence_type in (DigitalPresenceType.SOCIAL_MEDIA, DigitalPresenceType.THIRD_PARTY_PLATFORM):
        status = f"Sem site próprio — {presence.provider}"
    return {"Possui Site": False, "Status Site": status,
            "Score": result.score, "Prioridade": labels[classify_priority(result.score).value]}
