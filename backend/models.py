from typing import Literal
from pydantic import BaseModel


class Lead(BaseModel):
    id: int
    company: str
    phone: str | None = None
    niche: str | None = None
    website: str | None = None
    location: str | None = None
    stage: str
    originalStage: str | None = None
    contactRole: Literal["reception", "direct", "unknown"]
    score: int | None = None
    nextContact: str | None = None
    nextAction: str | None = None


class LeadPage(BaseModel):
    items: list[Lead]
    total: int
    page: int
    pageSize: int
    stages: list[str]


class StageCount(BaseModel):
    stage: str
    count: int


class Overview(BaseModel):
    total: int
    today: int
    overdue: int
    meetings: int
    referenceDate: str
    invalidDates: int
    stageCounts: list[StageCount]
    actions: list[Lead]
