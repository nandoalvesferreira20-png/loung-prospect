import hashlib
import sqlite3

import pytest
from fastapi.testclient import TestClient

from backend.config import Settings
from backend.main import create_app
from core.database.schema import initialize_database

URL = '/v1/integrations/sales-ai/leads'
TOKEN = 'synthetic-sales-ai-token-for-tests-only'
HEADERS = {'Authorization': f'Bearer {TOKEN}'}


@pytest.fixture
def database(tmp_path):
    path = tmp_path / 'sales.db'
    initialize_database(path)
    with sqlite3.connect(path) as c:
        c.executemany("INSERT INTO leads (id,empresa,segmento,cidade,site,observacoes,telefone,created_at,updated_at) VALUES (?,?,?,?,?,?,?,'2026','2026')", [
            (7, 'Clínica Árvore', 'Saúde', 'São Paulo', 'https://example.org', 'Revisão humana', 'private'),
            (19, 'Loja', 'Varejo', None, None, None, 'private'),
            (42, 'Clínica Dois', 'Saúde', '', '', '', 'private'),
        ])
    return path


def test_serialization_selection_and_no_writes(database):
    before = hashlib.sha256(database.read_bytes()).digest()
    with TestClient(create_app(Settings(database, sales_ai_token=TOKEN))) as client:
        response = client.get(URL, headers=HEADERS, params={'lead_id': 7})
        assert response.status_code == 200
        assert response.headers['cache-control'] == 'no-store'
        assert response.json() == {'items': [{'lead_id': 7, 'nome': 'Clínica Árvore', 'nicho': 'Saúde', 'cidade': 'São Paulo', 'site': 'https://example.org', 'observacoes': 'Revisão humana'}], 'next_after_id': None}
        assert client.get(URL, headers=HEADERS, params={'lead_id': 19}).json()['items'][0]['observacoes'] is None
        for method in ('post', 'put', 'patch', 'delete'):
            assert getattr(client, method)(URL, headers=HEADERS).status_code == 405
    assert hashlib.sha256(database.read_bytes()).digest() == before


@pytest.mark.parametrize('headers', [{}, {'Authorization': 'Bearer wrong'}, {'Authorization': f'Basic {TOKEN}'}, {'Authorization': 'Bearer'}])
def test_authentication(database, headers):
    with TestClient(create_app(Settings(database, sales_ai_token=TOKEN))) as client:
        assert client.get(URL, headers=headers).status_code == 401


def test_disabled_and_invalid_configuration(database):
    with TestClient(create_app(Settings(database))) as client:
        assert client.get(URL, headers=HEADERS).status_code == 503
    with pytest.raises(ValueError):
        create_app(Settings(database, sales_ai_token='short'))


def test_filters_and_cursor(database):
    with TestClient(create_app(Settings(database, sales_ai_token=TOKEN))) as client:
        first = client.get(URL, headers=HEADERS, params={'nicho': 'Saúde', 'limit': 1}).json()
        assert first['items'][0]['lead_id'] == 7 and first['next_after_id'] == 7
        second = client.get(URL, headers=HEADERS, params={'nicho': 'Saúde', 'limit': 1, 'after_id': 7}).json()
        assert second['items'][0]['lead_id'] == 42 and second['next_after_id'] is None
        assert client.get(URL, headers=HEADERS, params={'after_id': 42}).json()['items'] == []
        for niche in ('missing', "' OR 1=1 --"):
            assert client.get(URL, headers=HEADERS, params={'nicho': niche}).json()['items'] == []
        selected = client.get(URL, headers=HEADERS, params=[('lead_id', 7), ('lead_id', 42)]).json()
        assert [item['lead_id'] for item in selected['items']] == [7, 42]
        for params in ({'limit': 0}, {'limit': 101}, {'after_id': -1}, {'lead_id': -1}, {'lead_id': 2**63}, {'lead_id': [7]*101}):
            assert client.get(URL, headers=HEADERS, params=params).status_code == 422
        for headers in ({'Origin': 'https://external.test'}, {'X-Forwarded-For': '127.0.0.1'}):
            assert client.get(URL, headers={**HEADERS, **headers}).status_code == 403
    with TestClient(create_app(Settings(database, sales_ai_token=TOKEN)), client=('192.168.1.2', 1234)) as client:
        assert client.get(URL, headers=HEADERS).status_code == 403


def test_legacy_schema_and_unavailable_database(tmp_path):
    path = tmp_path / 'legacy.db'
    with sqlite3.connect(path) as c:
        c.execute('CREATE TABLE leads (id INTEGER PRIMARY KEY, empresa TEXT, status TEXT)')
        c.execute("INSERT INTO leads VALUES (123, 'Legado', 'Novo')")
    with TestClient(create_app(Settings(path, sales_ai_token=TOKEN))) as client:
        payload = client.get(URL, headers=HEADERS).json()
        assert payload['items'] == [{'lead_id': 123, 'nome': 'Legado', 'nicho': None, 'cidade': None, 'site': None, 'observacoes': None}]
        assert client.get(URL, headers=HEADERS, params={'nicho': 'Saúde'}).json()['items'] == []
    missing = tmp_path / 'missing.db'
    with TestClient(create_app(Settings(missing, sales_ai_token=TOKEN))) as client:
        assert client.get(URL, headers=HEADERS).status_code == 503
    assert not missing.exists()
