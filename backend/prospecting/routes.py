from typing import Annotated, Literal
from fastapi import APIRouter, Query, Request
from fastapi.responses import Response
from .models import SearchRequest, ImportRequest, SearchStatus


router = APIRouter(prefix="/v1", tags=["prospecção"])


def manager(request: Request):
    return request.app.state.prospecting


@router.post("/prospecting/search", response_model=SearchStatus, status_code=202)
def start(body: SearchRequest, request: Request):
    return manager(request).start(body)


@router.get("/prospecting/search/{search_id}", response_model=SearchStatus)
def status(search_id: str, request: Request):
    return manager(request).status(search_id)


@router.get("/prospecting/search/{search_id}/results")
def results(search_id: str, request: Request,
            page: Annotated[int, Query(ge=1, le=1000000)]=1,
            pageSize: Annotated[int, Query(ge=1,le=100)]=20):
    return manager(request).results(search_id,page,pageSize)


@router.post("/prospecting/search/{search_id}/cancel", response_model=SearchStatus)
def cancel(search_id: str, request: Request):
    return manager(request).cancel(search_id)


@router.post("/leads/import")
def save(body: ImportRequest, request: Request):
    return manager(request).save(body.searchId,body.resultIds)


@router.get("/prospecting/search/{search_id}/export")
def export(search_id: str, request: Request, format: Literal["csv","xlsx"]="csv"):
    content, media_type = manager(request).export(search_id,format)
    return Response(content, media_type=media_type,
                    headers={"Content-Disposition":f'attachment; filename="prospeccao-{search_id}.{format}"'})
