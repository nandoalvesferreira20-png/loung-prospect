from datetime import date, datetime, timedelta, timezone
import hashlib
import sqlite3
import pytest
from fastapi.testclient import TestClient

from backend.config import Settings
from backend.main import create_app
from backend.repository import ReadRepository
from core.database.schema import initialize_database


@pytest.fixture
def database(tmp_path):
    path = tmp_path / "synthetic.db"
    initialize_database(path)
    reference = date.today()
    today = datetime.combine(reference, datetime.min.time(), tzinfo=timezone.utc).replace(hour=15).isoformat()
    yesterday = (datetime.combine(reference, datetime.min.time(), tzinfo=timezone.utc) - timedelta(days=1)).replace(hour=15).isoformat()
    records = [
        ("Teste Clínica Árvore", "Clínica odontológica", "Reunião marcada", "(11) 99999-1234", 95, yesterday),
        ("Teste Corretor", "Corretor autônomo", "Contatado", None, 80, today),
        ("Teste Legado", None, "Etapa personalizada", None, None, "data inválida"),
        ("Teste Encerrado", "Desconhecido", "Fechado", None, 40, yesterday),
        ("Teste Rascunho", None, "Mensagem gerada", None, None, None),
    ]
    with sqlite3.connect(path) as connection:
        connection.executemany("INSERT INTO leads (empresa,segmento,status,telefone,qualification_score,proximo_contato,cidade,created_at,updated_at) VALUES (?,?,?,?,?,?,'São Paulo','2026-01-01','2026-01-01')", records)
        connection.execute("INSERT INTO lead_contact_preferences VALUES (1,'contato_direto','2026-01-01')")
    return path


@pytest.fixture
def client(database):
    with TestClient(create_app(Settings(database))) as value:
        yield value


def test_mapping_and_manual_role_preserves_original(client):
    payload = client.get("/v1/leads").json()
    assert payload["total"] == 5
    assert payload["pageSize"] == 20
    lead = payload["items"][0]
    assert lead["company"] == "Teste Clínica Árvore"
    assert lead["phone"] == "(11) 99999-1234"
    assert lead["stage"] == "Reunião agendada"
    assert lead["originalStage"] == "Reunião marcada"
    assert lead["contactRole"] == "direct"  # Explicit preference beats niche.
    assert "Etapa personalizada" in payload["stages"]
    assert "Não contatar" in payload["stages"]
    assert client.get("/v1/leads/2").json()["contactRole"] == "direct"
    assert client.get("/v1/leads/3").json()["contactRole"] == "unknown"


def test_search_accents_phone_pagination_and_alias_filter(client):
    assert client.get("/v1/leads", params={"q":"CLINICA ARVORE"}).json()["total"] == 1
    assert client.get("/v1/leads", params={"q":"11999991234"}).json()["total"] == 1
    assert client.get("/v1/leads", params={"q":"sao paulo"}).json()["total"] == 5
    assert client.get("/v1/leads", params={"stage":"Contato realizado"}).json()["items"][0]["originalStage"] == "Contatado"
    assert client.get("/v1/leads", params={"stage":"Reunião"}).json()["total"] == 1
    first = client.get("/v1/leads", params={"pageSize":2}).json()
    second = client.get("/v1/leads", params={"pageSize":2,"page":2}).json()
    assert not {lead["id"] for lead in first["items"]} & {lead["id"] for lead in second["items"]}
    assert second["total"] == 5
    assert client.get("/v1/leads", params={"page":999}).json()["items"] == []
    assert client.get("/v1/leads", params={"q":"' OR 1=1 --"}).json()["total"] == 0
    assert client.get("/v1/leads", params={"q":"%"}).json()["total"] == 0


@pytest.mark.parametrize("params", [{"page":0},{"pageSize":101},{"page":"x"},{"q":"x"*201}])
def test_invalid_query(client, params):
    assert client.get("/v1/leads",params=params).status_code == 422


def test_overview_matches_day_rules_and_not_generated_drafts(client):
    response = client.get("/v1/overview")
    assert response.status_code == 200
    overview = response.json()
    assert (overview["total"],overview["today"],overview["overdue"],overview["meetings"]) == (5,1,1,1)
    assert overview["invalidDates"] == 1
    assert overview["referenceDate"] == date.today().isoformat()
    assert sum(item["count"] for item in overview["stageCounts"]) == 5
    meeting = next(lead for lead in overview["actions"] if lead["id"] == 1)
    assert meeting["originalStage"] == "Reunião marcada"


def test_no_writes_even_schema_or_timestamps(client, database):
    before = hashlib.sha256(database.read_bytes()).hexdigest()
    for url in ["/v1/leads","/v1/leads/1","/v1/overview"]:
        assert client.get(url).status_code == 200
        assert client.post(url,json={"status":"Fechado"}).status_code == (422 if url == '/v1/leads' else 405)
    assert hashlib.sha256(database.read_bytes()).hexdigest() == before
    with ReadRepository(database).connect() as (connection, _):
        with pytest.raises(sqlite3.OperationalError):
            connection.execute("UPDATE leads SET empresa='forbidden'")


def test_missing_file_not_created_and_health_is_liveness(tmp_path):
    path = tmp_path / "absent" / "missing.db"
    client = TestClient(create_app(Settings(path)))
    assert client.get("/health").json()["status"] == "ok"
    response = client.get("/v1/leads")
    assert response.status_code == 503
    assert str(path) not in response.text
    assert not path.parent.exists()


def test_old_schema_optional_columns_and_preference_absent(tmp_path):
    path = tmp_path / "old.db"
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE leads(id INTEGER PRIMARY KEY,empresa TEXT,status TEXT,segmento TEXT)")
        connection.execute("INSERT INTO leads VALUES(1,'Teste Clínica','Novo Lead','Clínica odontológica')")
    before = path.read_bytes()
    client = TestClient(create_app(Settings(path)))
    lead = client.get("/v1/leads").json()["items"][0]
    assert lead["phone"] is None
    assert lead["contactRole"] == "reception"
    assert lead["stage"] == "Novo"
    assert client.get("/v1/overview").json()["total"] == 1
    assert path.read_bytes() == before


def test_empty_database_is_not_unavailable(tmp_path):
    path = tmp_path / "empty.db"
    initialize_database(path)
    client = TestClient(create_app(Settings(path)))
    assert client.get("/v1/leads").json()["total"] == 0
    assert client.get("/v1/overview").json()["stageCounts"] == []


def test_incompatible_database_and_unknown_lead(client, tmp_path):
    assert client.get("/v1/leads/999").status_code == 404
    path = tmp_path / "bad.db"
    path.write_bytes(b"not sqlite")
    broken = TestClient(create_app(Settings(path)))
    assert broken.get("/v1/overview").status_code == 503


def test_host_and_browser_origin_restrictions(client):
    assert client.get("/v1/leads",headers={"Origin":"https://external.example"}).status_code == 403
    assert client.get("/v1/leads",headers={"Host":"external.example"}).status_code == 400
    assert client.get("/v1/leads").headers["Cache-Control"] == "no-store"


def test_desktop_changes_visible_next_request_even_in_wal(client, database):
    assert client.get("/v1/leads/1").json()["company"] == "Teste Clínica Árvore"
    with sqlite3.connect(database) as connection:
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("UPDATE leads SET empresa='Teste atualizado pelo desktop' WHERE id=1")
    assert client.get("/v1/leads/1").json()["company"] == "Teste atualizado pelo desktop"


def test_locked_database_has_controlled_error(client, database):
    connection = sqlite3.connect(database)
    try:
        connection.execute("BEGIN EXCLUSIVE")
        assert client.get("/v1/leads").status_code == 503
    finally:
        connection.rollback()
        connection.close()
