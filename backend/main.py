"""Run from repository root: python -m uvicorn backend.main:app --host 127.0.0.1."""
from typing import Annotated
from contextlib import asynccontextmanager
import asyncio
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware
from .config import Settings
from .models import Lead, LeadPage, Overview
from .repository import DatabaseUnavailable, ReadRepository
from .prospecting.jobs import JobManager, JobError, configured_provider
from .prospecting.storage import SelectionStore, StorageError
from .prospecting.routes import router as prospecting_router
from .sdr.routes import router as sdr_router
from .sdr.service import SdrService, configured_provider as configured_sdr_provider
from .crm.service import CrmService, local_zone
from .crm.routes import router as crm_router


def create_app(settings: Settings | None = None, *, provider_factory=configured_provider, job_options=None, sdr_provider_factory=configured_sdr_provider):
    settings = settings or Settings.from_environment()
    settings.validate()
    if settings.storage_backend not in ('sqlite','postgres'):
        raise ValueError('LOUNG_STORAGE_BACKEND deve ser sqlite ou postgres')
    if settings.storage_backend == 'postgres':
        from .persistence.runtime import create_postgres_app
        return create_postgres_app(settings, provider_factory, job_options, sdr_provider_factory)
    repository = ReadRepository(settings.database_path)
    store = SelectionStore(settings.database_path, settings.writes_enabled)
    jobs = JobManager(store, provider_factory, **(job_options or {}))
    sdr = SdrService(store, sdr_provider_factory)
    @asynccontextmanager
    async def lifespan(_app):
        if settings.initialize_local:
            from .local_database import initialize_local_database
            await asyncio.to_thread(initialize_local_database, settings.database_path)
        async def reap():
            while True:
                await asyncio.sleep(30)
                jobs.reap()
                await asyncio.to_thread(sdr.reap)
        task = asyncio.create_task(reap())
        try:
            yield
        finally:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            jobs.close()
    app = FastAPI(title="Loung Prospect API", version="0.2.3", description="API local de prospecção e SDR. Gravação habilitada explicitamente por configuração.", lifespan=lifespan)
    app.state.prospecting = jobs
    app.state.sdr = sdr
    app.state.crm = CrmService(store)
    app.include_router(prospecting_router)
    app.include_router(sdr_router)
    app.include_router(crm_router)
    from .local_routes import router as local_router
    app.include_router(local_router)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1", "[::1]", "testserver"])

    @app.middleware("http")
    async def local_only(request: Request, call_next):
        peer = request.client.host if request.client else ''
        if peer not in ('127.0.0.1', '::1', 'testclient') or any(
            request.headers.get(key) for key in ('forwarded', 'x-forwarded-for', 'x-forwarded-host')
        ):
            return JSONResponse(status_code=403, content={'detail': 'Acesso permitido somente no computador local.'})
        # Browser requests go through same-origin Next BFF; no wildcard CORS.
        if request.headers.get("origin") or request.headers.get("sec-fetch-site") == "cross-site":
            return JSONResponse(status_code=403, content={"detail":"Utilize a aplicação web local para acessar a API."})
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.exception_handler(DatabaseUnavailable)
    async def unavailable(_request, _error):
        return JSONResponse(status_code=503, content={"detail":"Base de leads indisponível ou incompatível. Verifique a configuração local do backend."})

    @app.exception_handler(JobError)
    async def job_error(_request, error):
        return JSONResponse(status_code=error.status, content={"detail":error.message})

    @app.exception_handler(StorageError)
    async def storage_error(_request, error):
        return JSONResponse(status_code=503, content={"detail":str(error)})

    @app.get("/health")
    def health():
        return {"status":"ok", "mode":"selected-import" if settings.writes_enabled else "read-only"}

    @app.get("/v1/leads", response_model=LeadPage)
    def leads(q: Annotated[str, Query(max_length=200)]="", stage: Annotated[str, Query(max_length=100)]="",
              page: Annotated[int, Query(ge=1, le=1000000)]=1, pageSize: Annotated[int, Query(ge=1, le=100)]=20):
        return repository.list_leads(q=q.strip(), stage=stage, page=page, page_size=pageSize)

    @app.get("/v1/leads/{lead_id}", response_model=Lead)
    def lead(lead_id: int):
        result = repository.get_lead(lead_id)
        if result is None:
            raise HTTPException(404, "Lead não encontrado.")
        return result

    @app.get("/v1/overview", response_model=Overview)
    def overview(tz: Annotated[str | None, Query(max_length=100)]=None):
        return repository.overview(tz=local_zone(tz) if tz else None)

    return app


app = create_app()
