from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator
from core.commercial.values import utc_iso


class Mutation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    revision: str = Field(pattern=r"^[a-f0-9]{64}$")


class StageChange(Mutation):
    stage: str = Field(min_length=1, max_length=200)
    confirmed: bool = Field(default=False, strict=True)


class ActivityCreate(Mutation):
    kind: Literal["Observação", "Contato realizado", "Resposta recebida", "Reunião agendada", "Proposta enviada"]
    description: str = Field(min_length=1, max_length=4000)
    confirmed: bool = Field(default=False, strict=True)
    channel: Literal["whatsapp", "telefone", "instagram", "email", "outro"] = "outro"

    @field_validator("description")
    @classmethod
    def meaningful(cls, value):
        if not value.strip():
            raise ValueError("Descrição vazia")
        return value.strip()


class FollowupChange(Mutation):
    action: Literal["schedule", "complete"] = "schedule"
    dueAt: str | None = Field(default=None, max_length=80)
    note: str = Field(default="", max_length=240)

    @field_validator("dueAt")
    @classmethod
    def aware_date(cls, value):
        return utc_iso(value)
