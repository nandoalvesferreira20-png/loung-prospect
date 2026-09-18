"""Provider-neutral structured generation and draft lifecycle."""
from dataclasses import dataclass
from enum import Enum
import math
from typing import Mapping, Protocol

MAX_MESSAGE_LENGTH = 1200


class OutreachStatus(str, Enum):
    GENERATED = "GERADA"
    EDITED = "EDITADA"
    APPROVED = "APROVADA"
    SENT = "ENVIADA"  # reserved; no transition exposed
    REPLIED = "RESPONDEU"  # reserved
    CANCELLED = "CANCELADA"


def validate_message(message):
    if not isinstance(message, str) or not message.strip():
        raise ValueError("A mensagem não pode ficar vazia.")
    if len(message) > MAX_MESSAGE_LENGTH:
        raise ValueError(f"A mensagem deve ter até {MAX_MESSAGE_LENGTH} caracteres.")
    return message


@dataclass(frozen=True)
class SalesGeneration:
    mensagem: str
    angulo: str
    confianca: float

    def __post_init__(self):
        validate_message(self.mensagem)
        if not isinstance(self.angulo, str) or not self.angulo.strip() or len(self.angulo) > 200:
            raise ValueError("Ângulo inválido na resposta da IA.")
        if type(self.confianca) not in (int, float) or not math.isfinite(self.confianca) or not 0 <= self.confianca <= 1:
            raise ValueError("Confiança inválida na resposta da IA.")

    @classmethod
    def from_mapping(cls, response):
        if not isinstance(response, Mapping) or set(response) != {"mensagem", "angulo", "confianca"}:
            raise ValueError("A IA retornou uma estrutura inválida.")
        return cls(**response)


class SalesAIProvider(Protocol):
    def generate(self, *, system_prompt: str, evidence: dict) -> dict: ...
