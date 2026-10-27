"""PostgreSQL integration using the fixed ephemeral PGlite socket, never env DSNs.
Start: node web/scripts/phase31-postgres.mjs
"""
from contextlib import closing
from datetime import datetime,timezone,timedelta
from pathlib import Path
from uuid import uuid4
from types import SimpleNamespace
import json
import sqlite3
import jwt
import psycopg
import pytest
from concurrent.futures import ThreadPoolExecutor
from time import monotonic,sleep
from fastapi.testclient import TestClient
from cryptography.hazmat.primitives.asymmetric import ec
from backend.main import create_app
from backend.config import Settings
from backend.authorization import identity,Identity,TokenVerifier
from backend.persistence.postgres import Database,PgStore,PgReader
from backend.tests.test_phase31_security import source
from backend.scripts.migrate_sqlite import inspect_source,apply

DSN='postgresql://postgres@127.0.0.1:55431/postgres?sslmode=disable&max_protocol_version=3.0'

@pytest.fixture
def workspace(tmp_path):
    try:
        c=psycopg.connect(DSN,connect_timeout=2)
    except psycopg.OperationalError:pytest.skip('Start synthetic PostgreSQL via phase31-postgres.mjs')
    with c:
        assert c.execute('SELECT value FROM phase31_test_marker').fetchone()[0]=='synthetic-memory-only'
        user,other,org,org2=[str(uuid4()) for _ in range(4)]
        for uid in (user,other):
            c.execute('INSERT INTO auth.users VALUES(%s)',(uid,))
            c.execute("INSERT INTO profiles(id,display_name) VALUES(%s,'Synthetic member')",(uid,))
        for oid,uid in ((org,user),(org2,other)):
            c.execute("INSERT INTO organizations(id,name,slug) VALUES(%s,'Synthetic test',%s)",(oid,'test-'+oid))
            c.execute("INSERT INTO organization_members(organization_id,user_id,role) VALUES(%s,%s,'member')",(oid,uid))
    key=ec.generate_private_key(ec.SECP256R1())
    from backend.tests.test_sdr_api import Provider
    from backend.tests.test_prospecting_api import transport
    from core.providers.google_places import GooglePlacesProvider
    app=create_app(Settings(tmp_path/'unused.db',True,'postgres',DSN,'https://synthetic.supabase.invalid'),
        sdr_provider_factory=Provider,provider_factory=lambda:GooglePlacesProvider(transport=transport,timeout=.1,max_requests=3))
    app.state.verifier.keys=SimpleNamespace(get_signing_key_from_jwt=lambda _:SimpleNamespace(key=key.public_key()))
    def headers(uid=user):
        now=datetime.now(timezone.utc)
        claims={'sub':uid,'role':'authenticated','iss':app.state.verifier.issuer,'aud':'authenticated','iat':now,'exp':now+timedelta(minutes=5)}
        return {'Authorization':'Bearer '+jwt.encode(claims,key,algorithm='ES256')}
    def seed(oid=org,uid=user):
        db=Database(DSN);store=PgStore(db,True)
        tok=identity.set(Identity(uid,oid,'member'))
        try:
            return store.save([{'empresa':'SYNTHETIC business','provider':'google','provider_place_id':'synthetic-place','telefone':'11999991234'}])
        finally:identity.reset(tok)
    return SimpleNamespace(app=app,user=user,other=other,org=org,org2=org2,headers=headers,seed=seed)


def test_full_contract_dedup_concurrency_audit(workspace):
    w=workspace
    assert w.seed()['inserted']==1
    assert w.seed()['duplicates']==1
    with TestClient(w.app) as c:
        h=w.headers();r=c.get('/v1/leads',headers=h);assert r.status_code==200,r.text
        lead=r.json()['items'][0];lid=lead['id']
        assert c.get('/v1/overview',headers=h).status_code==200
        assert c.get('/v1/pipeline',headers=h).status_code==200
        assert c.get('/v1/dashboard/commercial',headers=h).status_code==200
        assert c.get('/v1/followups',headers=h).status_code==200
        detail=c.get(f'/v1/crm/leads/{lid}',headers=h);assert detail.status_code==200,detail.text
        revision=detail.json()['lead']['revision']
        body={'revision':revision,'stage':'Em conversa','confirmed':False}
        r=c.patch(f'/v1/leads/{lid}/stage',json=body,headers=h);assert r.status_code==200,r.text
        assert c.patch(f'/v1/leads/{lid}/stage',json=body,headers=h).status_code==409
        body={'revision':r.json()['revision'],'kind':'Observação','description':'Nota sintética','channel':'outro'}
        r=c.post(f'/v1/leads/{lid}/activities',json=body,headers=h);assert r.status_code==200,r.text
        body={'revision':r.json()['revision'],'dueAt':'2026-12-01T10:00:00-03:00','note':'Retorno sintético'}
        r=c.post(f'/v1/leads/{lid}/followups',json=body,headers=h);assert r.status_code==200,r.text
        history=c.get(f'/v1/leads/{lid}/activities',headers=h);assert history.status_code==200,history.text
        assert any(i['actorName']=='Synthetic member' for i in history.json()['items'])
        assert c.get(f'/v1/sdr/history/{lid}',headers=h).status_code==200
        assert c.get(f'/v1/sdr/leads/{lid}',headers=h).status_code==200
    with psycopg.connect(DSN) as db:
        audit=db.execute('SELECT actor_id,old_value,new_value FROM audit_events WHERE organization_id=%s ORDER BY id',(w.org,)).fetchall()
        assert len(audit)>=5 and all(str(r[0])==w.user for r in audit)
        assert not any('telefone' in (r[2] or {}) for r in audit)
        assert any((r[1] or {}).get('status')=='Novo' and r[2].get('status')=='Em conversa' for r in audit)


def test_isolation_and_no_privilege_escalation(workspace):
    w=workspace;w.seed();w.seed(w.org2,w.other)
    with TestClient(w.app) as c:
        a=c.get('/v1/leads',headers=w.headers()).json()['items'][0]['id']
        b=c.get('/v1/leads',headers=w.headers(w.other)).json()['items'][0]['id']
        assert a!=b
        assert c.get(f'/v1/crm/leads/{a}',headers=w.headers(w.other)).status_code==404
        assert c.get('/v1/leads',headers={**w.headers(),'x-organization-id':w.org2}).status_code==403
    with psycopg.connect(DSN) as db:
        db.execute('SET LOCAL ROLE loung_api')
        db.execute("SELECT set_config('request.jwt.claims',%s,true),set_config('app.organization_id',%s,true)",(json.dumps({'sub':w.user}),w.org))
        assert db.execute('SELECT count(*) FROM leads').fetchone()[0]==1
        assert db.execute('SELECT count(*) FROM leads WHERE organization_id=%s',(w.org2,)).fetchone()[0]==0
        db.execute("DO $$ BEGIN UPDATE organization_members SET role='owner'; RAISE EXCEPTION 'Privilege escalation was allowed'; EXCEPTION WHEN insufficient_privilege THEN NULL; END $$")
    with psycopg.connect(DSN) as db:
        db.execute('SET LOCAL ROLE loung_api')
        db.execute("DO $$ BEGIN DELETE FROM audit_events; RAISE EXCEPTION 'Audit deletion was allowed'; EXCEPTION WHEN insufficient_privilege THEN NULL; END $$")


def test_authorship_cannot_be_forged(workspace):
    w=workspace
    tok=identity.set(Identity(w.user,w.org))
    try:
        store=PgStore(Database(DSN),True)
        with closing(store.connect('rw')) as c,c:
            c.execute("INSERT INTO leads(empresa,status,created_by,updated_by) VALUES('Synthetic','Novo',?,?)",(w.other,w.other))
    finally:identity.reset(tok)
    with psycopg.connect(DSN) as db:
        assert str(db.execute('SELECT created_by FROM leads WHERE organization_id=%s',(w.org,)).fetchone()[0])==w.user


def test_migration_repeated_and_preserved(workspace,tmp_path):
    p=source(tmp_path);data,report=inspect_source(p,tmp_path/'backup')
    apply(data,report,DSN,workspace.org,'synthetic-source')
    data,again=inspect_source(p,tmp_path/'backup')
    apply(data,again,DSN,workspace.org,'synthetic-source')
    assert all(t['migrated']==0 for t in again['tables'].values())
    assert again['tables']['leads']['ignored']==1
    with psycopg.connect(DSN) as db:
        assert db.execute('SELECT count(*) FROM outreach_revisions WHERE organization_id=%s',(workspace.org,)).fetchone()[0]==1
        assert db.execute('SELECT status FROM leads WHERE organization_id=%s',(workspace.org,)).fetchone()[0]=='Etapa própria'


def test_shared_wallet_and_simultaneous_revision(workspace):
    w=workspace;w.seed()
    with psycopg.connect(DSN) as db:
        db.execute("INSERT INTO organization_members(organization_id,user_id,role) VALUES(%s,%s,'member')",(w.org,w.other))
    with TestClient(w.app) as c:
        h=w.headers();other={**w.headers(w.other),'x-organization-id':w.org}
        lead=c.get('/v1/leads',headers=h).json()['items'][0]['id']
        assert c.get('/v1/leads',headers=other).json()['items'][0]['id']==lead
        revision=c.get(f'/v1/crm/leads/{lead}',headers=h).json()['lead']['revision']
        def update(headers):return c.patch(f'/v1/leads/{lead}/stage',headers=headers,json={'revision':revision,'stage':'Em conversa'}).status_code
        with ThreadPoolExecutor(2) as pool:
            assert sorted(pool.map(update,[h,other]))==[200,409]
        assert c.get(f'/v1/crm/leads/{lead}',headers=other).json()['lead']['stage']=='Em conversa'


def test_sdr_and_durable_search(workspace):
    w=workspace;w.seed()
    with TestClient(w.app) as c:
        h=w.headers();lid=c.get('/v1/leads',headers=h).json()['items'][0]['id']
        r=c.post('/v1/sdr/generate',headers=h,json={'leadId':lid,'requestId':str(uuid4())})
        assert r.status_code==200,r.text
        draft=r.json()
        saved=c.post('/v1/sdr/history',headers=h,json={'draftId':draft['draftId'],'message':draft['message'],'status':'EDITADA'})
        assert saved.status_code==200,saved.text
        history=c.get(f'/v1/sdr/history/{lid}',headers=h).json()
        assert history['items'][0]['actorName']=='Synthetic member'
        r=c.post('/v1/prospecting/search',headers=h,json={'niche':'Synthetic niche','location':'Synthetic city','quantity':3,'minScore':0})
        assert r.status_code==202,r.text
        search=r.json()['id'];deadline=monotonic()+10
        while monotonic()<deadline:
            status=c.get('/v1/prospecting/search/'+search,headers=h).json()
            if status['status'] in ('completed','failed','cancelled'):break
            sleep(.02)
        assert status['status']=='completed',status
        # Cache loss/restart still allows durable results to be read.
        who=identity.set(Identity(w.user,w.org))
        try:
            manager=w.app.state.prospecting
            manager.jobs.clear()
        finally:identity.reset(who)
        results=c.get('/v1/prospecting/search/'+search+'/results',headers=h)
        assert results.status_code==200,results.text
        assert results.json()['total']==3


def test_migration_trigger_failure_rolls_back(workspace,tmp_path):
    """An AFTER trigger failure must undo parents, audit and migration map too."""
    w=workspace
    data,report=inspect_source(source(tmp_path),tmp_path/'backup')
    with psycopg.connect(DSN) as db:
        db.execute("""CREATE FUNCTION public.synthetic_bad_audit() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN INSERT INTO public.audit_events(organization_id,lead_id,action,origin)
        VALUES(NEW.organization_id,-999,'synthetic','migration'); RETURN NEW; END $$""")
        db.execute("CREATE TRIGGER synthetic_bad_audit AFTER INSERT ON public.lead_interactions FOR EACH ROW EXECUTE FUNCTION public.synthetic_bad_audit()")
    try:
        with pytest.raises(psycopg.errors.ForeignKeyViolation):
            apply(data,report,DSN,w.org,'original-source-id')
        diagnostic=report['failureDiagnostic']
        assert diagnostic['sqlstate']=='23503'
        assert diagnostic['type']=='ForeignKeyViolation'
        assert diagnostic['table']=='audit_events'
        assert diagnostic['constraint']
        assert diagnostic['phase']=='lead_interactions.insert'
        assert report['applied'] is False
        assert all(t['migrated']==0 for t in report['tables'].values())
        with psycopg.connect(DSN) as db:
            for table in ('leads','lead_interactions','audit_events','migration_map'):
                assert db.execute('SELECT count(*) FROM '+table+' WHERE organization_id=%s',(w.org,)).fetchone()[0]==0
    finally:
        with psycopg.connect(DSN) as db:
            db.execute('DROP TRIGGER synthetic_bad_audit ON public.lead_interactions')
            db.execute('DROP FUNCTION public.synthetic_bad_audit()')
    # Retry exactly the same source-id after repair, then verify idempotency.
    apply(data,report,DSN,w.org,'original-source-id')
    apply(data,report,DSN,w.org,'original-source-id')
    with psycopg.connect(DSN) as db:
        assert db.execute('SELECT count(*) FROM leads WHERE organization_id=%s',(w.org,)).fetchone()[0]==1


def test_migration_target_inspection_is_read_only(workspace):
    from backend.scripts.check_migration_target import inspect_target
    result=inspect_target(DSN,workspace.org,'original-source-id')
    assert result['readOnly'] is True
    assert result['mappedForSource']==[]
    assert result['counts']['leads']==0
    assert result['auditFunctions']
    assert result['foreignKeys']
