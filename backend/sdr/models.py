from typing import Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, field_validator


class GenerateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    leadId: int = Field(gt=0, strict=True)
    recipient: Literal["auto", "direct", "reception", "unknown"] = "auto"
    service: Literal["auto", "website", "landing", "management", "crm", "automation"] = "auto"
    instruction: str = Field(default="", max_length=500)
    requestId: UUID
    previousDraftId: UUID | None = None


class SaveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    draftId: UUID
    message: str = Field(min_length=1, max_length=1200)
    status: Literal["EDITADA", "APROVADA"] = "EDITADA"

    @field_validator("message")
    @classmethod
    def not_blank(cls, value):
        if not value.strip():
            raise ValueError("Mensagem vazia")
        return value
