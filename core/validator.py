"""Offline validation of explicit website verification evidence.

This module does not perform verification. A caller must report a completed
inspection of the website information in the consulted source. A blank field,
a loaded page or an attempted extraction is not proof of completion.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from core.qualification.models import ObservationStatus

WEBSITE_VERIFICATION_KEY = "_website_verification"


@dataclass(frozen=True)
class WebsiteVerification:
    """Explicit report about the source, not the existence of a business website.

    website_found=None means no conclusion. completed=True must only be supplied
    after the website information in the correct source has been inspected
    successfully. Errors take precedence over a completion claim.
    """

    source_url: str
    completed: bool = False
    website_found: bool | None = None
    error: bool = False


def website_observation(record: Mapping[str, Any]) -> ObservationStatus:
    """Read optional verification metadata; never infer NOT_FOUND from emptiness.

    Legacy populated values remain OBSERVED (not verified URLs). Explicit reports
    must match Google Maps in the record. Malformed/contradictory reports yield
    ERROR rather than a commercial absence signal.
    """
    value = record.get("Site")
    present = isinstance(value, str) and bool(value.strip())
    if WEBSITE_VERIFICATION_KEY not in record:
        return ObservationStatus.OBSERVED if present else ObservationStatus.UNVERIFIED
    check = record[WEBSITE_VERIFICATION_KEY]
    if not isinstance(check, WebsiteVerification):
        return ObservationStatus.ERROR
    if (not isinstance(check.source_url, str) or not check.source_url.strip()
            or check.source_url != record.get("Google Maps")
            or type(check.completed) is not bool or type(check.error) is not bool
            or (check.website_found is not None and type(check.website_found) is not bool)):
        return ObservationStatus.ERROR
    if check.error:
        return ObservationStatus.ERROR
    if not check.completed or check.website_found is None:
        return ObservationStatus.UNVERIFIED
    if check.website_found != present:
        return ObservationStatus.ERROR
    return ObservationStatus.OBSERVED if present else ObservationStatus.NOT_FOUND


def with_website_verification(
    record: Mapping[str, Any], verification: WebsiteVerification,
) -> dict[str, Any]:
    """Return a shallow copy carrying immutable evidence; preserve all columns.

    Metadata is internal to the adapter, not a new Excel column. This helper is
    opt-in and is not called by the current scraper/extractor.
    """
    return {**record, WEBSITE_VERIFICATION_KEY: verification}
