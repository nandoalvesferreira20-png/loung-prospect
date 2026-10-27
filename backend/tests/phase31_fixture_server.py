"""Synthetic Auth + real PostgreSQL FastAPI runtime for browser QA only.
No real Supabase, Google or Groq calls. Secrets and identities are generated per run.
"""
from datetime import datetime,timedelta,timezone
from secrets import token_urlsafe
from uuid import uuid4
from pathlib import Path
import json
import jwt
import psycopg
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi import FastAPI,Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from backend.main import create_app as runtime
from backend.config import Settings
from backend.authorization import Identity,identity
from backend.persistence.postgres import Database,PgStore
from backend.tests.test_phase31_postgres import DSN


def create_app():
    key=ec.generate_private_key(ec.SECP256R1());uid,oid=str(uuid4()),str(uuid4());password=token_urlsafe(24)
    outsider=str(uuid4())
    with psycopg.connect(DSN,prepare_threshold=None) as c:
        assert c.execute('SELECT value FROM phase31_test_marker').fetchone()[0]=='synthetic-memory-only'
        for user in (uid,outsider):
            c.execute('INSERT INTO auth.users VALUES(%s)',(user,));c.execute("INSERT INTO profiles(id,display_name) VALUES(%s,'Browser QA')",(user,))
        c.execute("INSERT INTO organizations(id,name,slug) VALUES(%s,'Synthetic browser workspace',%s)",(oid,'browser-'+oid))
        c.execute("INSERT INTO organization_members(organization_id,user_id,role) VALUES(%s,%s,'member')",(oid,uid))
    tok=identity.set(Identity(uid,oid))
    try:PgStore(Database(DSN),True).save([{'empresa':'SYNTHETIC browser lead','telefone':'11999991234'}])
    finally:identity.reset(tok)
    issuer='http://127.0.0.1:8100/auth/v1'
    def user(user_id):return {'id':user_id,'aud':'authenticated','role':'authenticated','email':'qa@example.invalid','email_confirmed_at':'2026-01-01T00:00:00Z','app_metadata':{},'user_metadata':{},'created_at':'2026-01-01T00:00:00Z','updated_at':'2026-01-01T00:00:00Z'}
    refreshes={};revoked=set();recovery=[]
    def session(user_id):
        now=datetime.now(timezone.utc);refresh=token_urlsafe(32);refreshes[refresh]=user_id
        token=jwt.encode({'sub':user_id,'role':'authenticated','iss':issuer,'aud':'authenticated','iat':now,'exp':now+timedelta(hours=1)},key,algorithm='ES256',headers={'kid':'synthetic-key'})
        return {'access_token':token,'token_type':'bearer','expires_in':3600,'expires_at':int((now+timedelta(hours=1)).timestamp()),'refresh_token':refresh,'user':user(user_id)}
    app=FastAPI()
    app.add_middleware(CORSMiddleware,allow_origins=['http://127.0.0.1:3100'],allow_methods=['*'],allow_headers=['*'])
    @app.get('/__test/config')
    def config():return {'signature':'phase31-synthetic-only','email':'qa@example.invalid','outsider':'outsider@example.invalid','password':password,'recoveries':len(recovery)}
    @app.get('/auth/v1/.well-known/jwks.json')
    def jwks():return {'keys':[{**json.loads(jwt.algorithms.ECAlgorithm.to_jwk(key.public_key())),'kid':'synthetic-key','alg':'ES256','use':'sig'}]}
    @app.post('/auth/v1/token')
    async def login(request:Request):
        body=await request.json()
        if request.query_params.get('grant_type')=='refresh_token':
            current=refreshes.pop(body.get('refresh_token'),None)
            if current:return session(current)
        elif body.get('password')==password and body.get('email') in ('qa@example.invalid','outsider@example.invalid'):
            return session(uid if body['email']=='qa@example.invalid' else outsider)
        return JSONResponse({'msg':'Invalid login credentials','code':'invalid_credentials'},400)
    @app.get('/auth/v1/user')
    def get_user(request:Request):
        raw=request.headers.get('authorization','')[7:]
        try:
            claims=jwt.decode(raw,key.public_key(),algorithms=['ES256'],audience='authenticated',issuer=issuer)
            if raw in revoked:raise ValueError()
            return user(claims['sub'])
        except Exception:return JSONResponse({'msg':'Invalid session'},401)
    @app.post('/auth/v1/logout')
    def logout(request:Request):revoked.add(request.headers.get('authorization','')[7:]);return {}
    @app.post('/auth/v1/recover')
    def recover():recovery.append(True);return {}
    def forbidden():raise AssertionError('External provider forbidden')
    api=runtime(Settings(Path('unused-synthetic.db'),True,'postgres',DSN,'http://127.0.0.1:8100'),provider_factory=forbidden,sdr_provider_factory=forbidden)
    app.mount('/',api)
    return app
