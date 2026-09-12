from contextlib import closing
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
from unittest.mock import Mock
import sqlite3

import pytest

from core.database import LeadRepository, InteractionRepository, LeadNotFoundError, initialize_database, connect_database
from core.database.schema import LEADS_SCHEMA
from core.commercial.service import CommercialService
from core.commercial.values import STATUSES, utc_iso
from core.commercial.day import build_day, get_my_day
from ui.commercial_logic import (CommercialLead, parse_contact_date, parse_reference_date,
                                 format_date, priority_label, history_text, interaction_values, day_values)

UTC = timezone.utc
LOCAL = timezone(timedelta(hours=-3))


@pytest.fixture
def repo(tmp_path):
    return LeadRepository(tmp_path / "commercial.db")


@pytest.fixture
def lead(repo):
    return repo.create_lead(dict(empresa="Clínica São José", status="Legado", responsavel="Ana", observacoes="Manter"))


def test_schema_old_new_and_idempotence(tmp_path):
    path = tmp_path / "old.db"
    with closing(connect_database(path)) as connection:
        with connection:
            connection.execute(LEADS_SCHEMA)
            connection.execute("INSERT INTO leads (empresa,status,created_at,updated_at) VALUES ('Antiga','Legado','old','old')")
    for _ in range(3):
        initialize_database(path)
    repo = LeadRepository(path)
    row = repo.list_leads()[0]
    assert row["empresa"] == "Antiga" and row["status"] == "Legado" and row["created_at"] == "old"
    for key in ("ultimo_contato", "proximo_contato", "proxima_acao", "canal_preferencial"):
        assert row[key] is None
    with closing(connect_database(path)) as connection:
        assert [r[1] for r in connection.execute("PRAGMA table_info(lead_interactions)")] == [
            "id", "lead_id", "tipo", "canal", "descricao", "created_at"]
    assert repo.count_leads() == 1


def test_interactions_order_isolation_and_restart(repo, lead):
    interactions = InteractionRepository(repo.path)
    other = repo.create_lead({"empresa": "Outra"})
    assert interactions.list_interactions(lead) == [] and interactions.get_last_interaction(lead) is None
    first = interactions.create_interaction(lead, tipo="Primeiro contato", canal="whatsapp", descricao="Olá, José d'Ávila!")
    second = interactions.create_interaction(lead, tipo="Observação")
    interactions.create_interaction(other, tipo="Outro")
    reopened = InteractionRepository(repo.path)
    history = reopened.list_interactions(lead)
    assert [r["id"] for r in history] == [second, first]
    assert history[0]["descricao"] == "" and history[0]["canal"] is None
    assert history[1]["descricao"] == "Olá, José d'Ávila!"
    assert datetime.fromisoformat(history[0]["created_at"]).utcoffset() == timedelta(0)
    assert reopened.get_last_interaction(lead)["id"] == second
    assert reopened.count_interactions(lead) == 2
    assert reopened.count_interactions(other) == 1


def test_missing_lead(repo):
    interactions = InteractionRepository(repo.path)
    with pytest.raises(LeadNotFoundError):
        interactions.create_interaction(999, tipo="Ligação")
    assert interactions.count_interactions(999) == 0


@pytest.mark.parametrize("values", [{"tipo": ""}, {"tipo": "  "}, {"tipo": "Outro", "canal": 123},
                                    {"tipo": "Outro", "descricao": None}])
def test_invalid_interaction_no_insert(repo, lead, values):
    interactions = InteractionRepository(repo.path)
    with pytest.raises(ValueError):
        interactions.create_interaction(lead, **values)
    assert interactions.count_interactions(lead) == 0


def test_transactional_interaction_and_partial_updates(repo, lead):
    service = CommercialService(repo.path)
    before = dict(repo.get_lead(lead))
    inputs = dict(tipo="Ligação", descricao="Retornar amanhã", status="Retornar depois",
                  proxima_acao="Falar com José", proximo_contato="2026-09-12T10:00:00-03:00", canal_preferencial="telefone")
    original = deepcopy(inputs)
    identity = service.register_interaction(lead, **inputs)
    row = repo.get_lead(lead)
    interaction = service.interactions.get_last_interaction(lead)
    assert interaction["id"] == identity
    assert row["ultimo_contato"] == interaction["created_at"] == row["updated_at"]
    assert row["proximo_contato"] == "2026-09-12T13:00:00+00:00"
    assert row["status"] == "Retornar depois" and row["proxima_acao"] == "Falar com José"
    assert row["responsavel"] == before["responsavel"] and row["observacoes"] == before["observacoes"]
    assert row["canal_preferencial"] == "telefone" and inputs == original
    service.register_interaction(lead, tipo="Observação")
    later = repo.get_lead(lead)
    assert later["proximo_contato"] == row["proximo_contato"] and later["status"] == row["status"]
    service.register_interaction(lead, tipo="Outro", proximo_contato=None)
    assert repo.get_lead(lead)["proximo_contato"] is None


def test_service_rollback_after_history_insert(repo, lead, monkeypatch):
    service = CommercialService(repo.path)
    before = dict(repo.get_lead(lead))
    monkeypatch.setattr(LeadRepository, "_update_commercial", Mock(side_effect=sqlite3.OperationalError("simulated")))
    with pytest.raises(sqlite3.OperationalError):
        service.register_interaction(lead, tipo="Reunião", status="Em conversa")
    assert service.interactions.count_interactions(lead) == 0
    assert dict(repo.get_lead(lead)) == before


def test_service_history_insert_failure_does_not_update(repo, lead):
    service = CommercialService(repo.path)
    before = dict(repo.get_lead(lead))
    with closing(connect_database(repo.path)) as connection:
        connection.execute("CREATE TRIGGER reject_interaction BEFORE INSERT ON lead_interactions BEGIN SELECT RAISE(ABORT, 'test'); END")
    with pytest.raises(sqlite3.IntegrityError):
        service.register_interaction(lead, tipo="Mensagem", status="Contato realizado")
    assert dict(repo.get_lead(lead)) == before and service.interactions.count_interactions(lead) == 0


def test_followup_atomic_and_legacy_methods(repo, lead):
    values = dict(status="Meu status legado", responsavel="João", observacoes="O'Brian",
                  proxima_acao="Ligar", proximo_contato=datetime(2026, 9, 11, 10, tzinfo=LOCAL), canal_preferencial="outro")
    repo.update_commercial_followup(lead, **values)
    before = dict(repo.get_lead(lead))
    assert before["proximo_contato"] == "2026-09-11T13:00:00+00:00"
    with pytest.raises(ValueError):
        repo.update_commercial_followup(lead, **{**values, "status": "Changed", "proximo_contato": "bad"})
    assert dict(repo.get_lead(lead)) == before
    repo.update_details(lead, status="Novo", responsavel="Ana", observacoes="edit")
    row = repo.get_lead(lead)
    assert row["proxima_acao"] == "Ligar" and row["proximo_contato"] == before["proximo_contato"]
    repo.mark_last_contact(lead, datetime(2026, 9, 11, tzinfo=UTC))
    assert repo.get_lead(lead)["ultimo_contato"] == "2026-09-11T00:00:00+00:00"
    with pytest.raises(LeadNotFoundError):
        repo.update_commercial_followup(999, **values)


@pytest.mark.parametrize("value", ["2026-09-11", "2026-09-11T10:00:00", "bad", datetime(2026, 9, 11), 123])
def test_ambiguous_dates_rejected(value):
    with pytest.raises(ValueError):
        utc_iso(value)


def test_date_helpers():
    assert parse_contact_date("11/09/2026 10:30", tz=LOCAL) == "2026-09-11T13:30:00+00:00"
    assert format_date("2026-09-11T13:30:00+00:00", tz=LOCAL) == "11/09/2026 10:30"
    assert parse_contact_date("") is None and format_date(None) == ""
    assert utc_iso(None) is None
    assert format_date("wrong") == "Data inválida"
    assert parse_reference_date("11/09/2026") == date(2026, 9, 11)


@pytest.mark.parametrize("value", ["31/02/2026 10:00", "11/09/2026", "2026-09-11", "11/09/2026 25:00"])
def test_bad_ui_contact_dates(value):
    with pytest.raises(ValueError):
        parse_contact_date(value)


def test_day_filters_counts_and_order(repo):
    def add(name, status, due=None, score=50, owner="Ana"):
        return repo.create_lead(dict(empresa=name, status=status, proximo_contato=due,
            qualification_score=score, responsavel=owner))
    older = add("Older", "Legado", "2026-09-09T10:00:00-03:00", 10)
    overdue = add("Overdue", "Em conversa", "2026-09-10T23:00:00-03:00", 99)
    today = add("Today", "Novo", "2026-09-11T10:00:00-03:00", 40)
    meeting = add("Meeting", "Reunião agendada", score=70)
    proposal = add("Proposal", "Proposta enviada", score=30)
    add("Terminal", "Fechado", "2026-09-10T10:00:00-03:00")
    add("Other", "Novo", owner="Bia")
    add("Future", "Em conversa", "2026-09-12T10:00:00-03:00")
    summary = get_my_day(repo, date(2026, 9, 11), responsavel="Ana", tz=LOCAL)
    assert summary.counts == dict(atrasados=2, hoje=1, novos=1, reunioes=1, propostas=1)
    assert [r["id"] for r in summary.rows] == [older, overdue, today, meeting, proposal]
    assert day_values(summary.rows[0])[4] == "Baixa"


@pytest.mark.parametrize("status", ["Fechado", "Sem interesse", "Perdido"])
def test_terminal_not_overdue_but_today_included(repo, status):
    lead = repo.create_lead(dict(empresa="A", status=status, proximo_contato="2026-09-10T23:30:00-03:00"))
    rows = repo.list_leads()
    assert build_day(rows, date(2026, 9, 11), tz=LOCAL).counts["atrasados"] == 0
    assert build_day(rows, date(2026, 9, 10), tz=LOCAL).counts["hoje"] == 1


def test_day_timezone_boundary_and_invalid_data(repo):
    repo.create_lead(dict(empresa="A", status="Em conversa", proximo_contato="2026-09-11T01:00:00+00:00"))
    rows = [dict(r) for r in repo.list_leads()]
    original = deepcopy(rows)
    assert build_day(rows, date(2026, 9, 11), tz=LOCAL).counts["atrasados"] == 1
    assert build_day(rows, date(2026, 9, 11), tz=UTC).counts["hoje"] == 1
    assert rows == original
    rows[0]["proximo_contato"] = "invalid"
    result = build_day(rows, date(2026, 9, 11), tz=UTC)
    assert result.invalid_dates == 1 and result.rows == []


def test_day_score_ties_and_null(repo):
    ids = [repo.create_lead(dict(empresa=str(i), qualification_score=score)) for i, score in enumerate((None, 70, 70, 10))]
    result = get_my_day(repo, date(2026, 9, 11), tz=UTC)
    assert [r["id"] for r in result.rows] == [ids[1], ids[2], ids[3], ids[0]]


@pytest.mark.parametrize("score,label", [(None, "Não disponível"), (0, "Baixa"), (30, "Média"), (50, "Boa"), (70, "Alta")])
def test_priority_reuses_rules(score, label):
    assert priority_label(score) == label


def test_modal_controller_history_and_partial_followup(repo, lead):
    controller = CommercialLead(repo, lead)
    assert history_text(controller.history()) == "Nenhuma interação registrada."
    controller.save(status="Retornar depois", responsavel="Bia", observacoes="Persistir", proxima_acao="Ligar",
                    proximo_contato="12/09/2026 10:00", canal_preferencial="telefone")
    first = controller.register(tipo="Ligação", canal="telefone", descricao="Falamos com José")
    row = controller.load()
    assert row["status"] == "Retornar depois" and row["proxima_acao"] == "Ligar" and row["observacoes"] == "Persistir"
    controller.register(tipo="Follow-up", canal="", descricao="", update_followup=True,
                        status="Em conversa", proxima_acao="Enviar proposta", proximo_contato="")
    reopened = CommercialLead(LeadRepository(repo.path), lead)
    assert len(reopened.history()) == 2 and reopened.history()[-1]["id"] == first
    assert "Falamos com José" in history_text(reopened.history())
    assert reopened.load()["proximo_contato"] is None and reopened.load()["status"] == "Em conversa"
    assert reopened.load()["responsavel"] == "Bia" and reopened.load()["observacoes"] == "Persistir"


def test_constants_and_validation():
    assert len(STATUSES) == 10 and "Contato realizado" in STATUSES
    with pytest.raises(ValueError):
        interaction_values(tipo="", canal="", descricao="")
    assert interaction_values(tipo="Outro", canal="", descricao="")["canal"] is None


def test_parameterized_history(repo, lead):
    interactions = InteractionRepository(repo.path)
    text = "'); DROP TABLE leads; --"
    interactions.create_interaction(lead, tipo=text, canal=text, descricao=text)
    assert interactions.list_interactions(lead)[0]["descricao"] == text
    assert interactions.list_interactions("1 OR 1=1") == []
    assert repo.get_lead(lead) is not None
