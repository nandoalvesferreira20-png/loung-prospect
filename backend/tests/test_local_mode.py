"""Local startup and persistence never use the operator's database or credentials."""
from contextlib import closing
import sqlite3
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from backend.config import Settings, CLOUD_MARKERS
from backend.local_database import initialize_local_database
from backend.main import create_app
from backend.tests.test_sdr_api import Provider
from core.database.schema import initialize_database


@pytest.fixture
def local_settings(tmp_path, monkeypatch):
    for name in (*CLOUD_MARKERS, 'LOUNG_AUTH_MODE', 'LOUNG_STORAGE_BACKEND', 'SUPABASE_URL', 'SUPABASE_AUTH_AUDIENCE', 'LOUNG_POSTGRES_DSN', 'LOUNG_ENABLE_WRITES'):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv('LOUNG_DATABASE_PATH', str(tmp_path / 'local.db'))
    return Settings.from_environment()


def test_local_startup_crud_restart_and_preferences(local_settings):
    assert local_settings.storage_backend == 'sqlite' and local_settings.writes_enabled
    assert not local_settings.database_path.exists()  # Import/config never writes.
    with TestClient(create_app(local_settings)) as client:
        assert client.get('/v1/session').json()['role'] == 'local'
        assert client.get('/v1/leads').json()['total'] == 0
        body = {'empresa':'Synthetic company', 'telefone':'11999990000'}
        assert client.post('/v1/leads', json=body).json()['inserted'] == 1
        assert client.post('/v1/leads', json=body).json()['duplicates'] == 1
        edit = client.get('/v1/leads/1/edit').json()
        mutation = {**edit['fields'], 'observacoes':'Synthetic notes', 'revision':edit['revision']}
        mutation['cidade'] = 'Synthetic city'
        assert client.patch('/v1/leads/1',json=mutation).status_code == 200
        assert client.patch('/v1/leads/1',json=mutation).status_code == 409
        assert client.put('/v1/local/preferences',json={'values':{'displayName':'Synthetic user','startPage':'/pipeline'}}).status_code == 200
    with TestClient(create_app(local_settings)) as client:
        assert client.get('/v1/leads').json()['total'] == 1
        assert client.get('/v1/leads/1/edit').json()['observacoes'] == 'Synthetic notes'
        assert client.get('/v1/local/preferences').json()['values']['startPage'] == '/pipeline'
        assert client.get('/v1/dashboard/commercial').status_code != 500
        assert client.get('/v1/pipeline').json()['total'] == 1


def test_local_sdr_pipeline_followups_restart(local_settings):
    with TestClient(create_app(local_settings, sdr_provider_factory=Provider)) as client:
        client.post('/v1/leads',json={'empresa':'Synthetic company','telefone':'11999990000'})
        draft = client.post('/v1/sdr/generate', json={'leadId':1,'requestId':str(uuid4())}).json()
        assert client.post('/v1/sdr/history',json={'draftId':draft['draftId'],'message':draft['message'],'status':'EDITADA'}).status_code == 200
        lead = client.get('/v1/crm/leads/1').json()['lead']
        assert client.patch('/v1/leads/1/stage',json={'stage':'Contato realizado','confirmed':True,'revision':lead['revision']}).status_code == 200
        lead = client.get('/v1/crm/leads/1').json()['lead']
        assert client.post('/v1/leads/1/followups',json={'dueAt':'2027-01-01T12:00:00Z','note':'Synthetic followup','revision':lead['revision']}).status_code == 200
    with TestClient(create_app(local_settings)) as client:
        assert len(client.get('/v1/sdr/history/1').json()['items']) == 1
        lead = client.get('/v1/crm/leads/1').json()['lead']
        assert lead['stage'] == 'Contato realizado' and lead['nextAction'] == 'Synthetic followup'


def test_existing_sqlite_migration_preserves_rows_and_backup(tmp_path):
    path = tmp_path / 'legacy.db'
    initialize_database(path)
    with sqlite3.connect(path) as c:
        c.execute("INSERT INTO leads (empresa,status,created_at,updated_at) VALUES ('Synthetic legacy','Novo','2026','2026')")
    with closing(sqlite3.connect(path)) as c:
        before = list(c.iterdump())
    initialize_local_database(path)
    backups = list((path.parent/'backups').glob('*.db'))
    assert len(backups) == 1
    with closing(sqlite3.connect(backups[0])) as c:
        assert list(c.iterdump()) == before
    initialize_local_database(path)
    assert len(list((path.parent/'backups').glob('*.db'))) == 1
    with sqlite3.connect(path) as c:
        assert c.execute('SELECT empresa FROM leads').fetchone()[0] == 'Synthetic legacy'
        assert c.execute('PRAGMA user_version').fetchone()[0] == 1
        with pytest.raises(sqlite3.IntegrityError):
            c.execute("INSERT INTO lead_interactions (lead_id,tipo,created_at) VALUES (999,'invalid','2026')")


@pytest.mark.parametrize('headers', [{'origin':'https://external.test'}, {'host':'external.test'}, {'x-forwarded-for':'127.0.0.1'}, {'sec-fetch-site':'cross-site'}])
def test_local_rejects_external_requests(local_settings, headers):
    with TestClient(create_app(local_settings)) as client:
        assert client.get('/v1/leads',headers=headers).status_code in (400,403)


def test_local_rejects_remote_peer(local_settings):
    with TestClient(create_app(local_settings),client=('192.168.1.22',4567)) as client:
        assert client.get('/v1/leads',headers={'host':'127.0.0.1'}).status_code == 403


@pytest.mark.parametrize('values', [
    {'LOUNG_AUTH_MODE':'typo'}, {'LOUNG_STORAGE_BACKEND':'postgres'},
    {'LOUNG_POSTGRES_DSN':'postgresql://synthetic.invalid/test'},
    {'LOUNG_AUTH_MODE':'saas','LOUNG_STORAGE_BACKEND':'sqlite'}, {'VERCEL':'1'},
])
def test_fail_closed_mode_configuration(local_settings, monkeypatch, values):
    for key,value in values.items(): monkeypatch.setenv(key,value)
    with pytest.raises(ValueError): Settings.from_environment()
