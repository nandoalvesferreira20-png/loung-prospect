"""Offline URL classification, independent of commercial qualification rules."""

from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from urllib.parse import urlsplit

from .models import ObservationStatus


class DigitalPresenceType(str, Enum):
    OWN_WEBSITE = "own_website"
    SOCIAL_MEDIA = "social_media"
    THIRD_PARTY_PLATFORM = "third_party_platform"
    NOT_FOUND = "not_found"
    UNVERIFIED = "unverified"
    ERROR = "error"


SOCIAL_PROVIDERS = MappingProxyType({
    "instagram.com": "Instagram", "facebook.com": "Facebook", "fb.com": "Facebook",
    "tiktok.com": "TikTok", "linkedin.com": "LinkedIn", "youtube.com": "YouTube",
    "youtu.be": "YouTube",
    "x.com": "X", "twitter.com": "X", "threads.net": "Threads",
})
THIRD_PARTY_PROVIDERS = MappingProxyType({
    "linktr.ee": "Linktree", "booksy.com": "Booksy", "calendly.com": "Calendly",
    "apps.apple.com": "App Store", "play.google.com": "Google Play",
    "wixsite.com": "Wix", "wordpress.com": "WordPress.com",
    "canva.site": "Canva Sites", "api.whatsapp.com": "WhatsApp",
    "trinks.com": "Trinks",
    "beacons.ai": "Beacons", "bio.site": "Bio Site", "sites.google.com": "Google Sites",
    "carrd.co": "Carrd", "ifood.com.br": "iFood", "rappi.com.br": "Rappi",
    "tripadvisor.com": "Tripadvisor", "tripadvisor.com.br": "Tripadvisor",
    "restaurantguru.com": "Restaurant Guru", "restaurantguru.com.br": "Restaurant Guru",
})


def matches_domain(hostname, domain):
    """Exact hostname or dot-delimited subdomain only."""
    return hostname == domain or hostname.endswith("." + domain)


@dataclass(frozen=True)
class DigitalPresence:
    presence_type: DigitalPresenceType
    url: str | None
    hostname: str | None
    provider: str | None
    reason: str


def classify_digital_presence(
    website: str | None,
    observation: ObservationStatus = ObservationStatus.UNVERIFIED,
) -> DigitalPresence:
    """Consume the website observation already resolved by the validator/adapter.

    NOT_FOUND is trusted only as an explicit upstream observation, never inferred
    from an empty value. Unverified fallback URLs are not promoted to evidence.
    OWN_WEBSITE means an independent-looking URL, not verified ownership.
    Provider matching uses exact domains or dot-delimited subdomains, not substrings.
    """
    state = ObservationStatus(observation)
    hostname = None
    valid = False
    if isinstance(website, str) and website:
        try:
            parsed = urlsplit(website)
            hostname = parsed.hostname
            if hostname:
                hostname = hostname.lower()
                if hostname.startswith("www."):
                    hostname = hostname[4:]
            # Access port to reject malformed port syntax; do not resolve hosts.
            parsed.port
            valid = bool(
                parsed.scheme.lower() in ("http", "https") and hostname
                and not any(char.isspace() for char in website)
                and not any(char in hostname for char in ("%", "\\"))
                and parsed.username is None and parsed.password is None
            )
        except ValueError:
            valid = False

    def result(kind, reason, provider=None):
        return DigitalPresence(kind, website, hostname, provider, reason)

    if state == ObservationStatus.ERROR:
        return result(DigitalPresenceType.ERROR, "Erro explícito na observação de website.")
    empty = website is None or (isinstance(website, str) and not website.strip())
    if state == ObservationStatus.NOT_FOUND:
        if empty:
            return result(DigitalPresenceType.NOT_FOUND, "Website não encontrado na fonte, conforme observação explícita.")
        return result(DigitalPresenceType.UNVERIFIED, "Valor preenchido contradiz a observação not_found.")
    if state != ObservationStatus.OBSERVED:
        return result(DigitalPresenceType.UNVERIFIED, "URL não confirmada pela observação; pode ser fallback genérico.")
    if not valid:
        return result(DigitalPresenceType.UNVERIFIED, "Sem URL HTTP/HTTPS válida para classificação.")
    if hostname == "barb.page.link":
        return result(DigitalPresenceType.UNVERIFIED,
                      "Link intermediário observado; destino e provedor não identificados sem seguir redirecionamento.")
    for providers, kind in (
        (SOCIAL_PROVIDERS, DigitalPresenceType.SOCIAL_MEDIA),
        (THIRD_PARTY_PROVIDERS, DigitalPresenceType.THIRD_PARTY_PLATFORM),
    ):
        for domain, provider in providers.items():
            if matches_domain(hostname, domain):
                return result(kind, f"Hostname corresponde ao provedor conhecido {provider} ({domain}).", provider)
    return result(DigitalPresenceType.OWN_WEBSITE,
                  "URL com aparência de website independente; titularidade e vínculo com a empresa não verificados.")
