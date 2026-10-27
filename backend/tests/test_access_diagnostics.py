"""Backend launch/access regression tests. All configuration and identities synthetic."""
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4
import psycopg
import pytest
from fastapi.testclient import TestClient
from backend.main import create_app
from backend.config import Settings
from backend.persistence.postgres import Database
from backend.persistence.errors import DatabaseAccessError,database_error_code
from backend.authorization import Identity
from backend.scripts.run_api import main


def test_launcher_passes_explicit_env_file_without_loading_desktop(monkeypatch,tmp_path):
    env=tmp_path/'server.env';env.write_text('SUPABASE_URL=https://synthetic.invalid\n',encoding='utf8')
    calls=[];monkeypatch.setattr('backend.scripts.run_api.uvicorn.run',lambda *a,**k:calls.append((a,k)))
    main(['--env-file',str(env),'--port','8123'])
    args,kwargs=calls[0]
    assert args==('backend.main:app',) and kwargs['env_file']==str(env.resolve())
    assert kwargs['host']=='127.0.0.1' and kwargs['port']==8123


def test_missing_configuration_fails_before_jwt_or_database(tmp_path):
    app=create_app(Settings(tmp_path/'unused',False,'postgres'))
    with TestClient(app) as client:
        health=client.get('/health').json()
        assert not health['configured'] and 'SUPABASE_URL' in health['missingConfiguration']
        response=client.get('/v1/session')
        assert response.status_code==503 and response.json()['code']=='BACKEND_NOT_CONFIGURED'
        assert client.get('/health',headers={'origin':'http://other.invalid'}).json()['code']=='BFF_REQUIRED'


def test_database_stage_classification_does_not_expose_driver_text(monkeypatch,tmp_path,caplog):
    secret='synthetic-sensitive-marker'
    def fail(*args,**kwargs):raise psycopg.OperationalError('failed to resolve host '+secret)
    monkeypatch.setattr('backend.persistence.postgres.psycopg.connect',fail)
    app=create_app(Settings(tmp_path/'unused',False,'postgres','synthetic-dsn','https://synthetic.invalid'))
    app.state.verifier=SimpleNamespace(verify=lambda _:str(uuid4()))
    with TestClient(app) as client:
        response=client.get('/v1/session',headers={'Authorization':'Bearer '+secret})
        assert response.status_code==503 and response.json()['code']=='DB_DNS_FAILED'
        assert secret not in response.text and secret not in caplog.text
        assert 'database_connect' in caplog.text


def test_set_role_failure_is_distinct_and_closes_connection(monkeypatch):
    class Connection:
        closed=False
        def execute(self,*args):raise psycopg.errors.InsufficientPrivilege('private-db-message')
        def close(self):self.closed=True
    connection=Connection()
    monkeypatch.setattr('backend.persistence.postgres.psycopg.connect',lambda *a,**k:connection)
    with pytest.raises(DatabaseAccessError) as error:Database('synthetic').open(Identity(str(uuid4())))
    assert error.value.stage=='runtime_role' and error.value.code=='DB_PERMISSION_DENIED'
    assert connection.closed


def test_temporary_membership_failure_recovers_without_disabling_auth(tmp_path,monkeypatch):
    app=create_app(Settings(tmp_path/'unused',False,'postgres','synthetic','https://synthetic.invalid'))
    user=str(uuid4());org=str(uuid4())
    app.state.verifier=SimpleNamespace(verify=lambda _:user)
    def unavailable(_):raise DatabaseAccessError('membership_query',psycopg.OperationalError())
    monkeypatch.setattr(app.state.database,'memberships',unavailable)
    with TestClient(app) as client:
        assert client.get('/v1/leads').status_code==503
        monkeypatch.setattr(app.state.database,'memberships',lambda _:[{'organization_id':org,'name':'Synthetic','role':'owner'}])
        # Session/profile query uses a separate reader; only inject that read boundary.
        class Result:
            def fetchone(self):return {'display_name':'Synthetic'}
        class Conn:
            columns={'leads':[]}
            def execute(self,*a):return Result()
            def close(self):pass
        monkeypatch.setattr(app.state.database,'connection',lambda *a,**k:Conn())
        response=client.get('/v1/session')
        assert response.status_code==200 and response.json()['organization']=='Synthetic'
        monkeypatch.setattr(app.state.database,'memberships',lambda _:[])
        response=client.get('/v1/session');assert response.status_code==403 and response.json()['code']=='MEMBERSHIP_REQUIRED'


def test_safe_permission_and_auth_failure_codes():
    assert database_error_code(psycopg.errors.InsufficientPrivilege('private'))=='DB_PERMISSION_DENIED'
    assert database_error_code(psycopg.errors.InvalidPassword('private'))=='DB_LOGIN_REJECTED'


def test_permission_diagnostics_are_allowlisted_and_ignore_sensitive_context():
    from backend.persistence.errors import permission_details
    sensitive='PRIVATE_CREDENTIAL'
    error=SimpleNamespace(sqlstate='42501',diag=SimpleNamespace(message_primary='permission denied for schema auth',context=sensitive))
    wrapped=DatabaseAccessError('membership_query',error,'session_memberships')
    assert wrapped.sqlstate=='42501' and wrapped.permission=={'object_type':'schema','object':'auth','privilege':'USAGE'}
    assert sensitive not in str(wrapped) and sensitive not in str(wrapped.permission)
    error.diag.message_primary='permission denied for schema '+sensitive
    assert permission_details(error)=={}


def test_query_diagnostic_survives_rollback_failure(monkeypatch):
    class Connection:
        def execute(self,*a):raise psycopg.errors.InsufficientPrivilege('not logged')
        def rollback(self):raise psycopg.OperationalError('cleanup not logged')
        def close(self):pass
    db=Database('synthetic')
    monkeypatch.setattr(db,'open',lambda *a,**k:Connection())
    with pytest.raises(DatabaseAccessError) as error:db.memberships(str(uuid4()))
    assert error.value.sqlstate=='42501' and error.value.statement_id=='session_memberships'

def test_session_probe_refuses_administrative_login_before_connect(monkeypatch,capsys):
    from backend.scripts.check_session_access import diagnose
    def forbidden(*args,**kwargs):raise AssertionError('Must not construct an administrative DB connection')
    monkeypatch.setattr('backend.scripts.check_session_access.Database',forbidden)
    assert not diagnose('postgresql://postgres:PRIVATE_MARKER@127.0.0.1/postgres',str(uuid4()))
    out=capsys.readouterr().out
    assert 'REFUSED_NON_RESTRICTED_LOGIN' in out and 'PRIVATE_MARKER' not in out
