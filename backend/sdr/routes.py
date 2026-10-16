from fastapi import APIRouter, Request, Path
from .models import GenerateRequest, SaveRequest

router = APIRouter(prefix="/v1/sdr", tags=["sdr"])


@router.get("/leads/{lead_id}")
def context(request: Request, lead_id: int = Path(gt=0)):
    return request.app.state.sdr.context(lead_id)


@router.post("/generate")
def generate(body: GenerateRequest, request: Request):
    return request.app.state.sdr.generate(body)


@router.get("/history/{lead_id}")
def history(request: Request, lead_id: int = Path(gt=0)):
    return request.app.state.sdr.store.history(lead_id)


@router.post("/history")
def save(body: SaveRequest, request: Request):
    return request.app.state.sdr.save(body)
