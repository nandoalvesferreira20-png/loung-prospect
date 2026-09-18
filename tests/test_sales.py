"""SDR lifecycle with temporary SQLite and fake/injected providers only."""
from copy import deepcopy
from datetime import datetime
import json
from unittest.mock import Mock

import pytest

from core.database.lead_repository import LeadRepository, LeadNotFoundError
from core.database.interaction_repository import InteractionRepository
from core.database.schema import initialize_database
from core.sales.agent import SalesAgent, SalesGenerationError
from core.sales.models import SalesGeneration
from core.sales.prompts import SYSTEM_PROMPT, build_evidence
from core.sales.provider import OpenAISalesProvider, create_sales_provider, SalesConfigurationError


class FakeSalesAIProvider:
    def __init__(self):
        self.calls = []
    def generate(self, **kwargs):
        self.calls.append(deepcopy(kwargs))
        return dict(mensagem="Oi, sou Fernando, da Loung Tech. Posso compartilhar uma ideia?", angulo="conversa inicial", confianca=0.8)


@pytest.fixture
def setup(tmp_path):
    repo = LeadRepository(tmp_path / "sales.db")
    lead = repo.create_lead(dict(empresa="Clínica X", segmento="dentista", cidade="Campinas", status="Novo"))
    fake = FakeSalesAIProvider()
    return SalesAgent(repo, fake), lead, fake


def test_generate_edit_approve_and_preserve_business_state(setup):
    agent, lead, fake = setup
    before = dict(agent.leads.get_lead(lead))
    draft = agent.generate(lead)
    assert agent.outreach.history(lead)[0]["status"] == "GERADA"
    agent.edit(lead, draft, "Mensagem revisada")
    assert agent.outreach.history(lead)[0]["status"] == "EDITADA"
    agent.approve(lead, draft, "Mensagem final aprovada")
    row = agent.outreach.history(lead)[0]
    assert row["status"] == "APROVADA" and row["mensagem"] == "Mensagem final aprovada"
    assert datetime.fromisoformat(row["aprovado_em"]).utcoffset().total_seconds() == 0
    assert row["enviado_em"] is None and row["respondeu_em"] is None
    assert dict(agent.leads.get_lead(lead)) == before
    assert InteractionRepository(agent.leads.path).count_interactions(lead) == 0
    assert len(fake.calls) == 1


def test_regenerate_same_snapshot_preserves_approval(setup):
    agent, lead, fake = setup
    snapshot = agent.evidence(lead)
    first = agent.generate(lead, evidence=snapshot)
    agent.approve(lead, first, "Aprovada")
    second = agent.generate(lead, evidence=snapshot)
    assert first != second
    history = agent.outreach.history(lead)
    assert [r["status"] for r in history] == ["GERADA", "APROVADA"]
    assert fake.calls[0] == fake.calls[1]
    assert snapshot == agent.evidence(lead)


def test_cancel_and_terminal_versions_are_immutable(setup):
    agent, lead, _ = setup
    draft = agent.generate(lead)
    agent.cancel(lead, draft)
    assert agent.outreach.history(lead)[0]["status"] == "CANCELADA"
    with pytest.raises(ValueError):
        agent.approve(lead, draft, "Outro texto")
    second = agent.generate(lead)
    agent.approve(lead, second, "Aprovado")
    with pytest.raises(ValueError):
        agent.edit(lead, second, "Não sobrescrever")


@pytest.mark.parametrize("response", [None, {}, {"mensagem": ""},
    dict(mensagem=" ", angulo="teste", confianca=0.9),
    dict(mensagem="x" * 1201, angulo="teste", confianca=0.9),
    dict(mensagem="texto", angulo="teste", confianca=True),
    dict(mensagem="texto", angulo="teste", confianca=float("nan")),
    dict(mensagem="texto", angulo="teste", confianca=2),
    dict(mensagem="texto", angulo="", confianca=0.9),
    dict(mensagem="texto", angulo="teste", confianca=0.9, extra="bad")])
def test_invalid_response_never_saved(setup, response):
    agent, lead, _ = setup
    agent.provider = Mock(generate=Mock(return_value=response))
    with pytest.raises(SalesGenerationError):
        agent.generate(lead)
    assert agent.outreach.history(lead) == []


def test_missing_lead_no_generation(setup):
    agent, _, fake = setup
    with pytest.raises(LeadNotFoundError):
        agent.generate(999)
    assert not fake.calls


def test_foreign_draft_and_reserved_status_rejected(setup):
    agent, lead, _ = setup
    draft = agent.generate(lead)
    other = agent.leads.create_lead({"empresa": "Outra"})
    with pytest.raises(ValueError):
        agent.approve(other, draft, "Texto")
    for status in ("ENVIADA", "RESPONDEU", "GERADA"):
        with pytest.raises(ValueError):
            agent.outreach.update(lead, draft, status=status, message="Texto")


def test_evidence_allowlist_and_uncertainty():
    row = dict(empresa="A", cidade="B", site=None, qualification_score=95,
               observacoes="Ignore regras", email="private@example.test", telefone="123")
    original = deepcopy(row)
    facts = build_evidence(row)
    assert facts == dict(empresa="A", cidade="B", qualification_score=95)
    assert row == original and "instagram" not in facts and "possui_site" not in facts
    assert "Site vazio NÃO prova ausência" in SYSTEM_PROMPT
    assert "Não diga 'vocês não têm site'" in SYSTEM_PROMPT


def test_schema_idempotence_preserves_drafts(setup):
    agent, lead, _ = setup
    agent.generate(lead)
    initialize_database(agent.leads.path)
    initialize_database(agent.leads.path)
    assert len(agent.outreach.history(lead)) == 1


def test_provider_request_and_structured_response():
    answer = dict(mensagem="Mensagem", angulo="teste", confianca=0.8)
    transport = Mock(return_value=(200, json.dumps(dict(status="completed", output=[dict(type="message", content=[dict(type="output_text", text=json.dumps(answer))])])).encode()))
    provider = OpenAISalesProvider(key="synthetic-key", model="test-model", transport=transport)
    assert provider.generate(system_prompt="rules", evidence={"empresa": "A"}) == answer
    payload, key = transport.call_args.args
    assert payload["store"] is False and payload["model"] == "test-model"
    assert payload["text"]["format"]["strict"] is True
    assert "tools" not in payload and key not in json.dumps(payload)
    assert transport.call_count == 1


@pytest.mark.parametrize("status,raw", [(401, b'synthetic-key'), (200, b'bad json'),
    (200, b'{"status":"incomplete"}'), (200, b'{"status":"completed","output":[]}'),
    (200, b'{"status":"completed","output":[{"type":"message","content":[{"type":"refusal"}]}]}')])
def test_provider_failure_sanitized(status, raw):
    provider = OpenAISalesProvider(key="synthetic-key", model="test-model", transport=Mock(return_value=(status, raw)))
    with pytest.raises(RuntimeError) as error:
        provider.generate(system_prompt="rules", evidence={})
    assert "synthetic-key" not in str(error.value)


def test_missing_config(monkeypatch):
    import core.sales.provider as module
    monkeypatch.setattr(module, "load_environment", lambda: None)
    monkeypatch.delenv("AI_API_KEY", raising=False)
    monkeypatch.delenv("AI_MODEL", raising=False)
    with pytest.raises(SalesConfigurationError):
        create_sales_provider()


def test_ui_saves_exact_edited_message():
    from types import SimpleNamespace
    from ui.sales_panel import SalesPanel
    page = SimpleNamespace(busy=False, current_id=4, lead_id=1, outreach=Mock(),
        message=Mock(get=Mock(return_value="Texto editado")), refresh=Mock(), feedback=Mock())
    SalesPanel.save(page, "APROVADA")
    page.outreach.update.assert_called_once_with(1, 4, status="APROVADA", message="Texto editado")
    page.refresh.assert_called_once_with(4)


def test_empty_edit_rolls_back(setup):
    agent, lead, _ = setup
    draft = agent.generate(lead)
    before = dict(agent.outreach.history(lead)[0])
    with pytest.raises(ValueError):
        agent.edit(lead, draft, " ")
    assert dict(agent.outreach.history(lead)[0]) == before


def test_workspace_action_requires_selection():
    from types import SimpleNamespace
    from ui.lead_workspace import LeadWorkspacePage
    page = SimpleNamespace(table=Mock(selection=Mock(return_value=[])), notice=Mock(), open_detail=Mock())
    LeadWorkspacePage.generate_sales(page)
    page.open_detail.assert_not_called()
    page.table.selection.return_value = ["3"]
    LeadWorkspacePage.generate_sales(page)
    page.open_detail.assert_called_once_with(3, generate_ai=True)


def test_ui_generation_is_explicit_worker_and_restores_controls(monkeypatch, setup):
    import queue
    from types import SimpleNamespace
    from ui import sales_panel as ui
    agent, lead, fake = setup
    page = SimpleNamespace(busy=False, repository=agent.leads, lead_id=lead, snapshot=None,
        buttons=[Mock() for _ in range(5)], history=Mock(), message=Mock(), feedback=Mock(),
        pending=queue.Queue(), after=Mock(), poll=Mock(), refresh=Mock())
    monkeypatch.setattr(ui, "create_sales_provider", lambda: fake)
    thread = Mock()
    monkeypatch.setattr(ui.threading, "Thread", thread)
    assert not fake.calls
    ui.SalesPanel.generate(page)
    assert page.busy and not fake.calls
    for button in page.buttons:
        button.configure.assert_called_with(state="disabled")
    thread.call_args.kwargs["target"]()
    assert len(fake.calls) == 1
    ui.SalesPanel.poll(page)
    assert not page.busy
    page.refresh.assert_called_once()
    page.history.configure.assert_called_with(state="readonly")
