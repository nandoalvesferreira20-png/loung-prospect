"""Niche filtering against isolated synthetic SQLite databases only."""
import hashlib
import sqlite3

from fastapi.testclient import TestClient

from backend.config import Settings
from backend.main import create_app
from backend.tests.test_api import database  # noqa: F401


def test_niches_filters_and_pagination(database):
    with sqlite3.connect(database) as connection:
        connection.executemany(
            "INSERT INTO leads (empresa,segmento,status,created_at,updated_at) VALUES (?,?,?,'2026-01-01','2026-01-01')",
            [("Synthetic Alpha", "Software", "Novo"),
             ("Synthetic Beta", "Software", "Contatado"),
             ("Synthetic Gamma", "Software", "Novo"),
             ("Synthetic Blank", "", "Novo"),
             ("Synthetic Spaces", " \t\n", "Novo"),
             ("Synthetic Exact", " Software ", "Novo"),
             ("Synthetic Quote", "' OR 1=1 --", "Novo")],
        )
    before = hashlib.sha256(database.read_bytes()).hexdigest()
    with TestClient(create_app(Settings(database))) as client:
        niches = client.get('/v1/lead-niches').json()
        assert len(niches) == len(set(niches))
        assert all(isinstance(niche, str) and niche.strip() for niche in niches)
        assert 'Software' in niches and ' Software ' in niches
        assert client.get('/v1/leads').json() == client.get('/v1/leads', params={'niche': ''}).json()
        assert client.get('/v1/leads').json()['total'] == 12  # Includes missing niches.
        first = client.get('/v1/leads', params={'niche': 'Software', 'pageSize': 2}).json()
        second = client.get('/v1/leads', params={'niche': 'Software', 'pageSize': 2, 'page': 2}).json()
        assert first['total'] == second['total'] == 3
        assert len(first['items']) == 2 and len(second['items']) == 1
        assert not {item['id'] for item in first['items']} & {item['id'] for item in second['items']}
        assert all(item['niche'] == 'Software' for item in first['items'] + second['items'])
        for filters, total in [({'q': 'beta'}, 1), ({'stage': 'Novo'}, 2),
                               ({'q': 'beta', 'stage': 'Novo'}, 0),
                               ({'q': 'beta', 'stage': 'Contato realizado'}, 1), ({'page': 999}, 3)]:
            result = client.get('/v1/leads', params={'niche': 'Software', **filters}).json()
            assert result['total'] == total
            if filters.get('page') == 999:
                assert result['items'] == []
        for niche, total in [('Inexistente', 0), ("' OR 1=1 --", 1), (' Software ', 1)]:
            assert client.get('/v1/leads', params={'niche': niche}).json()['total'] == total
    assert hashlib.sha256(database.read_bytes()).hexdigest() == before


def test_schema_without_niche(tmp_path):
    path = tmp_path / 'minimal.db'
    with sqlite3.connect(path) as connection:
        connection.execute('CREATE TABLE leads(id INTEGER PRIMARY KEY, empresa TEXT, status TEXT)')
        connection.execute("INSERT INTO leads VALUES(1,'Synthetic','Novo')")
    with TestClient(create_app(Settings(path))) as client:
        assert client.get('/v1/lead-niches').json() == []
        assert client.get('/v1/leads').json()['total'] == 1
        assert client.get('/v1/leads', params={'niche': 'Software'}).json()['total'] == 0
