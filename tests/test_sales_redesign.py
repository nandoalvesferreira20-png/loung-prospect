"""Configuration, inline selection and connection state without real services."""
import json
import os
import queue
from types import SimpleNamespace
from unittest.mock import Mock

import groq
import httpx
import pytest

from core.providers import environment
from core.sales import provider
from core.sales.config import create_groq_provider
from core.sales.groq_provider import GroqSalesProvider
from core.sales.errors import SalesConfigurationError, SalesProviderError
from ui.sales_workspace import SalesWorkspacePage
from ui.sales_workspace_logic import sales_counts


@pytest.fixture
def config_env(tmp_path, monkeypatch):
    monkeypatch.setattr(os, "environ", {key: value for key, value in os.environ.items()
        if key not in ("AI_PROVIDER", "AI_API_KEY", "AI_MODEL", "GROQ_API_KEY", "GROQ_MODEL", "GROQ_TIMEOUT", "OPENAI_API_KEY")})
    project = tmp_path / "project"
    project.mkdir()
    (project / ".env").write_text("GROQ_API_KEY=synthetic-test-key\nGROQ_MODEL=test-model\n", encoding="utf-8")
    monkeypatch.setattr(environment, "ROOT", project)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    return project


def test_groq_selected_without_ai_provider_from_stable_env_path(config_env):
    before = (config_env / ".env").read_bytes()
    selected = provider.create_sales_provider()
    assert isinstance(selected, GroqSalesProvider)
    assert selected.model == "test-model" and not selected.connection_verified
    assert not (config_env.parent / "elsewhere" / ".env").exists()
    assert (config_env / ".env").read_bytes() == before


def test_existing_environment_precedes_file(config_env):
    os.environ["GROQ_MODEL"] = "environment-model"
    assert create_groq_provider().model == "environment-model"


def test_explicit_other_provider_preserved(config_env):
    os.environ.update(AI_PROVIDER="ollama", AI_MODEL="gemma3:4b")
    assert provider.create_sales_provider().provider_name == "ollama"


def test_no_openai_key_fallback(config_env):
    (config_env / ".env").write_text("GROQ_MODEL=test-model\n", encoding="utf-8")
    os.environ["OPENAI_API_KEY"] = "synthetic-other-key"
    with pytest.raises(SalesConfigurationError, match="GROQ_API_KEY"):
        create_groq_provider()


@pytest.mark.parametrize("status", [200, 401, 403, 429, 500])
def test_connection_requires_successful_model_lookup(status):
    requests = []
    def handler(request):
        requests.append(request)
        return httpx.Response(status, json={"id": "test-model", "object": "model", "created": 1,
            "owned_by": "test", "error": {"message": "private synthetic-test-key"}})
    selected = GroqSalesProvider(key="synthetic-test-key", model="test-model", client_factory=lambda **kw:
        groq.Groq(**kw, http_client=httpx.Client(transport=httpx.MockTransport(handler))))
    assert not selected.connection_verified
    if status == 200:
        selected.test_connection()
        assert selected.connection_verified
    else:
        with pytest.raises(SalesProviderError) as error:
            selected.test_connection()
        assert "private" not in str(error.value)
        assert not selected.connection_verified
    assert len(requests) == 1 and requests[0].method == "GET"
    assert requests[0].url.path == "/openai/v1/models/test-model"


def test_lead_switch_retains_editors_and_drafts():
    a, b = Mock(), Mock()
    a.message = "Edição manual não salva"
    page = SimpleNamespace(selected_id=1, repository=Mock(get_lead=Mock(return_value={"id": 2})),
        empty=Mock(), editors={1: a, 2: b}, cards={1: Mock(), 2: Mock()}, build_editor=Mock(), prune_editors=Mock(), stepper=Mock())
    SalesWorkspacePage.select_lead(page, 2)
    assert page.selected_id == 2
    a.pack_forget.assert_called_once()
    b.pack.assert_called_once()
    SalesWorkspacePage.select_lead(page, 1)
    assert page.editors[1] is a and a.message == "Edição manual não salva"
    page.build_editor.assert_not_called()


def test_late_generation_only_updates_status_and_counts():
    current = Mock()
    page = SimpleNamespace(selected_id=2, editors={2: current}, connection_label=Mock(), refresh=Mock())
    SalesWorkspacePage.generation_completed(page, SimpleNamespace(provider_name="groq", connection_verified=True), None)
    assert page.selected_id == 2
    assert not current.mock_calls
    page.refresh.assert_called_once()
    page.connection_label.configure.assert_called_once_with(text="Groq conectada")


def test_connection_worker_only_updates_queue(monkeypatch):
    from ui import sales_workspace as ui
    service = Mock()
    monkeypatch.setattr(ui, "create_groq_provider", lambda: service)
    thread = Mock()
    monkeypatch.setattr(ui.threading, "Thread", thread)
    page = SimpleNamespace(connection_busy=False, test_button=Mock(), connection_label=Mock(),
        connection_queue=queue.Queue(), after=Mock(), poll_connection=Mock())
    SalesWorkspacePage.test_connection(page)
    assert page.connection_busy
    assert not service.test_connection.called
    count = len(page.connection_label.mock_calls)
    thread.call_args.kwargs["target"]()
    assert len(page.connection_label.mock_calls) == count
    SalesWorkspacePage.poll_connection(page)
    assert not page.connection_busy
    page.connection_label.configure.assert_called_with(text="Groq conectada")


def test_metrics_come_from_existing_states():
    rows = [dict(status="Novo", draft_status="GERADA"), dict(status="Reunião agendada"),
        dict(status="Reunião marcada"), dict(status="Interessado", ultimo_contato="2026-01-01")]
    stats = sales_counts(rows)
    assert stats["leads"] == 4 and stats["pending"] == 1
    assert stats["meetings"] == 2 and stats["interested"] == 1 and stats["contacted"] == 1
