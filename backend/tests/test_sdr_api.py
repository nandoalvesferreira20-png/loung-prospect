"""All generation uses a deterministic stub, never the real API or real database."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import sqlite3
from threading import Event
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from backend.config import Settings
from backend.main import create_app
from backend.sdr.policy import routing, WEB_POLICY
from core.sales.contact import normalize_phone
from core.sales.errors import SalesProviderError
from backend.tests.test_api import database  # registers isolated schema fixture


class Provider:
    provider_name = "groq"
    model = "offline-model"

    def __init__(self):
        self.calls = []

    def generate(self, *, system_prompt, evidence):
        self.calls.append((system_prompt, evidence))
        role = evidence["tipo_contato"]
        message = {"recepcao_equipe": "Olá! Sou Fernando, da Loung Tech. Quem cuida da apresentação digital? Poderiam me encaminhar à pessoa responsável?",
                   "contato_direto": "Olá! Sou Fernando, da Loung Tech. Podemos conversar sobre um site profissional adequado ao seu segmento?",
                   "indefinido": "Olá! Sou Fernando, da Loung Tech. Quem é a pessoa responsável pela apresentação digital?"}[role]
        return {"mensagem": message + (f" Versão {len(self.calls)}." if len(self.calls) > 1 else ""), "angulo": "Apresentação digital", "confianca": 0.7}


def payload(lead=1, **values):
    return {"leadId": lead, "requestId": str(uuid4()), **values}


def client_for(database, provider=None, writes=False):
    return TestClient(create_app(Settings(database, writes), sdr_provider_factory=lambda: provider or Provider()))


@pytest.mark.parametrize("niche,expected", [
    ("CLÍNICA ODONTOLÓGICA", "recepcao_equipe"), ("Clinica veterinaria", "recepcao_equipe"),
    ("Salão com recepção", "recepcao_equipe"), ("Corretor autônomo", "contato_direto"),
    ("Advogado AUTONOMO", "contato_direto"), ("Personal trainer", "contato_direto"),
    ("Fotógrafos", "contato_direto"), ("Profissionais freelancers", "contato_direto"),
    ("Pequenos prestadores de serviços", "contato_direto"), ("Imobiliária", "indefinido"),
    ("Salão pequeno", "indefinido"), ("segmento desconhecido", "indefinido"), (None, "indefinido"),
])
def test_heuristics(niche, expected):
    assert routing(niche)[0] == expected


def test_selection_manual_role_services_and_allowlisted_evidence(database):
    provider = Provider()
    with client_for(database, provider) as client:
        context = client.get("/v1/sdr/leads/1").json()
        assert context["company"] == "Teste Clínica Árvore"
        assert context["contactType"] == "contato_direto"  # saved desktop choice
        assert context["normalizedPhone"] == "5511999991234"
        assert context["contactSource"] == "preferencia_desktop"
        assert client.get("/v1/sdr/leads/999").status_code == 404
        response = client.post("/v1/sdr/generate", json=payload(recipient="reception", service="automation", instruction="Mais breve"))
        assert response.status_code == 200
        assert "encaminhar" in response.json()["message"]
        assert response.json()["contactType"] == "recepcao_equipe"
        system, evidence = provider.calls[0]
        assert WEB_POLICY in system
        assert evidence["servico"] == "Automações e integrações digitais"
        assert evidence["instrucao_adicional"] == "Mais breve"
        assert not {"telefone", "whatsapp", "email", "observacoes"} & evidence.keys()
        assert client.get("/v1/sdr/history/1").json()["items"] == []


def test_incomplete_lead_has_neutral_prompt_without_fabricated_facts(database):
    provider = Provider()
    with client_for(database, provider) as client:
        result = client.post("/v1/sdr/generate", json=payload(3)).json()
        assert result["contactType"] == "indefinido"
        assert "responsável" in result["message"]
        evidence = provider.calls[0][1]
        assert "segmento" not in evidence and "site" not in evidence
        assert evidence["empresa"] == "Teste Legado"


@pytest.mark.parametrize("phone,expected", [("(11) 99999-1234", "5511999991234"), ("+55 11 99999-1234", "5511999991234"), ("11 3333-4444", "551133334444"), ("+1 (415) 555-0123", "14155550123"), ("+351 912 345 678", "351912345678")])
def test_phone_normalization(phone, expected):
    assert normalize_phone(phone) == expected


@pytest.mark.parametrize("phone", [None, "", "123", "(00) 99999-1234", "11 88888-1234", "+55 111", "11999991234 ramal 3"])
def test_invalid_phone(phone):
    with pytest.raises(ValueError):
        normalize_phone(phone)


def test_no_authorization_requirement_but_refusal_still_blocks(database):
    provider = Provider()
    with client_for(database, provider) as client:
        context = client.get("/v1/sdr/leads/1").json()
        assert not context["blocked"] and context["normalizedPhone"]
        assert "não informado" in client.get("/v1/sdr/leads/2").json()["whatsappReason"].lower()
        with sqlite3.connect(database) as connection:
            connection.execute("UPDATE leads SET whatsapp_consent='Recusado' WHERE id=1")
        context = client.get("/v1/sdr/leads/1").json()
        assert context["blocked"] and context["normalizedPhone"] is None
        assert client.post("/v1/sdr/generate", json=payload()).status_code == 409
        assert not provider.calls


def test_idempotency_and_regenerate_different_version(database):
    provider = Provider()
    with client_for(database, provider) as client:
        body = payload()
        first = client.post("/v1/sdr/generate", json=body).json()
        assert client.post("/v1/sdr/generate", json=body).json() == first
        assert len(provider.calls) == 1
        assert client.post("/v1/sdr/generate", json={**body, "recipient":"unknown"}).status_code == 409
        second = client.post("/v1/sdr/generate", json=payload(previousDraftId=first["draftId"])).json()
        assert first["message"] != second["message"]
        assert provider.calls[1][1]["revisao_solicitada"]["textos_anteriores"][0] == first["message"]
        assert client.post("/v1/sdr/generate", json=payload(2, previousDraftId=first["draftId"])).status_code == 409


def test_concurrent_click_rejected_before_provider_call(database):
    entered, release = Event(), Event()
    provider = Provider()
    original = provider.generate
    def slow(**kwargs):
        entered.set()
        assert release.wait(5)
        return original(**kwargs)
    provider.generate = slow
    with client_for(database, provider) as client, ThreadPoolExecutor() as pool:
        future = pool.submit(client.post, "/v1/sdr/generate", json=payload())
        assert entered.wait(3)
        try:
            assert client.post("/v1/sdr/generate", json=payload()).status_code == 429
        finally:
            release.set()
        assert future.result().status_code == 200
        assert len(provider.calls) == 1


@pytest.mark.parametrize("failure", [TimeoutError("secret-api-key"), RuntimeError("secret-api-key"), SalesProviderError("secret-api-key"), {"mensagem":"", "angulo":"teste", "confianca":0.7}, {}])
def test_failures_empty_timeout_sanitized_and_cached(database, failure):
    provider = Provider()
    calls = []
    def fail(**_kwargs):
        calls.append(1)
        if isinstance(failure, Exception): raise failure
        return failure
    provider.generate = fail
    before = database.read_bytes()
    with client_for(database, provider) as client:
        body = payload()
        response = client.post("/v1/sdr/generate", json=body)
        assert response.status_code == 502 and "secret-api-key" not in response.text
        assert client.post("/v1/sdr/generate", json=body).status_code == 502
        assert len(calls) == 1
    assert database.read_bytes() == before


def test_writes_flag_generation_is_read_only(database):
    before = database.read_bytes()
    with client_for(database, writes=False) as client:
        draft = client.post("/v1/sdr/generate", json=payload()).json()
        assert client.get("/v1/sdr/history/1").json()["writesEnabled"] is False
        response = client.post("/v1/sdr/history", json={"draftId":draft["draftId"], "message":draft["message"], "status":"APROVADA"})
        assert response.status_code == 403
    assert database.read_bytes() == before
    assert not (database.parent / "backups").exists()


def test_save_revisions_backup_idempotent_approval_preserve_leads(database):
    with sqlite3.connect(database) as connection:
        before_leads = connection.execute("SELECT * FROM leads").fetchall()
        schema = connection.execute("SELECT sql FROM sqlite_master ORDER BY name").fetchall()
    before = hashlib.sha256(database.read_bytes()).hexdigest()
    with client_for(database, writes=True) as client:
        draft = client.post("/v1/sdr/generate", json=payload()).json()
        assert hashlib.sha256(database.read_bytes()).hexdigest() == before
        body = {"draftId":draft["draftId"], "message":"Olá! Podemos conversar?\nUma opção para vocês.", "status":"EDITADA"}
        saved = client.post("/v1/sdr/history", json=body)
        assert saved.status_code == 200
        assert client.post("/v1/sdr/history", json=body).json() == saved.json()
        assert client.post("/v1/sdr/history", json={**body, "message":"Texto revisado", "status":"APROVADA"}).status_code == 200
        assert client.post("/v1/sdr/history", json={**body, "message":"Sobrescrever aprovado"}).status_code == 409
        assert len(client.get("/v1/sdr/history/1").json()["items"]) == 1
        with sqlite3.connect(database) as connection:
            assert connection.execute("SELECT * FROM leads").fetchall() == before_leads
            assert connection.execute("SELECT sql FROM sqlite_master ORDER BY name").fetchall() == schema
            assert connection.execute("SELECT mensagem FROM outreach_revisions").fetchone()[0] == body["message"]
            assert connection.execute("SELECT status FROM outreach").fetchone()[0] == "APROVADA"
            assert connection.execute("SELECT count(*) FROM lead_interactions").fetchone()[0] == 0
        backups = list((database.parent / "backups").glob("*.db"))
        assert len(backups) == 1
        with sqlite3.connect(backups[0]) as backup:
            assert backup.execute("SELECT * FROM leads").fetchall() == before_leads
            assert backup.execute("SELECT count(*) FROM outreach").fetchone()[0] == 0
            assert backup.execute("SELECT sql FROM sqlite_master ORDER BY name").fetchall() == schema
            assert backup.execute("PRAGMA quick_check").fetchone()[0] == "ok"


def test_expiry_validation_and_old_schema_no_migration(database, tmp_path):
    with client_for(database) as client:
        assert client.post("/v1/sdr/generate", json=payload(instruction="x"*501)).status_code == 422
        assert client.post("/v1/sdr/generate", json=payload(recipient="owner-confirmed")).status_code == 422
        assert client.post("/v1/sdr/history", json={"draftId":str(uuid4()), "message":"texto", "status":"EDITADA"}).status_code == 410
        assert client.post("/v1/sdr/history", json={"draftId":str(uuid4()), "message":"  ", "status":"EDITADA"}).status_code == 422
    old = tmp_path / "old.db"
    with sqlite3.connect(old) as connection:
        connection.execute("CREATE TABLE leads (id INTEGER PRIMARY KEY,empresa TEXT,status TEXT)")
        connection.execute("INSERT INTO leads VALUES (1,'Teste antigo',NULL)")
    before = old.read_bytes()
    with client_for(old) as client:
        assert not client.get("/v1/sdr/history/1").json()["available"]
        assert client.post("/v1/sdr/generate", json=payload()).status_code == 200
    assert old.read_bytes() == before


def test_configured_provider_reuses_configuration_and_caps_timeout(monkeypatch):
    from backend.sdr import service
    provider = Provider()
    provider.timeout = 60
    monkeypatch.setattr(service, "create_groq_provider", lambda: provider)
    assert service.configured_provider() is provider
    assert provider.timeout == 30


def test_expired_token_capacity_and_regeneration_duplicate(database):
    provider = Provider()
    with client_for(database, provider) as client:
        first = client.post("/v1/sdr/generate", json=payload()).json()
        previous = provider.generate
        def repeat(**kwargs):
            response = previous(**kwargs)
            return {**response, "mensagem":first["message"]}
        provider.generate = repeat
        assert client.post("/v1/sdr/generate", json=payload(previousDraftId=first["draftId"])).status_code == 502
        client.app.state.sdr.drafts[first["draftId"]]["time"] -= 901
        assert client.post("/v1/sdr/history", json={"draftId":first["draftId"], "message":"Texto", "status":"EDITADA"}).status_code == 410
        service = client.app.state.sdr
        sample = next(iter(service.requests.values()))
        service.requests.update({str(uuid4()):dict(sample) for _ in range(100)})
        calls = len(provider.calls)
        assert client.post("/v1/sdr/generate", json=payload()).status_code == 429
        assert len(provider.calls) == calls


def test_backup_failure_and_concurrent_desktop_refusal_prevent_write(database, monkeypatch):
    from backend.prospecting.storage import StorageError
    with client_for(database, writes=True) as client:
        draft = client.post("/v1/sdr/generate", json=payload()).json()
        body = {"draftId":draft["draftId"], "message":"Texto revisado", "status":"EDITADA"}
        def fail():
            raise StorageError("safe synthetic failure")
        monkeypatch.setattr(client.app.state.sdr.store.writer, "_backup", fail)
        before = database.read_bytes()
        assert client.post("/v1/sdr/history", json=body).status_code == 503
        assert database.read_bytes() == before
        assert not client.app.state.sdr.store.writer.backed_up
        with sqlite3.connect(database) as connection:
            connection.execute("UPDATE leads SET do_not_contact=1 WHERE id=1")
        before = database.read_bytes()
        assert client.post("/v1/sdr/history", json=body).status_code == 409
        assert database.read_bytes() == before


def test_missing_history_schema_generation_still_works_with_writes_flag(database):
    with sqlite3.connect(database) as connection:
        connection.execute("DROP TABLE outreach_revisions")
    before = database.read_bytes()
    with client_for(database, writes=True) as client:
        history = client.get("/v1/sdr/history/1").json()
        assert not history["available"] and not history["writesEnabled"]
        draft = client.post("/v1/sdr/generate", json=payload()).json()
        assert client.post("/v1/sdr/history", json={"draftId":draft["draftId"], "message":draft["message"], "status":"APROVADA"}).status_code == 409
    assert database.read_bytes() == before


def test_legacy_evidence_bounded_and_manual_unknown_overrides_saved_role(database):
    with sqlite3.connect(database) as connection:
        connection.execute("UPDATE leads SET empresa=?, observacoes='PRIVATE NOTE' WHERE id=1", ("x"*5000,))
    provider = Provider()
    with client_for(database, provider) as client:
        result = client.post("/v1/sdr/generate", json=payload(recipient="unknown")).json()
        assert result["contactType"] == "indefinido"
        evidence = provider.calls[0][1]
        assert len(evidence["empresa"]) == 1500
        assert "PRIVATE NOTE" not in str(evidence)
