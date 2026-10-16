from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import sqlite3
from zoneinfo import ZoneInfo
import pytest
from fastapi.testclient import TestClient
from backend.config import Settings
from backend.main import create_app
from backend.tests.test_api import database
from core.commercial.day import build_day
from core.commercial.values import STATUS_ALIASES


def client_for(database, writes=True):
    return TestClient(create_app(Settings(database,writes)))


def detail(client, lead=1):
    return client.get(f"/v1/crm/leads/{lead}").json()


def move(client, stage, lead=1, rev=None):
    return client.patch(f"/v1/leads/{lead}/stage",json={"stage":stage,"confirmed":True,"revision":rev or detail(client,lead)["lead"]["revision"]})


@pytest.mark.parametrize("legacy,canonical",list(STATUS_ALIASES.items()))
def test_legacy_mapping_read_never_writes(database, legacy, canonical):
    with sqlite3.connect(database) as connection:
        connection.execute("UPDATE leads SET status=? WHERE id=1",(legacy,))
    before=database.read_bytes()
    with client_for(database) as client:
        result=client.get("/v1/pipeline").json()
        lead=next(lead for col in result["columns"] for lead in col["items"] if lead["id"] == 1)
        assert lead["stage"] == canonical and lead["originalStage"] == legacy
        assert not move(client,canonical).json()["changed"]
    assert database.read_bytes() == before


def test_pipeline_custom_search_niche_pagination_and_detail(database):
    with client_for(database) as client:
        result=client.get("/v1/pipeline",params={"limit":1}).json()
        assert sum(c["total"] for c in result["columns"]) == 5
        assert "Etapa personalizada" in result["stages"]
        assert all(len(c["items"]) <= 1 for c in result["columns"])
        filtered=client.get("/v1/pipeline",params={"q":"CLINICA ARVORE","niche":"clinica odontologica"}).json()
        assert filtered["total"] == 1
        assert detail(client)["lead"]["stage"] == "Reunião agendada"
        assert client.get("/v1/crm/leads/999").status_code == 404
        assert client.get("/v1/pipeline",params={"stage":"made-up"}).status_code == 422
        assert client.get("/v1/pipeline",params={"q":"' OR 1=1 --"}).json()["total"] == 0


def test_stage_custom_existing_atomic_history_and_concurrency(database):
    with client_for(database) as client:
        before=detail(client)["lead"]
        response=move(client,"Etapa personalizada")
        assert response.status_code == 200
        assert move(client,"Fechado",rev=before["revision"]).status_code == 409
        assert move(client,"Made up").status_code == 422
        assert detail(client)["lead"]["stage"] == "Etapa personalizada"
        activities=client.get("/v1/leads/1/activities").json()
        event=next(e for e in activities["items"] if e["origin"] == "manual")
        assert "Reunião marcada" in event["description"] and "Etapa personalizada" in event["description"]
        assert detail(client)["lead"]["lastContact"] is None
        assert len(list((database.parent/"backups").glob("*.db"))) == 1


def test_two_simultaneous_updates_only_one_wins(database):
    with client_for(database) as client, ThreadPoolExecutor() as pool:
        rev=detail(client)["lead"]["revision"]
        assert client.patch("/v1/leads/1/stage",json={"stage":"Contato realizado","revision":rev}).status_code == 422
        futures=[pool.submit(move,client,target,rev=rev) for target in ("Fechado","Perdido")]
        assert sorted(f.result().status_code for f in futures) == [200,409]


def test_activity_confirmation_append_notes_and_no_stage_inference(database):
    with sqlite3.connect(database) as connection:
        connection.execute("UPDATE leads SET observacoes='Observação antiga' WHERE id=1")
    with client_for(database) as client:
        base={"kind":"Contato realizado","description":"Conversa confirmada pelo operador","channel":"whatsapp"}
        rev=detail(client)["lead"]["revision"]
        assert client.post("/v1/leads/1/activities",json={**base,"revision":rev}).status_code == 422
        response=client.post("/v1/leads/1/activities",json={**base,"revision":rev,"confirmed":True})
        assert response.status_code == 200
        assert client.post("/v1/leads/1/activities",json={**base,"revision":rev,"confirmed":True}).status_code == 409
        lead=detail(client)["lead"]
        assert lead["stage"] == "Reunião agendada" and lead["lastContact"]
        assert client.post("/v1/leads/1/activities",json={"kind":"Observação","description":"Nova observação","revision":lead["revision"]}).status_code == 200
        assert detail(client)["lead"]["notes"] == "Observação antiga"
        history=client.get("/v1/leads/1/activities").json()
        assert any(row["description"] == "Nova observação" for row in history["items"])
        assert any(row["description"] == "Observação antiga" for row in history["items"])


def test_followup_schedule_reschedule_complete_preserves_commercial_data(database):
    with client_for(database) as client:
        original=detail(client,3)["lead"]
        def schedule(due,note):
            return client.post("/v1/leads/3/followups",json={"revision":detail(client,3)["lead"]["revision"],"dueAt":due,"note":note})
        assert schedule("2026-12-20T09:00:00-03:00","Revisar proposta").status_code == 200
        assert detail(client,3)["lead"]["nextContact"] == "2026-12-20T12:00:00+00:00"
        old=detail(client,3)["lead"]["revision"]
        assert schedule(None,"Definir um horário com a equipe").status_code == 200
        assert client.patch("/v1/followups/3",json={"action":"complete","revision":old}).status_code == 409
        current=detail(client,3)["lead"]
        assert client.patch("/v1/followups/3",json={"action":"complete","revision":current["revision"]}).status_code == 200
        final=detail(client,3)["lead"]
        assert final["nextContact"] is None and final["nextAction"] is None
        assert final["stage"] == original["stage"] and final["lastContact"] is None
        history=client.get("/v1/leads/3/activities").json()["items"]
        assert any("Follow-up concluído" in r["kind"] for r in history)
        assert any("2026-12-20T12:00:00+00:00" in r["description"] for r in history)
        assert schedule("2026-12-20T09:00","").status_code == 422
        assert schedule(None,"").status_code == 422


def test_my_day_reuses_rules_and_paginates(database):
    with sqlite3.connect(database) as connection:
        connection.row_factory=sqlite3.Row
        rows=[dict(row) for row in connection.execute("SELECT * FROM leads")]
    zone=ZoneInfo("America/Sao_Paulo")
    summary=build_day(rows,datetime.now(zone).date(),tz=zone)
    with client_for(database) as client:
        result=client.get("/v1/followups",params={"scope":"day","limit":1}).json()
        assert result["total"] == len(summary.rows)
        assert result["overdue"] == summary.counts["atrasados"]
        assert result["invalidDates"] == 1
        assert result["items"][0]["id"] == summary.rows[0]["id"]
        assert client.get("/v1/followups",params={"tz":"Not/A_Zone"}).status_code == 422
        overview=client.get("/v1/overview",params={"tz":"America/Sao_Paulo"}).json()
        assert overview["today"] == summary.counts["hoje"] and overview["overdue"] == summary.counts["atrasados"]
        assert client.get("/v1/overview",params={"tz":"Not/A_Zone"}).status_code == 422


def test_metrics_no_inference_from_drafts_and_distinct_leads(database):
    with client_for(database) as client:
        before=client.get("/v1/dashboard/commercial").json()
        assert before["contacted"] == 1 and before["responded"] == 0
        assert before["converted"] == 1 and before["total"] == 5
        for _ in range(2):
            client.post("/v1/leads/1/activities",json={"revision":detail(client)["lead"]["revision"],"kind":"Resposta recebida","description":"Resposta confirmada manualmente","confirmed":True})
        assert client.get("/v1/dashboard/commercial").json()["responded"] == 1
        with sqlite3.connect(database) as connection:
            connection.execute("INSERT INTO outreach(lead_id,mensagem,status,criado_em,atualizado_em) VALUES(3,'Rascunho','GERADA','2026-01-01','2026-01-01')")
        assert client.get("/v1/dashboard/commercial").json()["contacted"] == 1
        history=client.get("/v1/leads/3/activities").json()["items"]
        assert any(row["origin"] == "draft" for row in history)


def test_legacy_contact_response_facts_survive_stage_progression(database):
    with sqlite3.connect(database) as connection:
        connection.execute("UPDATE leads SET status='Respondeu' WHERE id=3")
    with client_for(database) as client:
        before=client.get("/v1/dashboard/commercial").json()
        assert before["contacted"] == 1 and before["responded"] == 1
        assert move(client,"Em conversa",lead=2).status_code == 200
        assert move(client,"Fechado",lead=3).status_code == 200
        after=client.get("/v1/dashboard/commercial").json()
        assert after["contacted"] == 1 and after["responded"] == 1


def test_writes_disabled_reads_and_missing_lead(database):
    before=database.read_bytes()
    with client_for(database,False) as client:
        rev=detail(client)["lead"]["revision"]
        assert client.get("/v1/pipeline").json()["writesEnabled"] is False
        assert move(client,"Fechado").status_code == 403
        assert client.post("/v1/leads/1/activities",json={"kind":"Observação","description":"texto","revision":rev}).status_code == 403
        assert client.patch("/v1/followups/1",json={"action":"complete","revision":rev}).status_code == 403
    assert database.read_bytes() == before
    assert not (database.parent/"backups").exists()
    with client_for(database) as client:
        assert move(client,"Fechado",lead=999,rev="a"*64).status_code == 404


def test_sql_failure_rolls_back_lead_and_timestamp(database):
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TRIGGER reject_activity BEFORE INSERT ON lead_interactions BEGIN SELECT RAISE(ABORT,'synthetic-secret'); END")
        before=connection.execute("SELECT * FROM leads WHERE id=1").fetchone()
    with client_for(database) as client:
        response=move(client,"Fechado")
        assert response.status_code == 503 and "synthetic-secret" not in response.text
        with sqlite3.connect(database) as connection:
            assert connection.execute("SELECT * FROM leads WHERE id=1").fetchone() == before
            assert connection.execute("SELECT count(*) FROM lead_interactions").fetchone()[0] == 0


def test_legacy_schema_no_migration_and_safe_unavailable(tmp_path):
    path=tmp_path/"old.db"
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE leads(id INTEGER PRIMARY KEY,empresa TEXT,status TEXT)")
        connection.executemany("INSERT INTO leads VALUES (?,?,?)",[(1,"Teste 1",None),(2,"Teste 2","")])
    before=path.read_bytes()
    with client_for(path) as client:
        result=client.get("/v1/pipeline").json()
        assert result["total"] == 2
        assert not result["writesEnabled"]
        assert not client.get("/v1/followups").json()["available"]
        assert client.get("/v1/dashboard/commercial").json()["pending"] is None
        assert not client.get("/v1/leads/1/activities").json()["available"]
    assert path.read_bytes() == before
