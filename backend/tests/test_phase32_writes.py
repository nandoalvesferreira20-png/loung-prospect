"""Write homologation: fixed disposable PostgreSQL and synthetic identities only."""
from uuid import uuid4
import psycopg
from psycopg import sql
import pytest
from fastapi.testclient import TestClient
from backend.tests.test_phase31_postgres import workspace, DSN
from backend.config import Settings
from backend.main import create_app
from backend.scripts.check_phase32_readiness import inspect


def make_owner(w):
    with psycopg.connect(DSN) as c:
        assert c.execute('SELECT value FROM phase31_test_marker').fetchone()[0] == 'synthetic-memory-only'
        c.execute("UPDATE organization_members SET role='owner' WHERE user_id=%s AND organization_id=%s", (w.user, w.org))


def snapshot(w):
    with psycopg.connect(DSN) as c:
        return {table: c.execute(sql.SQL('SELECT to_jsonb(t) FROM {} t WHERE organization_id=%s ORDER BY id').format(sql.Identifier(table)), (w.org,)).fetchall()
                for table in ('leads', 'lead_interactions', 'outreach', 'outreach_revisions', 'audit_events')}


def test_owner_lead_pipeline_interaction_sdr_and_audit(workspace):
    w = workspace
    make_owner(w)
    with TestClient(w.app) as client:
        h = w.headers()
        result = client.post('/v1/leads', headers=h, json={'empresa': 'SYNTHETIC homologation', 'telefone': '11999991234'})
        assert result.status_code == 201
        lead = client.get('/v1/leads', headers=h).json()['items'][0]['id']
        fields = client.get(f'/v1/leads/{lead}/edit', headers=h).json()
        result = client.patch(f'/v1/leads/{lead}', headers=h, json={**fields['fields'], 'observacoes': 'SYNTHETIC only', 'revision': fields['revision']})
        assert result.status_code == 200
        result = client.patch(f'/v1/leads/{lead}/stage', headers=h, json={'revision': result.json()['revision'], 'stage': 'Em conversa'})
        assert result.status_code == 200
        result = client.post(f'/v1/leads/{lead}/activities', headers=h, json={'revision': result.json()['revision'], 'kind': 'Observação', 'description': 'SYNTHETIC interaction', 'channel': 'outro'})
        assert result.status_code == 200
        draft = client.post('/v1/sdr/generate', headers=h, json={'leadId': lead, 'requestId': str(uuid4())})
        assert draft.status_code == 200
        body = {'draftId': draft.json()['draftId'], 'message': draft.json()['message'], 'status': 'EDITADA'}
        saved = client.post('/v1/sdr/history', headers=h, json=body)
        assert saved.status_code == 200
        assert client.post('/v1/sdr/history', headers=h, json=body).json()['id'] == saved.json()['id']
        assert client.post('/v1/sdr/history', headers=h, json={**body, 'message': body['message'] + ' Revisão sintética.'}).status_code == 200
        assert client.get(f'/v1/crm/leads/{lead}', headers=w.headers(w.other)).status_code == 404
        assert client.get(f'/v1/sdr/history/{lead}', headers=w.headers(w.other)).status_code == 404
        assert client.get('/v1/pipeline', headers=h).status_code == 200
        events = client.get('/v1/organization/activities', headers=h)
        assert events.status_code == 200
        assert all(item['actor_id'] == w.user for item in events.json()['items'] if item['origin'] == 'web')
    state = snapshot(w)
    assert len(state['leads']) == 1 and len(state['lead_interactions']) == 2  # stage + explicit observation
    assert len(state['outreach']) == 1 and len(state['outreach_revisions']) == 1
    assert all(row[0]['created_by'] == w.user and row[0]['updated_by'] == w.user for table in ('leads', 'lead_interactions', 'outreach', 'outreach_revisions') for row in state[table])
    assert all(row[0]['organization_id'] == w.org for rows in state.values() for row in rows)
    assert all(row[0]['actor_id'] == w.user for row in state['audit_events'] if row[0]['origin'] == 'web')


@pytest.mark.parametrize('operation', ['create', 'edit', 'stage', 'interaction', 'sdr', 'sdr_revision'])
def test_audit_failure_rolls_back_business_and_all_children(workspace, operation):
    w = workspace
    make_owner(w)
    w.seed()
    with TestClient(w.app) as client:
        h = w.headers()
        lead = client.get('/v1/leads', headers=h).json()['items'][0]['id']
        fields = client.get(f'/v1/leads/{lead}/edit', headers=h).json()
        draft = client.post('/v1/sdr/generate', headers=h, json={'leadId': lead, 'requestId': str(uuid4())}).json()
        if operation == 'sdr_revision':
            assert client.post('/v1/sdr/history', headers=h, json={'draftId': draft['draftId'], 'message': draft['message'], 'status': 'EDITADA'}).status_code == 200
        before = snapshot(w)
        with psycopg.connect(DSN) as c:
            c.execute(sql.SQL("CREATE FUNCTION public.synthetic_homologation_failure() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN IF NEW.organization_id={}::uuid THEN RAISE EXCEPTION 'SYNTHETIC_PRIVATE_FAILURE'; END IF; RETURN NEW; END $$").format(sql.Literal(w.org)))
            c.execute('CREATE TRIGGER synthetic_homologation_failure BEFORE INSERT ON public.audit_events FOR EACH ROW EXECUTE FUNCTION public.synthetic_homologation_failure()')
        try:
            if operation == 'create':
                result = client.post('/v1/leads', headers=h, json={'empresa': 'SYNTHETIC rollback new lead'})
            elif operation == 'edit':
                result = client.patch(f'/v1/leads/{lead}', headers=h, json={**fields['fields'], 'observacoes': 'rollback', 'revision': fields['revision']})
            elif operation == 'stage':
                result = client.patch(f'/v1/leads/{lead}/stage', headers=h, json={'stage': 'Em conversa', 'revision': fields['revision']})
            elif operation == 'interaction':
                result = client.post(f'/v1/leads/{lead}/activities', headers=h, json={'kind': 'Observação', 'description': 'rollback', 'channel': 'outro', 'revision': fields['revision']})
            else:
                result = client.post('/v1/sdr/history', headers=h, json={'draftId': draft['draftId'], 'message': draft['message'] + ' Revisão sintética.', 'status': 'EDITADA'})
            assert result.status_code == 503
            assert 'SYNTHETIC_PRIVATE_FAILURE' not in result.text
            assert snapshot(w) == before
        finally:
            with psycopg.connect(DSN) as c:
                c.execute('DROP TRIGGER synthetic_homologation_failure ON public.audit_events')
                c.execute('DROP FUNCTION public.synthetic_homologation_failure()')


def test_disabled_writes_block_all_operations_before_provider(workspace, tmp_path):
    w = workspace
    make_owner(w)
    calls = []

    def forbidden_provider():
        calls.append(True)
        raise AssertionError('Provider must not run')

    app = create_app(Settings(tmp_path / 'unused.db', False, 'postgres', DSN, 'https://synthetic.supabase.invalid'), sdr_provider_factory=forbidden_provider)
    app.state.verifier = w.app.state.verifier
    before = snapshot(w)
    with TestClient(app) as client:
        for method, path in [('POST', '/v1/leads'), ('PATCH', '/v1/leads/1'), ('PATCH', '/v1/leads/1/stage'),
                             ('POST', '/v1/leads/1/activities'), ('POST', '/v1/leads/1/followups'),
                             ('PATCH', '/v1/followups/1'), ('POST', '/v1/sdr/generate'), ('POST', '/v1/sdr/history')]:
            response = client.request(method, path, headers=w.headers(), json={})
            assert response.status_code == 403 and response.json()['code'] == 'WRITES_DISABLED'
    assert not calls and snapshot(w) == before


def test_readiness_rejects_admin_before_connecting(monkeypatch):
    monkeypatch.setattr(psycopg, 'connect', lambda *a, **k: pytest.fail('Must not connect with administrative login'))
    with pytest.raises(ValueError, match='RESTRICTED_LOGIN_REQUIRED'):
        inspect('postgresql://postgres@127.0.0.1:55431/postgres')


def test_missing_auth_schema_usage_blocks_writes_while_session_still_works(workspace):
    """Reproduce the catalog drift found in real DB, exclusively in disposable DB."""
    w = workspace
    make_owner(w)
    before = snapshot(w)
    with psycopg.connect(DSN) as c:
        c.execute('REVOKE USAGE ON SCHEMA auth FROM loung_api')
    try:
        with TestClient(w.app) as client:
            assert client.get('/v1/session', headers=w.headers()).status_code == 200
            response = client.post('/v1/leads', headers=w.headers(), json={'empresa': 'SYNTHETIC auth usage regression'})
            assert response.status_code == 503
            assert response.json()['code'] == 'DB_PERMISSION_DENIED'
            assert snapshot(w) == before
    finally:
        with psycopg.connect(DSN) as c:
            c.execute('GRANT USAGE ON SCHEMA auth TO loung_api')
    with TestClient(w.app) as client:
        assert client.post('/v1/leads', headers=w.headers(), json={'empresa': 'SYNTHETIC auth usage regression'}).status_code == 201
