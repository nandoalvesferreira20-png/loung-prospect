"""Groq SDK requests use MockTransport only: no account, network or real key."""
import json
from unittest.mock import Mock

import groq
import httpx
import pytest

from core.sales.groq_provider import GroqSalesProvider
from core.sales.errors import SalesConfigurationError, SalesProviderError
from core.sales import provider
from core.sales.agent import SalesAgent, SalesGenerationError
from core.database.lead_repository import LeadRepository

ANSWER = dict(mensagem="Oi, sou Fernando, da Loung Tech. Posso compartilhar uma ideia sobre organização de contatos?",
              angulo="organização de contatos", confianca=0.8)


def sdk_provider(handler):
    factory = Mock(side_effect=lambda **kwargs: groq.Groq(**kwargs,
        http_client=httpx.Client(transport=httpx.MockTransport(handler))))
    return GroqSalesProvider(key="synthetic-test-key", model="test-model", client_factory=factory), factory


def completion(answer=ANSWER, finish="stop"):
    return {"id": "test", "object": "chat.completion", "created": 1, "model": "test-model",
        "choices": [{"index": 0, "finish_reason": finish, "message": {
            "role": "assistant", "content": json.dumps(answer)}}]}


def test_official_sdk_request_and_response():
    requests = []
    def handler(request):
        requests.append(request)
        return httpx.Response(200, json=completion())
    selected, factory = sdk_provider(handler)
    assert selected.generate(system_prompt="rules JSON", evidence={"empresa": "Clínica X"}) == ANSWER
    assert len(requests) == 1
    assert str(requests[0].url) == "https://api.groq.com/openai/v1/chat/completions"
    payload = json.loads(requests[0].content)
    assert payload["model"] == "test-model" and payload["stream"] is False
    assert payload["response_format"] == {"type": "json_object"}
    assert payload["messages"][0]["content"] == "rules JSON"
    assert json.loads(payload["messages"][1]["content"]) == {"empresa": "Clínica X"}
    assert "tools" not in payload
    assert factory.call_args.kwargs["max_retries"] == 0
    assert factory.call_args.kwargs["timeout"] == 60


@pytest.mark.parametrize("status,expected", [(401, "credencial"), (403, "permissões"), (429, "429"), (500, "rejeitou"), (400, "GROQ_MODEL")])
def test_http_errors_sanitized_no_retries(status, expected):
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(status, json={"error": {"message": "synthetic-test-key private body"}})
    selected, _ = sdk_provider(handler)
    with pytest.raises(SalesProviderError) as error:
        selected.generate(system_prompt="rules", evidence={})
    assert expected in str(error.value)
    assert "synthetic" not in str(error.value) and "body" not in str(error.value)
    assert len(calls) == 1


@pytest.mark.parametrize("exception,expected", [(httpx.ConnectError, "conectar"), (httpx.ReadTimeout, "tempo")])
def test_network_errors(exception, expected):
    def handler(request):
        raise exception("private", request=request)
    selected, _ = sdk_provider(handler)
    with pytest.raises(SalesProviderError, match=expected):
        selected.generate(system_prompt="rules", evidence={})


@pytest.mark.parametrize("body", [completion({}, "stop"), completion(ANSWER, "length"), completion(ANSWER | {"confianca": 87}),
    completion(ANSWER | {"mensagem": ""}), {"choices": []}])
def test_invalid_response_never_saved(tmp_path, body):
    selected, _ = sdk_provider(lambda req: httpx.Response(200, json=body))
    repo = LeadRepository(tmp_path / "test.db")
    lead = repo.create_lead({"empresa": "Test"})
    agent = SalesAgent(repo, selected)
    with pytest.raises(SalesGenerationError):
        agent.generate(lead)
    assert agent.outreach.history(lead) == []


def test_factory_uses_groq_settings_only(monkeypatch):
    monkeypatch.setattr(provider, "load_environment", lambda: None)
    monkeypatch.setenv("AI_PROVIDER", "groq")
    monkeypatch.delenv("AI_API_KEY", raising=False)
    monkeypatch.setenv("AI_MODEL", "other-provider-model")
    monkeypatch.setenv("GROQ_API_KEY", "synthetic-test-key")
    monkeypatch.setenv("GROQ_MODEL", "test-model")
    monkeypatch.setenv("GROQ_TIMEOUT", "90")
    selected = provider.create_sales_provider()
    assert isinstance(selected, GroqSalesProvider) and selected.model == "test-model"
    assert selected.timeout == 90
    monkeypatch.delenv("GROQ_MODEL")
    with pytest.raises(SalesConfigurationError):
        provider.create_sales_provider()


@pytest.mark.parametrize("timeout", [0, -1, "bad", "nan", 301])
def test_timeout_configuration(timeout):
    with pytest.raises(SalesConfigurationError):
        GroqSalesProvider(key="synthetic", model="test", timeout=timeout)
