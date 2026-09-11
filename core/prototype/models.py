"""Prototype Studio contracts only; no generation or automatic selection.

company_name is display data and MUST NEVER be used directly as a filesystem
path. A future slug/generator must validate paths and containment separately.
Paths here are opaque strings: no existence checks or filesystem operations.
Future JSON serialization must explicitly encode enums and ISO 8601 timestamps.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


def _required_text(name: str, value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be nonempty text")


def _score(value: int | None) -> None:
    if value is not None and (type(value) is not int or not 0 <= value <= 100):
        raise ValueError("qualification_score must be an integer from 0 to 100 or None")


def _timestamp(value: datetime | None) -> None:
    if value is not None and (not isinstance(value, datetime) or value.utcoffset() is None):
        raise ValueError("Timestamp must be a timezone-aware datetime")


@dataclass(frozen=True)
class PrototypeLead:
    """Selected lead data; opportunity/score do not authorize generation."""

    company_name: str
    segment: str
    city: str | None = None
    phone: str | None = None
    whatsapp: str | None = None
    address: str | None = None
    current_website: str | None = None
    opportunity: str | None = None
    qualification_score: int | None = None

    def __post_init__(self):
        _required_text("company_name", self.company_name)
        _required_text("segment", self.segment)
        _score(self.qualification_score)


@dataclass(frozen=True)
class PrototypeTemplate:
    """Template identity and version; path is not loaded or validated on disk."""

    template_id: str
    name: str
    segment: str
    version: str
    template_path: str

    def __post_init__(self):
        for name in ("template_id", "name", "segment", "version", "template_path"):
            _required_text(name, getattr(self, name))


@dataclass(frozen=True)
class PrototypeRequest:
    """Explicit request from future human selection; never derived automatically.

    This data object alone does not verify that human approval occurred.
    """

    lead: PrototypeLead
    template: PrototypeTemplate
    output_directory: str
    requested_at: datetime | None = None

    def __post_init__(self):
        if not isinstance(self.lead, PrototypeLead) or not isinstance(self.template, PrototypeTemplate):
            raise TypeError("lead and template must use the prototype contracts")
        _required_text("output_directory", self.output_directory)
        _timestamp(self.requested_at)


@dataclass(frozen=True)
class PrototypeManifest:
    """Future prototype.json contents. source identifies the supplied lead origin."""

    prototype_id: str
    company_name: str
    segment: str
    template_id: str
    template_version: str
    created_at: datetime
    source: str | None = None
    qualification_score: int | None = None

    def __post_init__(self):
        for name in ("prototype_id", "company_name", "segment", "template_id", "template_version"):
            _required_text(name, getattr(self, name))
        if self.created_at is None:
            raise ValueError("created_at is required")
        _timestamp(self.created_at)
        _score(self.qualification_score)


class PrototypeStatus(str, Enum):
    CREATED = "created"
    FAILED = "failed"


@dataclass(frozen=True)
class PrototypeResult:
    """Future generation outcome. Failure may happen before an ID is assigned.

    CREATED requires an ID, output path and matching manifest. Lists are owned by
    each result; immutable nested contracts can safely be shared.
    """

    status: PrototypeStatus
    prototype_id: str | None = None
    output_path: str | None = None
    manifest: PrototypeManifest | None = None
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def __post_init__(self):
        object.__setattr__(self, "status", PrototypeStatus(self.status))
        for name in ("prototype_id", "output_path"):
            if getattr(self, name) is not None:
                _required_text(name, getattr(self, name))
        if self.manifest is not None:
            if not isinstance(self.manifest, PrototypeManifest):
                raise TypeError("manifest must be a PrototypeManifest")
            if self.manifest.prototype_id != self.prototype_id:
                raise ValueError("Result and manifest IDs must match")
        if self.status == PrototypeStatus.CREATED:
            if self.prototype_id is None or self.output_path is None or self.manifest is None:
                raise ValueError("created requires prototype_id, output_path and manifest")
        for name in ("errors", "warnings"):
            items = getattr(self, name)
            if not isinstance(items, (list, tuple)) or not all(isinstance(item, str) for item in items):
                raise TypeError(f"{name} must be a collection of strings")
            object.__setattr__(self, name, list(items))
