"""Offline Ollama contract, transport, persistence and worker regressions."""
import json
import logging
import queue
import sqlite3
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from core.database.lead_repository import LeadRepository
from core.database.schema import OUTREACH_SCHEMA, initialize_database
from core.sales.agent import SalesAgent, SalesGenerationError
from core.sales.errors import SalesConfigurationError, SalesProviderError
from core.sales.ollama import OllamaSalesProvider, parse_ollama_output
from core.sales import ollama, provider
from core.sales.prompts import SYSTEM_PROMPT

ANSWER = dict(mensagem="Oi, sou Fernando, da Loung Tech. Posso compartilhar uma ideia?",
              angulo="Conversa inicial", confianca=0.8)


def response(content=None, **overrides):
    data = dict(done=True, message=dict(role="assistant", content=json.dumps(ANSWER) if content is None else content))
    data.update(overrides)
    return 200, json.dumps(data).encode()


@pytest.fixture
def environment(monkeypatch):
    monkeypatch.setattr(provider, "load_environment", lambda: None)
    for key in ("AI_API_KEY", "AI_PROVIDER", "AI_MODEL", "OLLAMA_BASE_URL", "OLLAMA_TIMEOUT"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("AI_PROVIDER", "ollama")
    monkeypatch.setenv("AI_MODEL", "gemma3:4b")
    return monkeypatch


def test_factory_without_api_key_and_safe_log(environment, caplog):
    with caplog.at_level(logging.INFO):
        selected = provider.create_sales_provider()
    assert isinstance(selected, OllamaSalesProvider)
    assert selected.base_url == "http://localhost:11434"
    assert selected.timeout == 120
    assert "provider=ollama model=gemma3:4b" in caplog.text
    assert "http://" not in caplog.text


def test_factory_configurable_and_openai_preserved(environment):
    environment.setenv("OLLAMA_BASE_URL", "http://127.0.0.1:11435")
    environment.setenv("OLLAMA_TIMEOUT", "60")
    selected = provider.create_sales_provider()
    assert selected.timeout == 60 and selected.base_url.endswith(":11435")
    environment.setenv("AI_PROVIDER", "openai")
    with pytest.raises(SalesConfigurationError):
        provider.create_sales_provider()
    environment.setenv("AI_API_KEY", "synthetic-key")
    assert isinstance(provider.create_sales_provider(), provider.OpenAISalesProvider)
    environment.setenv("AI_PROVIDER", "unknown")
    with pytest.raises(SalesConfigurationError):
        provider.create_sales_provider()


@pytest.mark.parametrize("kwargs", [dict(model=""), dict(model="bad\nmodel"),
    dict(model="--flag"), dict(timeout="bad"), dict(timeout="nan"), dict(timeout=0),
    dict(timeout=601), dict(base_url="file:///tmp"), dict(base_url="http://user:secret@localhost"),
    dict(base_url="http://localhost/api/chat"), dict(base_url="http://localhost?key=secret"),
    dict(base_url="http://localhost:99999")])
def test_invalid_configuration(kwargs):
    with pytest.raises(SalesConfigurationError) as error:
        OllamaSalesProvider(**(dict(model="gemma3:4b") | kwargs))
    assert "secret" not in str(error.value)


@pytest.mark.parametrize("wrapper", ["{}", "```json\n{}\n```", "Aqui está o JSON:\n{}\nFim."])
def test_parser_accepts_single_object(wrapper):
    assert parse_ollama_output(wrapper.format(json.dumps(ANSWER, ensure_ascii=False))) == ANSWER


@pytest.mark.parametrize("text", ["", "not json", "{}", "[]", "null",
    json.dumps([ANSWER]), json.dumps(ANSWER) + json.dumps(ANSWER),
    '{"broken":' + json.dumps(ANSWER),
    json.dumps(ANSWER)[:-1] + ',"confianca":0.9}',
    *[json.dumps(ANSWER | change) for change in [
        dict(mensagem=""), dict(mensagem=15), dict(mensagem="x" * 1201),
        dict(angulo=""), dict(angulo=None), dict(confianca=87), dict(confianca=-1),
        dict(confianca="0.8"), dict(confianca=True), dict(confianca=float("nan")),
        dict(confianca=float("inf")), dict(extra="unexpected")]]])
def test_parser_rejects_invalid_or_ambiguous(text):
    with pytest.raises(ValueError):
        parse_ollama_output(text)


def test_http_endpoint_payload_and_close(monkeypatch):
    connection = Mock()
    connection.getresponse.return_value = Mock(status=200, read=Mock(return_value=response()[1]))
    factory = Mock(return_value=connection)
    monkeypatch.setattr(ollama.http.client, "HTTPConnection", factory)
    evidence = {"empresa": "Clínica Sintética"}
    before = deepcopy(evidence)
    actual = OllamaSalesProvider(model="gemma3:4b").generate(system_prompt=SYSTEM_PROMPT, evidence=evidence)
    assert actual == ANSWER and evidence == before
    factory.assert_called_once_with("localhost", port=11434, timeout=120)
    args, kwargs = connection.request.call_args
    assert args == ("POST", "/api/chat")
    payload = json.loads(kwargs["body"])
    assert payload == dict(model="gemma3:4b", stream=False, format=provider.SCHEMA,
        messages=[dict(role="system", content=SYSTEM_PROMPT),
                  dict(role="user", content=json.dumps(evidence, ensure_ascii=False))])
    assert kwargs["headers"] == {"Content-Type": "application/json"}
    connection.close.assert_called_once()


@pytest.mark.parametrize("failure,expected", [(ConnectionRefusedError("secret"), "conectar"),
    (TimeoutError("secret"), "tempo de espera"),
    ((404, b'{"error":"model gemma3:4b not found secret"}'), "ollama pull gemma3:4b"),
    ((500, b'secret'), "rejeitou"), ((404, b'{"error":"route not found"}'), "rejeitou"),
    ((200, b'secret'), "resposta completa"), (response(done=False), "resposta completa"),
    (response(done_reason="length"), "resposta completa"),
    (response(content=json.dumps(ANSWER | dict(confianca=87))), "resposta completa"),
    ((200, b'x' * 1_000_001), "resposta completa")])
def test_failures_are_safe_not_saved_no_fallback(tmp_path, monkeypatch, failure, expected):
    fallback = Mock(side_effect=AssertionError("OpenAI must not run"))
    monkeypatch.setattr(provider, "_post", fallback)
    transport = Mock(side_effect=failure) if isinstance(failure, Exception) else Mock(return_value=failure)
    repo = LeadRepository(tmp_path / "sales.db")
    lead = repo.create_lead({"empresa": "Empresa"})
    agent = SalesAgent(repo, OllamaSalesProvider(model="gemma3:4b", transport=transport))
    with pytest.raises(SalesGenerationError) as error:
        agent.generate(lead)
    assert expected in str(error.value) and "secret" not in str(error.value)
    assert not agent.outreach.history(lead)
    assert transport.call_count == 1
    fallback.assert_not_called()


def test_success_history_and_old_schema_migration(tmp_path):
    path = tmp_path / "sales.db"
    with sqlite3.connect(path) as connection:
        connection.execute(OUTREACH_SCHEMA)
        connection.execute("INSERT INTO outreach (lead_id,mensagem,status,criado_em,atualizado_em) VALUES (1,'Antiga','GERADA','old','old')")
    repo = LeadRepository(path)
    lead = repo.create_lead({"empresa": "Empresa"})
    agent = SalesAgent(repo, OllamaSalesProvider(model="gemma3:4b", transport=Mock(return_value=response())))
    draft = agent.generate(lead)
    initialize_database(path)
    rows = [dict(row) for row in agent.outreach.history(lead)]
    old = next(row for row in rows if row["mensagem"] == "Antiga")
    assert old["provider"] is None and old["model"] is None
    new = next(row for row in rows if row["id"] == draft)
    assert new["provider"] == "ollama" and new["model"] == "gemma3:4b"
    assert new["status"] == "GERADA" and new["enviado_em"] is None


def test_worker_surfaces_safe_error_and_restores_controls(tmp_path, monkeypatch):
    from ui import sales_panel as ui
    repo = LeadRepository(tmp_path / "sales.db")
    lead = repo.create_lead({"empresa": "Empresa"})
    selected = OllamaSalesProvider(model="gemma3:4b", transport=Mock(side_effect=ConnectionRefusedError()))
    monkeypatch.setattr(ui, "create_sales_provider", lambda: selected)
    thread = Mock()
    monkeypatch.setattr(ui.threading, "Thread", thread)
    page = SimpleNamespace(busy=False, repository=repo, lead_id=lead, snapshot=None,
        buttons=[Mock() for _ in range(5)], history=Mock(), message=Mock(), feedback=Mock(),
        pending=queue.Queue(), after=Mock(), poll=Mock(), refresh=Mock(), current_id=None, rows={})
    ui.SalesPanel.generate(page)
    assert page.busy
    selected.transport.assert_not_called()
    thread.call_args.kwargs["target"]()
    ui.SalesPanel.poll(page)
    assert not page.busy and "conectar ao Ollama" in page.feedback.configure.call_args.kwargs["text"]
    page.refresh.assert_not_called()
    page.buttons[0].configure.assert_called_with(state="normal")


def test_configuration_error_displayed_without_starting_worker(monkeypatch):
    from ui import sales_panel as ui
    monkeypatch.setattr(ui, "create_sales_provider", Mock(side_effect=SalesConfigurationError("Configure AI_MODEL")))
    page = SimpleNamespace(busy=False, repository=Mock(), feedback=Mock())
    ui.SalesPanel.generate(page)
    page.feedback.configure.assert_called_once_with(text="Configure AI_MODEL")
    assert not page.busy
