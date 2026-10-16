from typing import Annotated, Literal
from fastapi import APIRouter, Query, Request, Path
from .models import StageChange, ActivityCreate, FollowupChange

router = APIRouter(tags=["crm"])
Offset = Annotated[int, Query(ge=0, le=1000000)]
Limit = Annotated[int, Query(ge=1, le=50)]


@router.get("/v1/pipeline")
def pipeline(request: Request, q: Annotated[str, Query(max_length=200)]="", niche: Annotated[str, Query(max_length=200)]="", stage: Annotated[str | None, Query(max_length=200)]=None, offset: Offset=0, limit: Limit=8):
    return request.app.state.crm.pipeline(q.strip(), niche, stage, offset, limit)


@router.get("/v1/crm/leads/{lead_id}")
def detail(request: Request, lead_id: int=Path(gt=0, le=9223372036854775807)):
    return request.app.state.crm.detail(lead_id)


@router.patch("/v1/leads/{lead_id}/stage")
def stage(body: StageChange, request: Request, lead_id: int=Path(gt=0, le=9223372036854775807)):
    return request.app.state.crm.mutate(lead_id, body, "stage")


@router.get("/v1/leads/{lead_id}/activities")
def activities(request: Request, lead_id: int=Path(gt=0, le=9223372036854775807), offset: Offset=0, limit: Limit=20):
    return request.app.state.crm.activities(lead_id, offset, limit)


@router.post("/v1/leads/{lead_id}/activities")
def activity(body: ActivityCreate, request: Request, lead_id: int=Path(gt=0, le=9223372036854775807)):
    return request.app.state.crm.mutate(lead_id, body, "activity")


@router.get("/v1/followups")
def followups(request: Request, tz: Annotated[str, Query(max_length=100)]="America/Sao_Paulo", scope: Literal["pending","day"]="pending", offset: Offset=0, limit: Limit=20):
    return request.app.state.crm.followups(tz,scope,offset,limit)


@router.post("/v1/leads/{lead_id}/followups")
def schedule(body: FollowupChange, request: Request, lead_id: int=Path(gt=0, le=9223372036854775807)):
    return request.app.state.crm.mutate(lead_id,body,"followup")


@router.patch("/v1/followups/{lead_id}")
def followup(body: FollowupChange, request: Request, lead_id: int=Path(gt=0, le=9223372036854775807)):
    return request.app.state.crm.mutate(lead_id,body,"followup")


@router.get("/v1/dashboard/commercial")
def commercial(request: Request, tz: Annotated[str, Query(max_length=100)]="America/Sao_Paulo"):
    return request.app.state.crm.metrics(tz)
