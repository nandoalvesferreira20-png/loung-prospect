"""Authenticated runtime: every request revalidates membership; no admin writes."""
from contextlib import asynccontextmanager
from types import SimpleNamespace
from threading import RLock
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware
from backend.authorization import TokenVerifier, Identity, identity
from backend.repository import DatabaseUnavailable
from backend.prospecting.storage import StorageError
from backend.prospecting.jobs import JobError
from backend.persistence.searches import PgJobManager as JobManager
from backend.prospecting.routes import router as prospecting
from backend.sdr.routes import router as sdr_routes
from backend.sdr.service import SdrService
from backend.persistence.sdr import PgSdrStore
from backend.crm.routes import router as crm
from backend.crm.service import CrmService, local_zone
from backend.persistence.postgres import Database,PgStore,PgReader,PgCrmMixin
from backend.persistence.session_queries import PROFILE_SQL
from backend.persistence.timing import current as request_timings, measure
import asyncio
import logging

log = logging.getLogger('loung.access')

def database_failure(error):
    code=getattr(error,'code','DB_UNAVAILABLE')
    log.warning('access stage=%s http=503 code=%s error_type=%s sqlstate=%s statement=%s permission=%s',
        getattr(error,'stage','database'),code,getattr(error,'error_type',type(error).__name__),
        getattr(error,'sqlstate',None),getattr(error,'statement_id',None),getattr(error,'permission',{}))
    return JSONResponse({'detail':'PostgreSQL indisponível. Nenhum fallback local foi utilizado.','code':code},503,headers={'Cache-Control':'no-store'})

class PgCrm(PgCrmMixin,CrmService): pass

class Scoped:
    def __init__(self,registry,field): self.registry,self.field=registry,field
    def __getattr__(self,name):
        who=identity.get()
        if who is None: raise HTTPException(401,'Entre novamente.')
        return getattr(getattr(self.registry.get(who.organization_id),self.field),name)

class Registry:
    def __init__(self,db,enabled,provider,options,sdr_provider):
        self.db,self.enabled,self.provider,self.options,self.sdr_provider=db,enabled,provider,options,sdr_provider
        self.items={}; self.lock=RLock()
    def get(self,org):
        with self.lock:
            if org not in self.items:
                if len(self.items)>=32: raise HTTPException(503,'Limite de workspaces ativos atingido.')
                store=PgStore(self.db,self.enabled);store.reader=PgReader(self.db)
                sdr=SdrService(store,self.sdr_provider);sdr.store=PgSdrStore(store)
                self.items[org]=SimpleNamespace(jobs=JobManager(store,self.provider,**(self.options or {})),sdr=sdr,crm=PgCrm(store))
            return self.items[org]

def create_postgres_app(settings,provider,options,sdr_provider):
    if not settings.postgres_dsn or not settings.supabase_url:
        # Fail closed without preventing tools/builds from importing the module.
        configured=False
    else: configured=True
    database=Database(settings.postgres_dsn)
    verifier=TokenVerifier(settings.supabase_url,settings.auth_audience) if configured else None
    registry=Registry(database,settings.writes_enabled,provider,options,sdr_provider)
    reader=PgReader(database)
    @asynccontextmanager
    async def lifespan(app):
        async def reap():
            while True:
                await asyncio.sleep(30)
                for item in list(registry.items.values()): item.jobs.reap();item.sdr.reap()
        task=asyncio.create_task(reap())
        try: yield
        finally:
            task.cancel()
            for item in registry.items.values(): item.jobs.close()
    app=FastAPI(title='Loung Prospect',version='0.3.1',lifespan=lifespan)
    app.add_middleware(TrustedHostMiddleware,allowed_hosts=['localhost','127.0.0.1','[::1]','testserver'])
    app.state.prospecting=Scoped(registry,'jobs');app.state.sdr=Scoped(registry,'sdr');app.state.crm=Scoped(registry,'crm')
    app.state.database=database;app.state.verifier=verifier
    app.state.writes_enabled=settings.writes_enabled
    from backend.persistence.team import router as team_router
    from backend.persistence.leads import router as lead_writes
    app.include_router(team_router)
    app.include_router(lead_writes)
    for router in (prospecting,sdr_routes,crm): app.include_router(router)
    @app.middleware('http')
    async def authorize(request,call_next):
        if request.headers.get('origin') or request.headers.get('sec-fetch-site')=='cross-site':
            return JSONResponse({'detail':'Utilize o BFF.','code':'BFF_REQUIRED'},403)
        token=None
        stage='configuration'
        try:
            if request.url.path!='/health':
                if not configured: raise HTTPException(503,'Configure Supabase Auth e PostgreSQL no servidor.')
                stage='jwt_verification'
                with measure('jwt'):
                    user=await asyncio.to_thread(app.state.verifier.verify,request.headers.get('authorization'))
                stage='membership'
                with measure('membership'):
                    memberships=await asyncio.to_thread(database.memberships,user)
                requested=request.headers.get('x-organization-id')
                member=next((m for m in memberships if m['organization_id']==requested),None) if requested else (memberships[0] if memberships else None)
                if not member: raise HTTPException(403,'Usuário sem acesso à organização.')
                token=identity.set(Identity(user,member['organization_id'],member['role']))
                request.state.member=member
                if request.method not in ('GET','HEAD','OPTIONS') and not settings.writes_enabled:
                    return JSONResponse({'detail':'Escrita desabilitada no servidor.','code':'WRITES_DISABLED'},403,headers={'Cache-Control':'no-store'})
            with measure('handler'):
                response=await call_next(request)
            response.headers['Cache-Control']='no-store'
            return response
        except HTTPException as e:
            code='BACKEND_NOT_CONFIGURED' if stage=='configuration' else 'MEMBERSHIP_REQUIRED' if stage=='membership' and e.status_code==403 else 'AUTH_UNAVAILABLE' if e.status_code==503 else 'AUTH_INVALID'
            log.warning('access stage=%s http=%s code=%s',stage,e.status_code,code)
            return JSONResponse({'detail':e.detail,'code':code},e.status_code,headers={'Cache-Control':'no-store'})
        except DatabaseUnavailable as error: return database_failure(error)
        finally:
            if token is not None: identity.reset(token)
    @app.middleware('http')
    async def performance(request,call_next):
        values={}
        token=request_timings.set(values)
        try:
            with measure('fastapi'):
                response=await call_next(request)
            response.headers['Server-Timing']=', '.join(f'{name};dur={duration:.1f}' for name,duration in values.items())
            return response
        finally:
            request_timings.reset(token)
    @app.exception_handler(DatabaseUnavailable)
    @app.exception_handler(StorageError)
    async def unavailable(request,error): return database_failure(error)
    @app.exception_handler(JobError)
    async def job_error(request,error): return JSONResponse({'detail':error.message},error.status)
    @app.get('/health')
    def health(): return {'status':'ok','storage':'postgres','configured':configured,
        'missingConfiguration':[name for name,value in [('SUPABASE_URL',settings.supabase_url),('LOUNG_POSTGRES_DSN',settings.postgres_dsn)] if not value]}
    @app.get('/v1/session')
    def session(request: Request):
        who=identity.get()
        with reader.connect() as (c,_):
            profile=c.execute(PROFILE_SQL,(who.user_id,)).fetchone()
        return {'userId':who.user_id,'displayName':profile['display_name'] if profile else 'Membro','organization':request.state.member['name'],'role':who.role,'writesEnabled':settings.writes_enabled}
    # Reuse validated query signatures from the legacy read endpoints.
    from typing import Annotated
    from fastapi import Query
    @app.get('/v1/leads')
    def leads(q: Annotated[str,Query(max_length=200)]='',stage: Annotated[str,Query(max_length=100)]='',page: Annotated[int,Query(ge=1,le=1000000)]=1,pageSize: Annotated[int,Query(ge=1,le=100)]=20):
        return reader.list_leads(q=q.strip(),stage=stage,page=page,page_size=pageSize)
    @app.get('/v1/leads/{lead_id}')
    def lead(lead_id:int):
        result=reader.get_lead(lead_id)
        if result is None: raise HTTPException(404,'Lead não encontrado.')
        return result
    @app.get('/v1/overview')
    def overview(tz: Annotated[str|None,Query(max_length=100)]=None): return reader.overview(tz=local_zone(tz) if tz else None)
    return app
