"""Claims-based authorship migration: native disposable PostgreSQL only."""
import json
from pathlib import Path
import psycopg
from psycopg import sql
import pytest
from backend.config import Settings
from backend.main import create_app
from backend.scripts.check_phase32_readiness import inspect, claims_stamp_installed
from backend.tests.test_phase31_postgres import workspace, DSN
from backend.tests.test_phase32_writes import (
    test_owner_lead_pipeline_interaction_sdr_and_audit as run_owner_flow,
    test_audit_failure_rolls_back_business_and_all_children as run_rollback_flow,
)
from backend.tests.test_sdr_api import Provider

ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / 'supabase/migrations/202610220001_stamp_actor_from_verified_claims.sql'
RUNTIME_DSN = DSN.replace('postgres@', 'loung_web@')


def snapshot(c):
    tables = ('leads', 'lead_interactions', 'outreach', 'outreach_revisions', 'audit_events')
    return {
        'rows': [c.execute(sql.SQL('SELECT to_jsonb(t) FROM {} t ORDER BY to_jsonb(t)::text').format(sql.Identifier(table))).fetchall() for table in tables],
        'policies': c.execute('SELECT polrelid,polname,polcmd,polroles,polqual::text,polwithcheck::text FROM pg_policy ORDER BY polrelid,polname').fetchall(),
        'rls': c.execute("SELECT oid,relrowsecurity,relforcerowsecurity FROM pg_class WHERE relnamespace='public'::regnamespace ORDER BY oid").fetchall(),
        'triggers': c.execute('SELECT tgrelid,tgname,tgfoid,tgtype,tgenabled FROM pg_trigger WHERE NOT tgisinternal ORDER BY tgrelid,tgname').fetchall(),
        'schemas': c.execute("SELECT nspname,nspowner,nspacl FROM pg_namespace WHERE nspname IN ('public','auth','extensions') ORDER BY nspname").fetchall(),
        'stamp': c.execute("SELECT oid,proowner,proacl,prosecdef,proconfig,provolatile FROM pg_proc WHERE oid='public.stamp_actor()'::regprocedure").fetchone(),
    }


@pytest.fixture(scope='module', autouse=True)
def installed_claims_stamp():
    with psycopg.connect(DSN, autocommit=True, prepare_threshold=None) as c:
        assert c.execute('SELECT value FROM phase31_test_marker').fetchone()[0] == 'synthetic-memory-only'
        assert c.execute('SELECT value FROM phase32_native_marker').fetchone()[0] == 'native-disposable-cluster'
        if c.execute("SELECT to_regprocedure('public.team_roster()')").fetchone()[0] is None:
            c.execute('ALTER TABLE auth.users ADD COLUMN IF NOT EXISTS email text')
            c.execute((ROOT / 'supabase/migrations/202610200002_team_operations.sql').read_text(encoding='utf-8-sig'))
        if not c.execute("SELECT 1 FROM pg_roles WHERE rolname='loung_web'").fetchone():
            c.execute('CREATE ROLE loung_web LOGIN NOINHERIT NOBYPASSRLS')
        c.execute('GRANT loung_api TO loung_web')
        original = c.execute("SELECT prosrc FROM pg_proc WHERE oid='public.stamp_actor()'::regprocedure").fetchone()[0]
        usage = c.execute("SELECT has_schema_privilege('loung_api','auth','USAGE')").fetchone()[0]
        c.execute('REVOKE USAGE ON SCHEMA auth FROM loung_api')
        before = snapshot(c)
        c.execute(MIGRATION.read_text(encoding='utf8'))
        after = snapshot(c)
        c.execute(MIGRATION.read_text(encoding='utf8'))  # idempotent, no ACL/default-grant drift
        assert snapshot(c) == after == before
    yield
    with psycopg.connect(DSN, autocommit=True) as c:
        c.execute(sql.SQL("CREATE OR REPLACE FUNCTION public.stamp_actor() RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path='' AS {}").format(sql.Literal(original)))
        if usage:
            c.execute('GRANT USAGE ON SCHEMA auth TO loung_api')


@pytest.fixture
def claims_workspace(workspace, tmp_path):
    def forbidden():
        raise AssertionError('External provider forbidden')
    app = create_app(Settings(tmp_path / 'unused.db', True, 'postgres', RUNTIME_DSN,
                              'https://synthetic.supabase.invalid'),
                     sdr_provider_factory=Provider, provider_factory=forbidden)
    app.state.verifier = workspace.app.state.verifier
    workspace.app = app
    return workspace


def test_catalog_ready_without_auth_usage_or_new_definer():
    result = inspect(RUNTIME_DSN)
    assert result['readyByCatalog'], [check for check in result['checks'] if not check['passed']]
    auth = next(check for check in result['checks'] if check['check'] == 'schema_usage' and check['schema'] == 'auth')
    assert auth['actual'] is False and auth['required'] is False
    with psycopg.connect(DSN) as c:
        assert claims_stamp_installed(c)


def test_owner_full_flow_uses_restricted_login_and_claims(claims_workspace):
    run_owner_flow(claims_workspace)


@pytest.mark.parametrize('operation', ['create', 'edit', 'stage', 'interaction', 'sdr', 'sdr_revision'])
def test_rollback_with_claims_and_without_auth_usage(claims_workspace, operation):
    run_rollback_flow(claims_workspace, operation)


@pytest.mark.parametrize('claims', ['', '{}', '{"sub":""}', '{"sub":"not-a-uuid"}', '{"sub":'])
def test_missing_or_malformed_identity_cannot_write(claims_workspace, claims):
    w = claims_workspace
    with psycopg.connect(RUNTIME_DSN) as c:
        with pytest.raises(psycopg.Error) as error:
            with c.transaction():
                c.execute('SET LOCAL ROLE loung_api')
                c.execute("SELECT set_config('request.jwt.claims',%s,true),set_config('app.organization_id',%s,true)", (claims, w.org))
                c.execute("INSERT INTO leads(empresa,status) VALUES('SYNTHETIC invalid identity','Novo')")
        assert error.value.sqlstate in ('42501', '22P02')
    with psycopg.connect(DSN) as c:
        assert c.execute('SELECT count(*) FROM leads WHERE organization_id=%s', (w.org,)).fetchone()[0] == 0


def test_created_actor_cannot_be_forged_or_reassigned(claims_workspace):
    w = claims_workspace
    with psycopg.connect(RUNTIME_DSN) as c:
        c.execute('SET LOCAL ROLE loung_api')
        c.execute("SELECT set_config('request.jwt.claims',%s,true),set_config('app.organization_id',%s,true)", (json.dumps({'sub': w.user, 'role': 'authenticated'}), w.org))
        lead, creator, updater = c.execute("INSERT INTO leads(empresa,status,created_by,updated_by) VALUES('SYNTHETIC forged actor','Novo',%s,%s) RETURNING id,created_by,updated_by", (w.other, w.other)).fetchone()
        assert str(creator) == str(updater) == w.user
        creator, updater = c.execute('UPDATE leads SET created_by=%s,updated_by=%s WHERE id=%s RETURNING created_by,updated_by', (w.other, w.other, lead)).fetchone()
        assert str(creator) == str(updater) == w.user


def test_claim_role_does_not_authorize_another_organization(claims_workspace):
    w = claims_workspace
    with psycopg.connect(RUNTIME_DSN) as c:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            with c.transaction():
                c.execute('SET LOCAL ROLE loung_api')
                c.execute("SELECT set_config('request.jwt.claims',%s,true),set_config('app.organization_id',%s,true)", (json.dumps({'sub': w.user, 'role': 'service_role'}), w.org2))
                c.execute("INSERT INTO leads(empresa,status) VALUES('SYNTHETIC cross-org','Novo')")


@pytest.mark.parametrize('statement', [
    'SET LOCAL ROLE postgres',
    "UPDATE organization_members SET role='owner'",
    'SELECT * FROM auth.users',
    "INSERT INTO audit_events(organization_id,action,origin) VALUES(gen_random_uuid(),'forged','web')",
])
def test_restricted_login_cannot_escalate(statement):
    with psycopg.connect(RUNTIME_DSN) as c:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            with c.transaction():
                c.execute('SET LOCAL ROLE loung_api')
                c.execute(statement)


def test_readiness_rejects_unreviewed_body():
    with psycopg.connect(DSN) as c:
        body = c.execute("SELECT prosrc FROM pg_proc WHERE oid='public.stamp_actor()'::regprocedure").fetchone()[0]
        c.execute(sql.SQL("CREATE OR REPLACE FUNCTION public.stamp_actor() RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path='' AS {}").format(sql.Literal(body + '\n-- unreviewed change')))
        assert not claims_stamp_installed(c)
        c.rollback()


def test_migration_fails_closed_on_unexpected_execute_grant():
    with psycopg.connect(DSN, autocommit=True) as c:
        c.execute('BEGIN')
        c.execute('GRANT EXECUTE ON FUNCTION public.stamp_actor() TO loung_api')
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            c.execute(MIGRATION.read_text(encoding='utf8'))
        c.execute('ROLLBACK')
        assert not c.execute("SELECT has_function_privilege('loung_api','public.stamp_actor()','EXECUTE')").fetchone()[0]
