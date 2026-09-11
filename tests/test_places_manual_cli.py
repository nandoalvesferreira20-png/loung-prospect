from unittest.mock import Mock
import json

import pytest

from scripts import test_google_places_real as cli
from core.providers.models import LeadCandidate
from core.providers.google_places import GooglePlacesConfigurationError, GooglePlacesHTTPError
from core.providers.google_places import GooglePlacesProvider


@pytest.fixture(autouse=True)
def no_real_environment(monkeypatch):
    monkeypatch.setattr(cli, "load_environment", Mock())


@pytest.mark.parametrize("args,city,segment,limit", [([], "Taubaté", "dentista", 5),
    (["--city", "Santos", "--segment", "veterinario", "--limit", "3"], "Santos", "veterinario", 3)])
def test_single_search(monkeypatch, capsys, args, city, segment, limit):
    provider = Mock(request_count=1)
    provider.search.return_value = [LeadCandidate("google_places", empresa="Clínica", avaliacao=0)]
    constructor = Mock(return_value=provider)
    monkeypatch.setattr(cli, "GooglePlacesProvider", constructor)
    assert cli.main(args) == 0
    constructor.assert_called_once_with(max_requests=1)
    provider.search.assert_called_once_with(city=city, segment=segment, max_results=limit)
    output = capsys.readouterr().out
    assert "WhatsApp: Não disponível" in output
    assert "Avaliação: 0" in output
    assert "Resultados recebidos: 1" in output


@pytest.mark.parametrize("limit", ["0", "21", "abc", "-1"])
def test_invalid_limit_never_calls_provider(monkeypatch, limit):
    provider = Mock()
    monkeypatch.setattr(cli, "GooglePlacesProvider", provider)
    with pytest.raises(SystemExit) as error:
        cli.main(["--limit", limit])
    assert error.value.code != 0
    provider.assert_not_called()


@pytest.mark.parametrize("error", [GooglePlacesConfigurationError("hidden"), GooglePlacesHTTPError(403), RuntimeError("hidden")])
def test_sanitized_failure(monkeypatch, capsys, error):
    monkeypatch.setattr(cli, "GooglePlacesProvider", Mock(side_effect=error))
    assert cli.main([]) == 1
    output = capsys.readouterr().err
    assert output and "hidden" not in output and "Traceback" not in output


def test_http_400_api_diagnostic_is_sanitized(monkeypatch, capsys):
    monkeypatch.setenv("GOOGLE_PLACES_API_KEY", "synthetic-secret")
    body = {"error": {"status": "INVALID_ARGUMENT", "message": "Invalid field\nsynthetic-secret",
                      "details": [{"private": "DO_NOT_PRINT"}]}, "headers": "DO_NOT_PRINT"}
    transport = Mock(return_value=(400, json.dumps(body).encode()))
    provider = GooglePlacesProvider(transport=transport)
    monkeypatch.setattr(cli, "GooglePlacesProvider", Mock(return_value=provider))
    assert cli.main([]) == 1
    output = capsys.readouterr().err
    assert "INVALID_ARGUMENT | Invalid field [REDACTED]" in output
    assert "Requests realizadas: 1" in output
    assert all(text not in output for text in ("synthetic-secret", "DO_NOT_PRINT", "Traceback"))
    transport.assert_called_once()
