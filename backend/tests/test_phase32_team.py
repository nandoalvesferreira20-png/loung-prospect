"""Synthetic-only PostgreSQL integration; never uses environment DSNs."""
from pathlib import Path
import psycopg
import pytest
from fastapi.testclient import TestClient
from backend.tests.test_phase31_postgres import workspace,DSN
from backend.authorization import Identity
from backend.persistence.postgres import Database
from backend.tests.test_auth_schema_acl import capture

@pytest.fixture(scope='module',autouse=True)
def install_team_schema():
    with psycopg.connect(DSN,prepare_threshold=None) as c:
        assert c.execute('SELECT value FROM phase31_test_marker').fetchone()[0]=='synthetic-memory-only'
        c.execute('ALTER TABLE auth.users ADD COLUMN IF NOT EXISTS email text')
        # Simulate Supabase/custom default grants, including a nonstandard role.
        c.execute('CREATE ROLE synthetic_default_executor NOLOGIN')
        c.execute('ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT EXECUTE ON FUNCTIONS TO authenticated,service_role,synthetic_default_executor')
        c.execute("INSERT INTO organizations(name,slug) VALUES('Synthetic preservation','synthetic-preservation')")
        c.execute("INSERT INTO leads(organization_id,empresa,status) SELECT o.id,'Synthetic '||n,'Novo' FROM organizations o CROSS JOIN generate_series(1,160) n WHERE o.slug='synthetic-preservation'")
        c.execute("INSERT INTO lead_interactions(organization_id,lead_id,tipo,created_at) SELECT organization_id,id,'synthetic','2026-01-01' FROM leads WHERE organization_id=(SELECT id FROM organizations WHERE slug='synthetic-preservation') ORDER BY id LIMIT 17")
        c.execute("INSERT INTO migration_map SELECT organization_id,'synthetic-source-id','leads',id,id FROM leads WHERE organization_id=(SELECT id FROM organizations WHERE slug='synthetic-preservation')")
        def snapshot():
            return [c.execute('SELECT to_jsonb(t) FROM public.'+table+' t ORDER BY to_jsonb(t)::text').fetchall()
                    for table in ('leads','lead_interactions','migration_map','audit_events')]
        before=snapshot()
        c.execute(Path('supabase/migrations/202610200002_team_operations.sql').read_text(encoding='utf8'))
        assert snapshot()==before # rows, IDs, source mapping, timestamps and audit unchanged
        for table,count in [('leads',160),('lead_interactions',17)]:
            assert c.execute('SELECT count(*) FROM '+table+" WHERE organization_id=(SELECT id FROM organizations WHERE slug='synthetic-preservation')").fetchone()[0]==count
        c.execute('ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE EXECUTE ON FUNCTIONS FROM authenticated,service_role,synthetic_default_executor')

def provision(w,role='owner'):
    with psycopg.connect(DSN) as c:
        c.execute('UPDATE organization_members SET role=%s WHERE organization_id=%s AND user_id=%s',(role,w.org,w.user))
        c.execute("UPDATE auth.users SET email='synthetic@example.invalid' WHERE id=%s",(w.user,))

def test_roster_and_owner_permissions(workspace):
    w=workspace
    with TestClient(w.app) as c:
        h=w.headers()
        r=c.get('/v1/team',headers=h)
        assert r.status_code==200
        assert [x['userId'] for x in r.json()['items']]==[w.user]
        assert r.json()['canManage'] is False
        assert c.patch('/v1/team/'+w.other,headers=h,json={'role':'owner'}).status_code==403
        assert c.get('/v1/organization/activities',headers=h).status_code==403
        provision(w,'admin')
        assert c.patch('/v1/team/'+w.other,headers=h,json={'role':'owner'}).status_code==403
        assert c.get('/v1/organization/activities',headers=h).status_code==200
        provision(w)
        assert c.patch('/v1/team/'+w.user,headers=h,json={'role':'member'}).status_code==403
        assert c.patch('/v1/team/'+w.other,headers=h,json={'role':'member'}).status_code==404
        assert c.get('/v1/team',headers={**h,'x-organization-id':w.org2}).status_code==403

def test_owner_change_remove_audit_and_revocation(workspace):
    w=workspace;provision(w)
    with psycopg.connect(DSN) as db:
        db.execute("INSERT INTO organization_members(organization_id,user_id,role) VALUES(%s,%s,'member')",(w.org,w.other))
    with TestClient(w.app) as c:
        h=w.headers()
        assert c.patch('/v1/team/'+w.other,headers=h,json={'role':'admin','organization_id':w.org2}).status_code==422
        assert c.patch('/v1/team/'+w.other,headers=h,json={'role':'admin'}).status_code==200
        events=c.get('/v1/organization/activities',headers=h).json()['items']
        event=next(e for e in events if e['action']=='organization_members.update' and e['actor_id']==w.user)
        assert 'new_value' not in event
        assert event['subject_id']==w.other
        assert (event['before_role'],event['after_role'])==('member','admin')
        assert c.delete('/v1/team/'+w.other,headers=h).status_code==200
        assert c.get('/v1/session',headers={**w.headers(w.other),'x-organization-id':w.org}).status_code==403
        assert c.get('/v1/session',headers=w.headers(w.other)).status_code==200

def test_sql_cannot_elevate_or_remove_last_owner(workspace):
    w=workspace;provision(w)
    # Operator-level invariant, even outside the API. Trap negative SQL server-side.
    with psycopg.connect(DSN,prepare_threshold=None) as c:
        result=capture(c,"DELETE FROM public.organization_members WHERE organization_id='"+w.org+"' AND user_id='"+w.user+"'")
        assert result['sqlstate']=='23514'
        assert c.execute('SELECT role FROM organization_members WHERE organization_id=%s AND user_id=%s',(w.org,w.user)).fetchone()[0]=='owner'
    c=Database(DSN).open(Identity(w.other,w.org2,'owner'),'rw')
    try:
        # A forged Python role cannot change the actual membership checked by SQL.
        assert capture(c,"SELECT public.manage_member('"+w.user+"','owner',false)")['sqlstate']=='42501'
        assert capture(c,"UPDATE public.organization_members SET role='owner' WHERE user_id='"+w.other+"'")['sqlstate']=='42501'
        assert c.execute('SELECT count(*) AS n FROM public.team_roster()').fetchone()['n']==1
    finally:c.close()

@pytest.mark.parametrize('role',['owner','admin','member'])
def test_lead_create_edit_isolation_revision_and_audit(workspace,role):
    w=workspace;provision(w,role)
    with TestClient(w.app) as c:
        h=w.headers()
        body={'empresa':'Synthetic manual','email':'synthetic@example.invalid','telefone':'synthetic','endereco':'Synthetic address'}
        assert c.post('/v1/leads',headers=h,json={**body,'organization_id':w.org2}).status_code==422
        assert c.post('/v1/leads',headers=h,json=body).status_code==201
        lead=c.get('/v1/leads',headers=h).json()['items'][0]['id']
        before=c.get(f'/v1/leads/{lead}/edit',headers=h).json()
        edit={**before['fields'],'observacoes':'Synthetic note','revision':before['revision'],'telefone':'changed'}
        assert c.patch(f'/v1/leads/{lead}',headers=h,json=edit).status_code==200
        assert c.patch(f'/v1/leads/{lead}',headers=h,json=edit).status_code==409
        assert c.get(f'/v1/leads/{lead}/edit',headers=w.headers(w.other)).status_code==404
        assert c.patch(f'/v1/leads/{lead}',headers=w.headers(w.other),json=edit).status_code==404
        assert c.post('/v1/leads',headers=h,json=body).json()['duplicates']==1
    with psycopg.connect(DSN) as db:
        assert db.execute("SELECT count(*) FROM audit_events WHERE organization_id=%s AND actor_id=%s AND action='leads.update'",(w.org,w.user)).fetchone()[0]==1

def test_write_switch_blocks_all_new_mutations(workspace,tmp_path):
    from backend.main import create_app
    from backend.config import Settings
    w=workspace;provision(w)
    app=create_app(Settings(tmp_path/'unused.db',False,'postgres',DSN,'https://synthetic.supabase.invalid'))
    app.state.verifier=w.app.state.verifier
    with TestClient(app) as c:
        h=w.headers()
        assert c.get('/v1/team',headers=h).json()['writesEnabled'] is False
        for method,path,body in [('POST','/v1/leads',{'empresa':'Synthetic'}),('PATCH','/v1/team/'+w.other,{'role':'admin'}),('DELETE','/v1/team/'+w.other,None)]:
            r=c.request(method,path,headers=h,json=body)
            assert r.status_code==403 and r.json()['code']=='WRITES_DISABLED'

def test_no_automatic_invitation_endpoint(workspace):
    w=workspace;provision(w)
    with TestClient(w.app) as c:
        # Invitations are deliberately operator-managed; no Admin API is installed.
        assert c.post('/v1/team/invitations',headers=w.headers(),json={'email':'synthetic@example.invalid'}).status_code==405

def test_concurrent_owners_cannot_remove_each_other(workspace):
    from concurrent.futures import ThreadPoolExecutor
    w=workspace;provision(w)
    with psycopg.connect(DSN) as db:
        db.execute("INSERT INTO organization_members(organization_id,user_id,role) VALUES(%s,%s,'owner')",(w.org,w.other))
    def demote(pair):
        actor,target=pair
        with TestClient(w.app) as c:
            return c.patch('/v1/team/'+target,headers={**w.headers(actor),'x-organization-id':w.org},json={'role':'admin'}).status_code
    with ThreadPoolExecutor(2) as pool:
        assert sorted(pool.map(demote,[(w.user,w.other),(w.other,w.user)]))==[200,403]
    with psycopg.connect(DSN) as db:
        assert db.execute("SELECT count(*) FROM organization_members WHERE organization_id=%s AND role='owner'",(w.org,)).fetchone()[0]==1

def test_team_audit_failure_rolls_back_role(workspace):
    w=workspace;provision(w)
    with psycopg.connect(DSN) as db:
        db.execute("INSERT INTO organization_members(organization_id,user_id,role) VALUES(%s,%s,'member')",(w.org,w.other))
        db.execute("""CREATE FUNCTION public.synthetic_fail_team_audit() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN IF NEW.action='organization_members.update' AND NEW.actor_id IS NOT NULL THEN
        RAISE EXCEPTION 'SYNTHETIC_PRIVATE_DETAIL'; END IF; RETURN NEW; END $$""")
        db.execute('CREATE TRIGGER synthetic_fail_team_audit BEFORE INSERT ON public.audit_events FOR EACH ROW EXECUTE FUNCTION public.synthetic_fail_team_audit()')
    try:
        with TestClient(w.app) as c:
            result=c.patch('/v1/team/'+w.other,headers=w.headers(),json={'role':'admin'})
            assert result.status_code==503
            assert 'SYNTHETIC_PRIVATE_DETAIL' not in result.text
        with psycopg.connect(DSN) as db:
            assert db.execute('SELECT role FROM organization_members WHERE organization_id=%s AND user_id=%s',(w.org,w.other)).fetchone()[0]=='member'
            assert db.execute("SELECT count(*) FROM audit_events WHERE organization_id=%s AND actor_id=%s",(w.org,w.user)).fetchone()[0]==0
    finally:
        with psycopg.connect(DSN) as db:
            db.execute('DROP TRIGGER synthetic_fail_team_audit ON public.audit_events')
            db.execute('DROP FUNCTION public.synthetic_fail_team_audit()')


def test_definer_owners_search_paths_and_effective_acl():
    functions=['team_roster()', 'manage_member(uuid,text,boolean)',
               'guard_membership()', 'audit_membership()']
    with psycopg.connect(DSN) as c:
        for name in functions:
            function='public.'+name
            owner,definer,config=c.execute('SELECT pg_get_userbyid(proowner),prosecdef,proconfig FROM pg_proc WHERE oid=%s::regprocedure',(function,)).fetchone()
            assert owner=='postgres' and definer and 'search_path=""' in config
            for role in ('anon','authenticated','service_role','synthetic_default_executor'):
                assert not c.execute('SELECT has_function_privilege(%s,%s,\'EXECUTE\')',(role,function)).fetchone()[0]
            allowed=name.startswith(('team_roster','manage_member'))
            assert c.execute('SELECT has_function_privilege(\'loung_api\',%s,\'EXECUTE\')',(function,)).fetchone()[0] is allowed
        assert c.execute("SELECT rolsuper,rolbypassrls,rolcreaterole FROM pg_roles WHERE rolname='loung_api'").fetchone()==(False,False,False)
        assert not c.execute("SELECT has_table_privilege('loung_api','organization_members','INSERT,UPDATE,DELETE,TRUNCATE')").fetchone()[0]
        assert not c.execute("SELECT has_table_privilege('loung_api','audit_events','INSERT')").fetchone()[0]


def test_roster_with_forged_org_missing_identity_and_hostile_search_path(workspace):
    import json
    w=workspace;provision(w)
    with psycopg.connect(DSN) as c:
        c.execute('CREATE TEMP TABLE organization_members(user_id uuid,role text)')
        c.execute("INSERT INTO organization_members VALUES(%s,'owner')",(w.user,))
        c.execute('SET LOCAL search_path=pg_temp,public')
        c.execute('SET LOCAL ROLE loung_api')
        for actor,org,expected in [(w.user,w.org,1),(w.user,w.org2,0),(None,w.org,0)]:
            c.execute("SELECT set_config('request.jwt.claims',%s,true),set_config('app.organization_id',%s,true)",(json.dumps({'sub':actor}),org))
            rows=c.execute('SELECT * FROM public.team_roster()').fetchall()
            assert len(rows)==expected
            if expected: assert str(rows[0][0])==w.user
            if not expected:
                result=capture(c,"SELECT public.manage_member('"+w.other+"','owner',false)")
                assert result['sqlstate']=='42501'
        assert capture(c,"SELECT public.guard_membership()")['sqlstate']=='42501'


@pytest.mark.parametrize('statement',[
    "UPDATE organization_members SET role='member' WHERE organization_id=%s",
    'DELETE FROM organization_members WHERE organization_id=%s',
])
def test_bulk_dml_cannot_remove_all_owners(workspace,statement):
    w=workspace;provision(w)
    with psycopg.connect(DSN) as c:
        c.execute("INSERT INTO organization_members(organization_id,user_id,role) VALUES(%s,%s,'owner')",(w.org,w.other))
        with pytest.raises(psycopg.errors.CheckViolation) as error:
            with c.transaction(): c.execute(statement,(w.org,))
        assert error.value.diag.constraint_name=='organization_last_owner'
        assert c.execute("SELECT count(*) FROM organization_members WHERE organization_id=%s AND role='owner'",(w.org,)).fetchone()[0]==2


def test_membership_identity_and_null_arguments(workspace):
    w=workspace;provision(w)
    with psycopg.connect(DSN) as c:
        for column,value in [('organization_id',w.org2),('user_id',w.other)]:
            with pytest.raises(psycopg.errors.CheckViolation):
                with c.transaction(): c.execute('UPDATE organization_members SET '+column+'=%s WHERE organization_id=%s AND user_id=%s',(value,w.org,w.user))
    c=Database(DSN).open(Identity(w.user,w.org,'owner'),'rw')
    try:
        assert capture(c,"SELECT public.manage_member(NULL,'owner',false)")['sqlstate']=='22023'
        assert capture(c,"SELECT public.manage_member('"+w.other+"','owner',NULL)")['sqlstate']=='22023'
    finally:c.close()


def test_migration_rejects_excess_runtime_privileges_atomically():
    migration=Path('supabase/migrations/202610200002_team_operations.sql').read_text(encoding='utf8')
    with psycopg.connect(DSN,autocommit=True) as c:
        for privilege in ('UPDATE','UPDATE(role)'):
            c.execute('BEGIN')
            c.execute('GRANT '+privilege+' ON organization_members TO loung_api')
            try:
                with pytest.raises(psycopg.errors.InsufficientPrivilege): c.execute(migration)
            finally:c.execute('ROLLBACK')
        assert not c.execute("SELECT has_table_privilege('loung_api','organization_members','UPDATE')").fetchone()[0]


def test_migration_detects_inherited_function_access():
    migration=Path('supabase/migrations/202610200002_team_operations.sql').read_text(encoding='utf8')
    postcondition='DO $$'+migration.rsplit('DO $$',1)[1].split('COMMIT;')[0]
    with psycopg.connect(DSN) as c:
        c.execute('SELECT 1')
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            with c.transaction():
                c.execute('GRANT loung_api TO authenticated')
                c.execute(postcondition)
        assert not c.execute("SELECT has_function_privilege('authenticated','public.team_roster()','EXECUTE')").fetchone()[0]


@pytest.mark.parametrize('isolation',['READ COMMITTED','REPEATABLE READ','SERIALIZABLE'])
@pytest.mark.parametrize('path',['update','delete','rpc'])
def test_native_mvcc_owner_concurrency(workspace,isolation,path):
    """Two real backends and pre-existing snapshots; WASM single-session is insufficient."""
    import json
    from concurrent.futures import ThreadPoolExecutor
    from time import monotonic,sleep
    w=workspace;provision(w)
    with psycopg.connect(DSN) as setup:
        if setup.execute("SELECT to_regclass('public.phase32_native_marker')").fetchone()[0] is None:
            pytest.skip('Requires isolated native PostgreSQL with phase32_native_marker')
        setup.execute("INSERT INTO organization_members(organization_id,user_id,role) VALUES(%s,%s,'owner')",(w.org,w.other))
    a=psycopg.connect(DSN,autocommit=True);b=psycopg.connect(DSN,autocommit=True)
    try:
        for c,actor in [(a,w.user),(b,w.other)]:
            c.execute('BEGIN ISOLATION LEVEL '+isolation)
            c.execute("SET LOCAL statement_timeout='8s'")
            if path=='rpc': c.execute('SET LOCAL ROLE loung_api')
            c.execute("SELECT set_config('request.jwt.claims',%s,true),set_config('app.organization_id',%s,true)",(json.dumps({'sub':actor}),w.org))
            c.execute('SELECT count(*) FROM public.organization_members').fetchone() # pin snapshot
        def change(c,actor,target):
            try:
                if path=='rpc': c.execute("SELECT public.manage_member(%s,'admin',false)",(target,))
                elif path=='update': c.execute("UPDATE public.organization_members SET role='admin' WHERE organization_id=%s AND user_id=%s",(w.org,actor))
                else: c.execute('DELETE FROM public.organization_members WHERE organization_id=%s AND user_id=%s',(w.org,actor))
                c.execute('COMMIT');return 'ok'
            except psycopg.Error as error:
                c.execute('ROLLBACK');return error.sqlstate
        # Leave A uncommitted so B actually waits on a lock, not just a stale snapshot.
        if path=='rpc': a.execute("SELECT public.manage_member(%s,'admin',false)",(w.other,))
        elif path=='update': a.execute("UPDATE public.organization_members SET role='admin' WHERE organization_id=%s AND user_id=%s",(w.org,w.user))
        else: a.execute('DELETE FROM public.organization_members WHERE organization_id=%s AND user_id=%s',(w.org,w.user))
        with ThreadPoolExecutor(1) as pool:
            pending=pool.submit(change,b,w.other,w.user)
            waiting=False;deadline=monotonic()+4
            with psycopg.connect(DSN,autocommit=True) as observer:
                while monotonic()<deadline:
                    waiting=observer.execute("SELECT wait_event_type='Lock' FROM pg_stat_activity WHERE pid=%s",(b.info.backend_pid,)).fetchone()[0]
                    if waiting:break
                    sleep(.02)
            a.execute('COMMIT')
            result=pending.result(timeout=10)
            assert waiting,'Second independent backend must overlap and wait'
        expected='42501' if path=='rpc' else '23514'
        assert result==(expected if isolation=='READ COMMITTED' else '40001')
        with psycopg.connect(DSN) as check:
            assert check.execute("SELECT count(*) FROM organization_members WHERE organization_id=%s AND role='owner'",(w.org,)).fetchone()[0]==1
    finally:
        a.close();b.close()
