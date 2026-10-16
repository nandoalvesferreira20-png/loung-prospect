from datetime import datetime, timezone
import sqlite3
from types import SimpleNamespace
from unittest.mock import Mock
from urllib.parse import parse_qs, urlsplit

import pytest

from core.database.lead_repository import LeadRepository
from core.database.schema import initialize_database, LEADS_SCHEMA
from core.database.interaction_repository import InteractionRepository
from core.sales.contact import ContactService, normalize_phone, SDR_STATUSES
from core.sales.agent import SalesAgent, SalesGenerationError
from ui.sales_workspace_logic import list_sales_leads, sales_counts


@pytest.fixture
def setup(tmp_path):
    repo = LeadRepository(tmp_path / "test.db")
    lead = repo.create_lead({"empresa": "Clínica São José", "segmento": "dentista", "telefone": "(11) 99999-1234"})
    service = ContactService(repo)
    values = dict(status="Novo", consent="Autorizado", source="Autorização expressa por formulário",
        authorized_at="2026-01-01T10:00:00-03:00", responsible="Fernando", notes="Revisar")
    return repo, lead, service, values


@pytest.mark.parametrize("value,expected", [("(11) 99999-1234", "5511999991234"),
    ("+55 (11) 99999-1234", "5511999991234"), ("5511999991234", "5511999991234"),
    ("(55) 99999-1234", "5555999991234"), ("11 3333-1234", "551133331234"),
    ("+351 912345678", "351912345678")])
def test_phone_normalization(value, expected):
    assert normalize_phone(value) == expected


@pytest.mark.parametrize("value", [None, "", "99999-1234", "00 11 999991234", "(20) 99999-1234",
    "+55 99999-1234", "11 88888-1234", "1199991234", "11 99999-1234 ramal 2", "+0123456789", "123abc456"])
def test_invalid_phone(value):
    with pytest.raises(ValueError):
        normalize_phone(value)


def test_link_needs_no_authorization_and_encoding_has_no_writes(setup):
    repo, lead, service, values = setup
    initial = dict(repo.get_lead(lead))
    assert service.preview_url(lead, "Oi").startswith("https://wa.me/5511999991234?")
    assert dict(repo.get_lead(lead)) == initial
    assert initial["whatsapp_consent"] == "Desconhecido"
    service.save(lead, **values)
    before = dict(repo.get_lead(lead))
    message = "Olá São José!\nUma ideia & você? #contato +"
    url = service.preview_url(lead, message)
    assert urlsplit(url).path == "/5511999991234"
    assert parse_qs(urlsplit(url).query)["text"] == [message]
    assert dict(repo.get_lead(lead)) == before
    assert before["ultimo_contato"] is None
    assert datetime.fromisoformat(before["consent_at"]).utcoffset().total_seconds() == 0


@pytest.mark.parametrize("change", [{"consent": "Recusado"}, {"consent": "Revogado"}, {"status": "Não contatar"}])
def test_refusals_block_generation_and_whatsapp_even_after_legacy_status_change(setup, change):
    repo, lead, service, values = setup
    service.save(lead, **(values | change))
    repo.update_status(lead, "Novo")
    with pytest.raises(ValueError, match="bloqueado"):
        service.preview_url(lead, "Oi")
    fake = Mock()
    with pytest.raises(SalesGenerationError, match="bloqueada"):
        SalesAgent(repo, fake).generate(lead)
    fake.generate.assert_not_called()
    with pytest.raises(ValueError, match="bloqueado"):
        service.save(lead, **values)


def test_link_uses_current_phone_without_changing_legacy_authorization(setup):
    repo, lead, service, values = setup
    service.save(lead, **values)
    with sqlite3.connect(repo.path) as connection:
        connection.execute("UPDATE leads SET telefone=? WHERE id=?", ("11988881234", lead))
    assert urlsplit(service.preview_url(lead, "Oi")).path == "/5511988881234"
    assert repo.get_lead(lead)["consent_number"] == "5511999991234"


@pytest.mark.parametrize("change", [{"source": ""}, {"authorized_at": ""},
    {"authorized_at": "2026-01-01"}, {"authorized_at": "2999-01-01T00:00:00Z"},
    {"status": "Contatado"}, {"status": "bad"}])
def test_invalid_updates_rollback(setup, change):
    repo, lead, service, values = setup
    before = dict(repo.get_lead(lead))
    with pytest.raises(ValueError):
        service.save(lead, **(values | change))
    assert dict(repo.get_lead(lead)) == before
    assert InteractionRepository(repo.path).list_interactions(lead) == []


@pytest.mark.parametrize("status", SDR_STATUSES)
def test_manual_status_and_history_persist(setup, status):
    repo, lead, service, values = setup
    service.save(lead, **(values | dict(status=status)), contact_at="2026-01-02T12:00:00Z" if status == "Contato realizado" else None)
    reopened = LeadRepository(repo.path)
    assert reopened.get_lead(lead)["status"] == status
    history = InteractionRepository(repo.path).list_interactions(lead)
    assert status in history[0]["descricao"] and "Fernando" in history[0]["descricao"]
    assert bool(reopened.get_lead(lead)["ultimo_contato"]) == (status == "Contato realizado")


def test_migration_preserves_old_lead_without_granting_consent(tmp_path):
    path = tmp_path / "old.db"
    with sqlite3.connect(path) as connection:
        connection.execute(LEADS_SCHEMA)
        connection.execute("INSERT INTO leads (empresa,status,created_at,updated_at) VALUES ('Antiga','Novo','old','old')")
    initialize_database(path)
    initialize_database(path)
    repo = LeadRepository(path)
    assert repo.count_leads() == 1
    row = repo.get_lead(1)
    assert row["empresa"] == "Antiga" and row["created_at"] == "old"
    assert row["whatsapp_consent"] == "Desconhecido" and row["do_not_contact"] == 0


def test_cached_generation_regeneration_and_revision_history(setup):
    repo, lead, _, _ = setup
    answer = dict(mensagem="Uma ideia para vocês?", angulo="contatos", confianca=0.8)
    fake = Mock(generate=Mock(return_value=answer))
    agent = SalesAgent(repo, fake)
    first = agent.generate(lead, reuse_existing=True)
    assert agent.generate(lead, reuse_existing=True) == first
    assert fake.generate.call_count == 1
    agent.edit(lead, first, "Edição humana")
    reviewed = agent.outreach.history(lead)[0]["revisado_em"]
    assert datetime.fromisoformat(reviewed).utcoffset().total_seconds() == 0
    agent.approve(lead, first, "Versão aprovada")
    assert [r["mensagem"] for r in agent.outreach.revisions(lead)] == ["Edição humana", answer["mensagem"]]
    fake.generate.return_value = answer | {"mensagem": "Outra ideia para conversar?"}
    second = agent.generate(lead, regeneration_reason="Mais curto")
    assert second != first
    context = fake.generate.call_args.kwargs["evidence"]
    assert context["revisao_solicitada"]["motivo"] == "Mais curto"
    assert "Versão aprovada" in context["revisao_solicitada"]["textos_anteriores"]
    with pytest.raises(SalesGenerationError, match="repetiu"):
        agent.generate(lead, regeneration_reason="Mais curto")
    assert len(agent.outreach.history(lead)) == 2


def test_refusal_during_generation_prevents_persistence(setup):
    repo, lead, service, values = setup
    def generate(**kwargs):
        service.save(lead, **(values | {"consent": "Recusado"}))
        return dict(mensagem="Oi", angulo="contato", confianca=0.8)
    agent = SalesAgent(repo, SimpleNamespace(generate=generate))
    with pytest.raises(ValueError, match="bloqueado"):
        agent.generate(lead)
    assert agent.outreach.history(lead) == []


def test_listing_filters_metrics_reuse_existing_leads(setup):
    repo, lead, _, _ = setup
    fake = Mock(generate=Mock(return_value=dict(mensagem="Olá", angulo="contato", confianca=0.8)))
    agent = SalesAgent(repo, fake)
    draft = agent.generate(lead)
    rows = list_sales_leads(repo, search="sÃO", segment="DENTISTA", status="Mensagem gerada")
    assert len(rows) == 1 and rows[0]["id"] == lead
    assert sales_counts(rows)["generated"] == 1
    agent.edit(lead, draft, "Revisada")
    assert sales_counts(list_sales_leads(repo))["reviewed"] == 1
    assert list_sales_leads(repo, search="sem correspondência") == []
    assert repo.count_leads() == 1
