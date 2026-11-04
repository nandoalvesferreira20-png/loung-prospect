"""Optional query context, no network or inferred neighborhood data."""
from unittest.mock import Mock

import pandas as pd
import pytest

from core.providers.google_places import build_query
from core.prospecting.service import prospect
from core.database import LeadRepository
from test_places_target import provider, place


@pytest.mark.parametrize("target", [False, True])
def test_payload_service_export_and_dedupe(monkeypatch, tmp_path, target):
    candidates = [place("Own", websiteUri="https://empresa.test", userRatingCount=120),
                  place("Social", websiteUri="https://instagram.com/a", userRatingCount=120),
                  place("Platform", websiteUri="https://linktr.ee/a", userRatingCount=120),
                  place("Absent", userRatingCount=120)]
    api, transport = provider(monkeypatch, [{"places": candidates}, {"places": candidates}])
    repo = LeadRepository(tmp_path / "test.db")
    args = dict(city="São Bernardo do Campo", segment="restaurante", provider=api, repository=repo, only_without_website=target)
    first = prospect(**args, export_path=tmp_path / "first.xlsx")
    second = prospect(**args, neighborhood=" Rudge Ramos ", export_path=tmp_path / "second.xlsx")
    assert transport.call_args_list[0].args[0]["textQuery"] == "restaurante em São Bernardo do Campo"
    assert transport.call_args_list[1].args[0]["textQuery"] == "restaurante em Rudge Ramos, São Bernardo do Campo"
    assert "neighborhood" not in transport.call_args.args[0]
    assert first.inserted == (3 if target else 4)
    assert second.inserted == 0 and second.duplicates == first.inserted
    frame = pd.read_excel(tmp_path / "first.xlsx")
    assert set(frame["Cidade"]) == {"São Bernardo do Campo"}
    assert "Bairro" not in frame.columns


def test_query_preserved_on_next_page(monkeypatch):
    api, transport = provider(monkeypatch, [{"places": [place("A")], "nextPageToken": "next"}, {"places": [place("B")]}])
    result = api.search(city="Santos", segment="dentista", neighborhood="Centro", max_results=2)
    assert len(result) == 2
    assert all(call.args[0]["textQuery"] == "dentista em Centro, Santos" for call in transport.call_args_list)
    assert all(item.cidade == "Santos" for item in result)


def test_cli_neighborhood(monkeypatch):
    import main
    import core.prospecting.service as service
    run = Mock()
    monkeypatch.setattr(service, "prospect", run)
    main.cli_main(["--fonte", "google_places", "--cidades", "Santos", "--segmentos", "dentista", "--bairro", "Centro"])
    assert run.call_args.kwargs["neighborhood"] == "Centro"


def test_bad_neighborhood_rejected_without_http(monkeypatch):
    api, transport = provider(monkeypatch, [])
    with pytest.raises(ValueError):
        api.search(city="A", segment="B", neighborhood=123)
    transport.assert_not_called()
