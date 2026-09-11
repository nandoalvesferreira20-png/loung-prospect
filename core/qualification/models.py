"""Data contracts only: no collection, scoring or commercial decisions."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class ObservationStatus(str, Enum):
    """NOT_FOUND concerns the consulted source, not real-world absence."""

    UNVERIFIED = "unverified"
    OBSERVED = "observed"
    NOT_FOUND = "not_found"
    ERROR = "error"


class QualificationStatus(str, Enum):
    QUALIFIED = "qualified"
    INSUFFICIENT_DATA = "insufficient_data"
    ERROR = "error"


@dataclass(frozen=True)
class QualificationNote:
    """A reason, evidence or limitation, optionally linked to a field/source."""

    code: str
    description: str
    field_name: str | None = None
    source_url: str | None = None


@dataclass
class QualificationInput:
    """Observed values, independent of spreadsheet column names.

    None means no available value; it does not establish absence. Missing entries
    in observations mean UNVERIFIED, even when a value is supplied (for example,
    a phone copied into whatsapp). OBSERVED does not certify external validity.
    Values are preserved without normalization or inference.
    """

    company_name: str | None
    city: str | None
    segment: str | None
    lead_id: str | None = None
    source_url: str | None = None
    phone: str | None = None
    whatsapp: str | None = None
    website: str | None = None
    address: str | None = None
    rating: str | None = None
    observations: dict[str, ObservationStatus] = field(default_factory=dict)

    def __post_init__(self):
        # Own the container rather than sharing the caller's mutable dictionary.
        allowed = set(self.__dataclass_fields__) - {"observations"}
        if self.observations.keys() - allowed:
            raise ValueError("Unknown observed field")
        self.observations = {
            name: ObservationStatus(status)
            for name, status in self.observations.items()
        }

    def observation_status(self, field_name: str) -> ObservationStatus:
        if field_name not in self.__dataclass_fields__ or field_name == "observations":
            raise ValueError("Unknown observed field")
        return self.observations.get(field_name, ObservationStatus.UNVERIFIED)


@dataclass
class QualificationResult:
    """Future analysis output, never an authorization to contact a lead.

    Status is required to avoid implicitly claiming that an analysis occurred.
    Score is optional commercial priority (0..100), not a sale probability.
    Timestamp and rule version must be supplied by the future analysis service.
    A timestamp, when provided, must include its timezone.
    """

    status: QualificationStatus
    score: int | None = None
    opportunity: str | None = None
    reasons: list[QualificationNote] = field(default_factory=list)
    evidence: list[QualificationNote] = field(default_factory=list)
    limitations: list[QualificationNote] = field(default_factory=list)
    rules_version: str | None = None
    analyzed_at: datetime | None = None

    def __post_init__(self):
        self.status = QualificationStatus(self.status)
        if self.score is not None and (
            type(self.score) is not int or not 0 <= self.score <= 100
        ):
            raise ValueError("Score must be an integer from 0 to 100 or None")
        if self.analyzed_at is not None and self.analyzed_at.utcoffset() is None:
            raise ValueError("analyzed_at must include a timezone")
        self.reasons = list(self.reasons)
        self.evidence = list(self.evidence)
        self.limitations = list(self.limitations)
