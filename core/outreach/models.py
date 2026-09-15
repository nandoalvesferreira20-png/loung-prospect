"""Immutable text-generation contracts. They do not authorize contact."""
from dataclasses import dataclass
from typing import Protocol

CHANNELS = ("whatsapp", "instagram", "phone")
OBJECTIVES = ("first_contact", "follow_up", "reactivation")
TONES = ("professional", "friendly", "direct")


@dataclass(frozen=True)
class OutreachContext:
    company_name: str | None = None
    segment: str | None = None
    city: str | None = None
    website: str | None = None
    phone: str | None = None
    whatsapp: str | None = None
    rating: str | None = None
    review_count: int | None = None
    qualification_score: int | None = None
    priority: str | None = None
    opportunity: str | None = None
    responsible: str | None = None

    def __post_init__(self):
        score = self.qualification_score
        if score is not None and (type(score) is not int or not 0 <= score <= 100):
            raise ValueError("Score deve ser inteiro entre 0 e 100.")


@dataclass(frozen=True)
class OutreachRequest:
    context: OutreachContext
    channel: str = "whatsapp"
    objective: str = "first_contact"
    tone: str = "professional"
    variation: int = 0

    def __post_init__(self):
        if not isinstance(self.context, OutreachContext):
            raise ValueError("Contexto de abordagem inválido.")
        for value, choices in ((self.channel, CHANNELS), (self.objective, OBJECTIVES), (self.tone, TONES)):
            if value not in choices:
                raise ValueError(f"Opção de abordagem inválida: {value}")
        if type(self.variation) is not int or self.variation not in range(3):
            raise ValueError("Variação deve ser 0, 1 ou 2.")


@dataclass(frozen=True)
class OutreachResult:
    message: str
    channel: str
    objective: str
    tone: str
    template_id: str
    warnings: tuple[str, ...] = ()

    def __post_init__(self):
        object.__setattr__(self, "warnings", tuple(self.warnings))


class OutreachGenerator(Protocol):
    def generate(self, request: OutreachRequest) -> OutreachResult: ...
