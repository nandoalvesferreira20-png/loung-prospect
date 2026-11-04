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
