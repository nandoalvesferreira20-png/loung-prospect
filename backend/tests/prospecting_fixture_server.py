"""Explicit synthetic server for browser tests. Never uses .env/live transport."""
from contextlib import asynccontextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from time import sleep
import asyncio
import json
import os
import sqlite3
from backend.config import Settings
from backend.main import create_app as production_app
from core.database.schema import initialize_database
from core.providers.google_places import GooglePlacesProvider


def create_app(authenticated=False):
    os.environ["GOOGLE_PLACES_API_KEY"]="synthetic-browser-test-key"
    parent=Path(__file__).resolve().parents[1]/".phase22-ui"
    parent.mkdir(exist_ok=True)
    temporary=TemporaryDirectory(dir=parent)
    path=Path(temporary.name)/"synthetic.db"
    initialize_database(path)
    with sqlite3.connect(path) as connection:
        connection.execute("INSERT INTO leads(empresa,status,provider,provider_place_id,created_at,updated_at) VALUES ('TESTE FASE 2.2 EXISTENTE','Novo','google_places','ui-1','2026-01-01','2026-01-01')")
    calls=[]
    def transport(payload,headers,timeout):
        calls.append(payload)
        if "Falha" in payload["textQuery"]:
            return 429,b'{"error":{"message":"synthetic-sensitive-value"}}'
        start=21 if "pageToken" in payload else 1
        if start==21 and any(word in payload["textQuery"] for word in ("Cancelamento","Lenta")):
            sleep(8)
        if "Vazia" in payload["textQuery"]:return 200,b'{}'
        count=min(payload["pageSize"],25-start+1)
        places=[{"id":f"ui-{index}","displayName":{"text":f"Teste empresa {index:02} — São Paulo"},"formattedAddress":f"Rua de Teste {index}, São Paulo",**({"nationalPhoneNumber":"(11) 99999-0000"} if index%2==0 else {})} for index in range(start,start+count)]
        return 200,json.dumps({"places":places,**({"nextPageToken":"page-2"} if start==1 and count==20 else {})}).encode()
    app=production_app(Settings(path,True),provider_factory=lambda:GooglePlacesProvider(transport=transport,timeout=15,max_requests=10))
    if authenticated:
        from backend.authorization import TokenVerifier
        from fastapi import HTTPException,Request
        from fastapi.responses import JSONResponse
        verifier=TokenVerifier('http://127.0.0.1:8112')
        @app.middleware('http')
        async def auth_and_slow_results(request,call_next):
            if request.url.path.startswith('/v1/'):
                try:request.state.user=await asyncio.to_thread(verifier.verify,request.headers.get('authorization'))
                except HTTPException as error:return JSONResponse({'detail':'Synthetic auth required'},error.status_code)
                parts=request.url.path.split('/')
                if parts[-1]=='results':
                    job=app.state.prospecting.get(parts[-2])
                    if 'Lenta' in job.request.niche:await asyncio.sleep(2.2)
            return await call_next(request)
        @app.get('/v1/session')
        def session(request:Request):
            return {'userId':request.state.user,'displayName':'Synthetic Operator',
                    'organization':'Synthetic Workspace','role':'owner','writesEnabled':True}
    original=app.router.lifespan_context
    @asynccontextmanager
    async def lifespan(app):
        async with original(app):
            yield
        temporary.cleanup()
    app.router.lifespan_context=lifespan
    @app.get("/__test/metrics")
    def metrics():return {"signature":"phase22-synthetic-only","calls":len(calls),"backups":len(list((path.parent/"backups").glob("*.db")))}
    return app


def create_authenticated_app():
    return create_app(authenticated=True)
