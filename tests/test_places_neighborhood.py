"""Optional query context, no network or inferred neighborhood data."""
from unittest.mock import Mock

import pandas as pd
import pytest

from core.providers.google_places import build_query
from core.prospecting.service import prospect
from core.database import LeadRepository
from ui.places_logic import parse_search
from test_places_target import provider, place


@pytest.mark.parametrize("neighborhood,location", [(None, "São Bernardo do Campo"), ("", "São Bernardo do Campo"),
    ("  ", "São Bernardo do Campo"), ("  Rudge Ramos  ", "Rudge Ramos, São Bernardo do Campo"),
    ("Jardim do Mar", "Jardim do Mar, São Bernardo do Campo"), ("Baeta Neves", "Baeta Neves, São Bernardo do Campo"),
    ("Vila São-José", "Vila São-José, São Bernardo do Campo")])
def test_query_and_parse(neighborhood, location):
    params = parse_search(" São Bernardo do Campo ", " restaurante ", "5", neighborhood)
    assert params["neighborhood"] == (neighborhood.strip() or None if neighborhood is not None else None)
    assert build_query(params["city"], params["segment"], params["neighborhood"]) == f"restaurante em {location}"


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


def test_ui_snapshot_and_lifecycle(monkeypatch):
    from test_places_ui import page
    from ui import places_search as ui
    state = page()
    assert state.entries["neighborhood"].get() == ""
    state.entries["neighborhood"].get.return_value = " Rudge Ramos "
    monkeypatch.setattr(ui, "create_provider", Mock())
    run, thread = Mock(), Mock()
    monkeypatch.setattr(ui, "prospect", run)
    monkeypatch.setattr(ui.threading, "Thread", thread)
    ui.PlacesSearchPage.start(state)
    state.entries["neighborhood"].get.return_value = "Mudou depois"
    thread.call_args.kwargs["target"]()
    assert run.call_args.kwargs["neighborhood"] == "Rudge Ramos"
    state.entries["neighborhood"].configure.assert_called_with(state="disabled")
    ui.PlacesSearchPage.cancel(state)
    assert state.cancel_event.is_set()
    ui.PlacesSearchPage.set_running(state, False)
    state.entries["neighborhood"].configure.assert_called_with(state="normal")


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
