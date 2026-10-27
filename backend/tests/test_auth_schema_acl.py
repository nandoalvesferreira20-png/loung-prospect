"""Reproduce auth ACL drift in the fixed in-memory PostgreSQL test server only."""
import json
from pathlib import Path
from types import SimpleNamespace
import psycopg
from psycopg import sql
from fastapi.testclient import TestClient
import pytest
from backend.persistence.errors import permission_details
from backend.tests.test_phase31_postgres import workspace,DSN

PATCH=Path(__file__).resolve().parents[2]/'supabase/migrations/202610200001_repair_auth_schema_usage.sql'


def repair():
    with psycopg.connect(DSN,prepare_threshold=None) as c:
        assert c.execute('SELECT value FROM phase31_test_marker').fetchone()[0]=='synthetic-memory-only'
        c.execute(PATCH.read_text(encoding='utf-8-sig'))


@pytest.fixture(autouse=True)
def restore_acl():
    try:repair()
    except psycopg.OperationalError:pytest.skip('Start synthetic PostgreSQL test server')
    yield
    repair()
    with psycopg.connect(DSN,prepare_threshold=None) as c:c.execute('GRANT SELECT ON public.organization_members TO loung_api')


def capture(c,query):
    notices=[]
    def notice(d):
        if d.message_primary.startswith('{'):notices.append(json.loads(d.message_primary))
    c.add_notice_handler(notice)
    try:
        block=sql.SQL("""DO $capture$
        DECLARE s text; m text;
        BEGIN
          EXECUTE {};
          RAISE NOTICE '%', json_build_object('ok',true)::text;
        EXCEPTION WHEN OTHERS THEN
          GET STACKED DIAGNOSTICS s=RETURNED_SQLSTATE,m=MESSAGE_TEXT;
          RAISE NOTICE '%',json_build_object('ok',false,'sqlstate',s,'message_primary',m)::text;
        END $capture$;""").format(sql.Literal(query))
        c.execute(block)
        return notices[-1]
    finally:c.remove_notice_handler(notice)


def test_missing_schema_usage_direct_uid_and_actual_session_are_distinct(workspace):
    w=workspace
    with psycopg.connect(DSN,prepare_threshold=None) as c:
        c.execute('REVOKE USAGE ON SCHEMA auth FROM loung_api')
        assert not c.execute("SELECT has_schema_privilege('loung_api','auth','USAGE')").fetchone()[0]
    with psycopg.connect(DSN,prepare_threshold=None) as c:
        c.execute('SET LOCAL ROLE loung_api')
        result=capture(c,'SELECT auth.uid()')
        assert result['sqlstate']=='42501'
        details=permission_details(SimpleNamespace(sqlstate=result['sqlstate'],diag=SimpleNamespace(message_primary=result['message_primary'])))
        assert details=={'object_type':'schema','object':'auth','privilege':'USAGE'}
    # Important counterexample: stored RLS OIDs + SECURITY DEFINER helper can
    # resolve a session without schema name lookup in the caller's context.
    with TestClient(w.app) as client:
        r=client.get('/v1/session',headers=w.headers())
        assert r.status_code==200,r.text
    repair()
    with psycopg.connect(DSN,prepare_threshold=None) as c:
        c.execute('SET LOCAL ROLE loung_api')
        assert capture(c,'SELECT auth.uid()')['ok']
        assert not c.execute("SELECT has_schema_privilege('loung_api','auth','CREATE')").fetchone()[0]
        assert not c.execute("SELECT has_table_privilege('loung_api','auth.users','SELECT')").fetchone()[0]


def test_real_statement_id_is_captured_for_membership_select(workspace,caplog):
    w=workspace
    with psycopg.connect(DSN,prepare_threshold=None) as c:c.execute('REVOKE SELECT ON public.organization_members FROM loung_api')
    with TestClient(w.app) as client:
        r=client.get('/v1/session',headers=w.headers())
        assert r.status_code==503 and r.json()['code']=='DB_PERMISSION_DENIED'
    assert 'statement=session_memberships' in caplog.text
    assert 'sqlstate=42501' in caplog.text
    assert 'public.organization_members' in caplog.text and 'SELECT' in caplog.text
    assert w.user not in caplog.text
    with psycopg.connect(DSN,prepare_threshold=None) as c:c.execute('GRANT SELECT ON public.organization_members TO loung_api')
    with TestClient(w.app) as client:assert client.get('/v1/session',headers=w.headers()).status_code==200


def test_incremental_grant_does_not_expand_tenant_access(workspace):
    w=workspace;w.seed();w.seed(w.org2,w.other)
    repair();repair() # Idempotent.
    with TestClient(w.app) as client:
        assert client.get('/v1/session',headers=w.headers()).status_code==200
        lead=client.get('/v1/leads',headers=w.headers()).json()['items'][0]['id']
        assert client.get(f'/v1/crm/leads/{lead}',headers=w.headers(w.other)).status_code==404
        assert client.get('/v1/leads',headers={**w.headers(w.other),'x-organization-id':w.org}).status_code==403
    with psycopg.connect(DSN,prepare_threshold=None) as c:
        assert c.execute("SELECT NOT rolsuper AND NOT rolbypassrls FROM pg_roles WHERE rolname='loung_api'").fetchone()[0]
        assert c.execute("SELECT relrowsecurity AND relforcerowsecurity FROM pg_class WHERE oid='public.leads'::regclass").fetchone()[0]


def test_grant_cannot_report_success_without_effective_privilege():
    with psycopg.connect(DSN,prepare_threshold=None) as c:
        c.execute("DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM pg_roles WHERE rolname='acl_test_grantor') THEN CREATE ROLE acl_test_grantor NOLOGIN; END IF; END $$")
        c.execute('GRANT USAGE ON SCHEMA auth TO acl_test_grantor')
        c.execute('REVOKE USAGE ON SCHEMA auth FROM loung_api')
    body=PATCH.read_text(encoding='utf-8-sig').replace('BEGIN;','',1).rsplit('COMMIT;',1)[0]
    with psycopg.connect(DSN,prepare_threshold=None) as c:
        c.execute('SET LOCAL ROLE acl_test_grantor')
        # Capture the migration's postcondition error, not only the GRANT warning.
        result=capture(c,body)
        assert result['sqlstate']=='42501'
        assert not c.execute("SELECT has_schema_privilege('loung_api','auth','USAGE')").fetchone()[0]
