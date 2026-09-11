from contextlib import closing
from datetime import datetime, timezone
import sqlite3
from unittest.mock import Mock

import pytest

from core.database import LeadRepository, LeadNotFoundError, connect_database, initialize_database
from core.database import lead_repository


@pytest.fixture
def repo(tmp_path):
    return LeadRepository(tmp_path / "nested" / "test.db")


def test_schema_and_idempotence(repo):
    identity = repo.create_lead({"empresa": "Clínica"})
    initialize_database(repo.path)
    initialize_database(repo.path)
    assert repo.count_leads() == 1
    with closing(connect_database(repo.path)) as connection:
        assert connection.row_factory is sqlite3.Row
        columns = {row["name"] for row in connection.execute("PRAGMA table_info(leads)")}
        assert columns == set(lead_repository.FIELDS) | {"id", "created_at", "updated_at"}
    row = repo.get_lead(identity)
    assert row["empresa"] == "Clínica" and row["status"] == "Novo"
    assert row["telefone"] is row["qualification_score"] is None
    assert datetime.fromisoformat(row["created_at"]).utcoffset().total_seconds() == 0
    assert row["created_at"] == row["updated_at"]


def test_empty_and_missing(repo):
    assert repo.list_leads() == []
    assert repo.count_leads() == 0
    assert repo.get_lead(999) is None


def test_order_and_filters(repo):
    a = repo.create_lead(dict(empresa="A", segmento="dentista", responsavel="Ana", qualification_score=70))
    b = repo.create_lead(dict(empresa="B", segmento="dentista", qualification_score=70, status="Revisão"))
    c = repo.create_lead(dict(empresa="C", segmento="advogado", qualification_score=20))
    d = repo.create_lead(dict(empresa="D"))
    assert [r["id"] for r in repo.list_leads()] == [a, b, c, d]
    assert [r["id"] for r in repo.list_leads(status="Revisão")] == [b]
    assert [r["id"] for r in repo.list_leads(segmento="dentista")] == [a, b]
    assert [r["id"] for r in repo.list_leads(responsavel="Ana")] == [a]
    assert [r["id"] for r in repo.list_leads(score_minimo=50)] == [a, b]
    assert [r["id"] for r in repo.list_leads(segmento="dentista", status="Novo", responsavel="Ana", score_minimo=70)] == [a]
    assert [r["id"] for r in repo.list_leads(score_minimo=None)] == [d]
    assert [r["id"] for r in repo.list_leads(responsavel=None)] == [b, c, d]


@pytest.mark.parametrize("method,field,value", [("update_status", "status", "Em contato"),
    ("update_notes", "observacoes", "Revisar amanhã"), ("update_responsible", "responsavel", "José"),
    ("update_notes", "observacoes", None), ("update_responsible", "responsavel", None)])
def test_updates_and_timestamp(repo, monkeypatch, method, field, value):
    clock = Mock()
    clock.now.return_value = datetime(2026, 1, 1, tzinfo=timezone.utc)
    monkeypatch.setattr(lead_repository, "datetime", clock)
    identity = repo.create_lead({"empresa": "Empresa"})
    before = repo.get_lead(identity)
    clock.now.return_value = datetime(2026, 1, 2, tzinfo=timezone.utc)
    getattr(repo, method)(identity, value)
    after = repo.get_lead(identity)
    assert after[field] == value
    assert after["created_at"] == before["created_at"]
    assert after["updated_at"] != before["updated_at"]


def test_parameterized_strings_and_nonmutation(repo):
    payload = "D'Ávila'); DROP TABLE leads; --"
    data = dict(empresa=payload, segmento=payload, responsavel=payload)
    identity = repo.create_lead(data)
    assert dict(repo.get_lead(identity))["empresa"] == payload
    assert len(repo.list_leads(segmento=payload, responsavel=payload)) == 1
    assert repo.list_leads(status="' OR 1=1 --") == []
    repo.update_notes(identity, payload)
    assert repo.get_lead(identity)["observacoes"] == payload
    assert data == dict(empresa=payload, segmento=payload, responsavel=payload)


def test_constraint_failure_rollback(repo):
    identity = repo.create_lead({"empresa": "Preservada"})
    original = dict(repo.get_lead(identity))
    with pytest.raises(sqlite3.IntegrityError):
        repo.update_status(identity, None)
    with pytest.raises(sqlite3.IntegrityError):
        repo.create_lead({"empresa": None})
    assert repo.count_leads() == 1
    assert dict(repo.get_lead(identity)) == original
    repo.update_notes(identity, "Still works")


def test_connection_transaction_rolls_back(repo):
    with closing(connect_database(repo.path)) as connection:
        with pytest.raises(RuntimeError):
            with connection:
                connection.execute("INSERT INTO leads (empresa, created_at, updated_at) VALUES (?, ?, ?)", ("Temporary", "now", "now"))
                raise RuntimeError("Abort")
    assert repo.count_leads() == 0


def test_isolated_databases(repo, tmp_path):
    other = LeadRepository(tmp_path / "other.db")
    repo.create_lead({"empresa": "A"})
    assert other.count_leads() == 0
    assert repo.path.is_relative_to(tmp_path)


def test_missing_update_and_unknown_fields(repo):
    with pytest.raises(LeadNotFoundError):
        repo.update_status(123, "Novo")
    with pytest.raises(ValueError):
        repo.create_lead({"empresa": "A", "arbitrary_column": 1})
