from copy import deepcopy
import json
from unittest.mock import Mock

import pytest

from core.providers.google_places import (
    GooglePlacesProvider, GooglePlacesError, GooglePlacesConfigurationError,
    FIELD_MASK, build_query, normalize_place,
)


@pytest.fixture
def factory(monkeypatch):
    monkeypatch.setenv("GOOGLE_PLACES_API_KEY", "synthetic-secret")
    def make(pages):
        transport = Mock(side_effect=[(200, json.dumps(page).encode()) for page in pages])
        return GooglePlacesProvider(transport=transport), transport
    return make


def test_missing_key(monkeypatch):
    monkeypatch.delenv("GOOGLE_PLACES_API_KEY", raising=False)
    with pytest.raises(GooglePlacesConfigurationError):
        GooglePlacesProvider(transport=Mock())


def test_normalization_and_nonmutation():
    place = dict(id="place-id", displayName={"text": "Clínica Árvore"}, formattedAddress="Rua A",
                 nationalPhoneNumber="123", websiteUri="https://example.test", rating=4.5,
                 userRatingCount=20, googleMapsUri="https://maps.example.test", location={"latitude": -23.0, "longitude": -45.0})
    before = deepcopy(place)
    lead = normalize_place(place, city="Taubaté", segment="dentista")
    assert (lead.provider, lead.provider_place_id, lead.empresa) == ("google_places", "place-id", "Clínica Árvore")
    assert (lead.cidade, lead.segmento, lead.telefone, lead.whatsapp) == ("Taubaté", "dentista", "123", None)
    assert (lead.avaliacao, lead.quantidade_avaliacoes, lead.latitude, lead.longitude) == (4.5, 20, -23.0, -45.0)
    assert lead.site == "https://example.test" and lead.endereco == "Rua A"
    assert lead.google_maps == "https://maps.example.test"
    assert place == before
    assert normalize_place({}, city="C", segment="S").telefone is None


def test_query_headers_and_timeout(factory):
    provider, transport = factory([{"places": [{"id": "1"}]}])
    assert build_query(" Taubaté ", " dentista ") == "dentista em Taubaté"
    assert len(provider.search(city="Taubaté", segment="dentista", max_results=1)) == 1
    payload, headers, timeout = transport.call_args.args
    assert payload == dict(textQuery="dentista em Taubaté", languageCode="pt-BR", pageSize=1)
    assert headers["X-Goog-Api-Key"] == "synthetic-secret"
    assert headers["X-Goog-FieldMask"] == FIELD_MASK and "*" not in FIELD_MASK
    assert "nextPageToken" in FIELD_MASK and "places.nationalPhoneNumber" in FIELD_MASK
    assert timeout == 30


@pytest.mark.parametrize("limit,pages", [(1, 1), (20, 1), (21, 2), (50, 3)])
def test_pagination_stops_at_limit(factory, limit, pages):
    provider, transport = factory([{"places": [{"id": str(i)} for i in range(20)], "nextPageToken": token} for token in ("a", "b", "c")])
    assert len(provider.search(city="C", segment="S", max_results=limit)) == limit
    assert provider.request_count == transport.call_count == pages
    if pages > 1:
        assert transport.call_args_list[1].args[0]["pageToken"] == "a"


def test_empty_and_zero(factory):
    provider, transport = factory([{}])
    assert provider.search(city="C", segment="S", max_results=0) == []
    transport.assert_not_called()
    assert provider.search(city="C", segment="S") == []
    assert provider.request_count == 1


@pytest.mark.parametrize("status", [400, 401, 403, 429, 500])
def test_http_errors_no_retry_or_key_leak(factory, status):
    provider, transport = factory([])
    transport.side_effect = None
    transport.return_value = status, b"synthetic-secret"
    with pytest.raises(GooglePlacesError) as error:
        provider.search(city="C", segment="S")
    assert "synthetic-secret" not in str(error.value)
    assert transport.call_count == 1


@pytest.mark.parametrize("failure", [TimeoutError("synthetic-secret"), ConnectionError("synthetic-secret")])
def test_transport_errors(factory, failure):
    provider, transport = factory([])
    transport.side_effect = failure
    with pytest.raises(GooglePlacesError) as error:
        provider.search(city="C", segment="S")
    assert "synthetic-secret" not in str(error.value)
    assert error.value.__cause__ is None


@pytest.mark.parametrize("raw", [b"broken", b"[]", b'{"places":null}', b'{"places":[1]}', b'{"error":{"message":"synthetic-secret"}}', b'{"places":[{"displayName":3}]}'])
def test_bad_responses(factory, raw):
    provider, transport = factory([])
    transport.side_effect = None
    transport.return_value = 200, raw
    with pytest.raises(GooglePlacesError) as error:
        provider.search(city="C", segment="S")
    assert "synthetic-secret" not in str(error.value)


def test_budget_and_safe_logs(factory):
    provider, transport = factory([{"nextPageToken": "a"}, {"nextPageToken": "b"}])
    provider.max_requests = 1
    log = Mock()
    provider._log = log
    with pytest.raises(GooglePlacesError, match="budget"):
        provider.search(city="C", segment="S")
    assert transport.call_count == 1
    assert "synthetic-secret" not in repr(log.call_args_list)
