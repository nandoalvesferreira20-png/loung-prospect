from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=160)]


class SearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    niche: Text
    location: Text
    quantity: int = Field(default=20, ge=1, le=100)
    neighborhood: str = Field(default="", max_length=120)
    onlyWithoutWebsite: bool = False
    minScore: int = Field(default=60, ge=0, le=100)


class ImportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    searchId: str = Field(pattern=r"^[0-9a-f]{32}$")
    resultIds: list[Annotated[int, Field(ge=1, le=100)]] = Field(min_length=1, max_length=100)


class SearchStatus(BaseModel):
    id: str
    query: SearchRequest
    status: Literal["pending", "running", "completed", "failed", "cancelled"]
    found: int
    scanned: int
    requestsMade: int
    pagesFetched: int
    requested: int
    cancelRequested: bool
    message: str
    error: str | None
    writesEnabled: bool
    expiresInSeconds: int
