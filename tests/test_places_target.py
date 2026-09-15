"""No network: real Places parser/pagination with injected JSON responses."""
import json
from threading import Event
from unittest.mock import Mock

import pandas as pd
import pytest

from core.database import LeadRepository
from core.providers.google_places import GooglePlacesProvider, normalize_place, FIELD_MASK
from core.prospecting.adapter import candidate_to_record
from core.prospecting.service import prospect
from core.lead_filter import classificar_status_site, WebsiteStatus
from core.qualification.adapter import adapt_record_to_qualification_input


def place(name, **extra):
    return dict(id=name, displayName={"text": name}, formattedAddress="Rua A",
                nationalPhoneNumber="11999999999", rating=4.5, **extra)


def provider(monkeypatch, pages, **kwargs):
    monkeypatch.setenv("GOOGLE_PLACES_API_KEY", "synthetic-test-key")
    transport = Mock(side_effect=[(200, json.dumps(page).encode()) for page in pages])
    return GooglePlacesProvider(transport=transport, **kwargs), transport


@pytest.mark.parametrize("extra,present", [({}, False), ({"websiteUri": None}, False),
    ({"websiteUri": ""}, False), ({"websiteUri": "   "}, False),
    ({"websiteUri": "https://empresa.test"}, True), ({"websiteUri": "N/A"}, False),
    ({"displayName": {"text": "Empresa www.exemplo.com.br"}}, False),
    ({"algumOutroCampo": "Visite nosso site http://example.test"}, False)])
def test_only_official_field_controls_decision(extra, present):
    candidate = normalize_place(extra, city="Campinas", segment="dentista")
    record = candidate_to_record(candidate, website_evidence=True)
    assert classificar_status_site(record) == (WebsiteStatus.PRESENT if present else WebsiteStatus.NOT_FOUND_IN_GOOGLE)
    assert adapt_record_to_qualification_input(record).observation_status("website") == ("observed" if present else "not_found")
    assert "places.websiteUri" in FIELD_MASK.split(",")
    assert "*" not in FIELD_MASK


def test_target_paginates_dedupes_and_exports(monkeypatch, tmp_path):
    api, transport = provider(monkeypatch, [
        {"places": [place("Site", websiteUri="https://site.test"), place("Low", nationalPhoneNumber2="ignored") | {"nationalPhoneNumber": None}], "nextPageToken": "page2"},
        {"places": [place("A"), place("A"), place("B")], "nextPageToken": "unused"},
    ])
    path = tmp_path / "leads.xlsx"
    summary = prospect(city="Campinas", segment="dentista", limit=2, provider=api,
        repository=LeadRepository(tmp_path / "test.db"), only_without_website=True, export_path=path)
    assert summary.inserted == 2 and summary.requests_made == 2
    assert summary.stats == dict(analisadas=5, com_site=1, sem_site=3, duplicadas=1, descartadas=3, qualificadas=2)
    assert summary.stop_reason == "Meta atingida"
    assert "pageToken" not in transport.call_args_list[0].args[0]
    assert transport.call_args_list[1].args[0]["pageToken"] == "page2"
    frame = pd.read_excel(path)
    assert list(frame["Empresa"]) == ["A", "B"]
    assert set(frame["Status Site"]) == {"SEM_SITE_NO_GOOGLE"}
    assert all(frame["Score"] >= 60)


@pytest.mark.parametrize("mode", [False, True])
def test_normal_mode_still_accepts_website(monkeypatch, tmp_path, mode):
    api, _ = provider(monkeypatch, [{"places": [place("Site", websiteUri="https://site.test")]}])
    summary = prospect(city="A", segment="B", provider=api, repository=LeadRepository(tmp_path / "test.db"), only_without_website=mode)
    assert summary.inserted == (0 if mode else 1)
    assert (summary.stats is not None) is mode


def test_cancel_between_candidates_preserves_partial(monkeypatch, tmp_path):
    api, transport = provider(monkeypatch, [{"places": [place("A"), place("B")], "nextPageToken": "unused"}])
    event = Event()
    summary = prospect(city="A", segment="B", provider=api, repository=LeadRepository(tmp_path / "test.db"),
        only_without_website=True, cancel_event=event, progress=lambda *args: event.set(), export_path=tmp_path / "partial.xlsx")
    assert summary.cancelled and summary.inserted == summary.exported_rows == 1
    assert transport.call_count == 1


@pytest.mark.parametrize("second", ["error", "repeat", "budget"])
def test_pagination_failures_keep_accepted_leads(monkeypatch, tmp_path, second):
    pages = [{"places": [place("A")], "nextPageToken": "next"}]
    if second == "repeat":
        pages.append({"places": [], "nextPageToken": "next"})
    api, _ = provider(monkeypatch, pages, max_requests=1 if second == "budget" else 10)
    summary = prospect(city="A", segment="B", provider=api, repository=LeadRepository(tmp_path / "test.db"),
        only_without_website=True, export_path=tmp_path / "partial.xlsx")
    assert summary.inserted == summary.exported_rows == 1
    assert bool(summary.errors) is (second != "budget")
    assert "parciais" in summary.stop_reason
    assert summary.stop_code == ("safety_limit_reached" if second == "budget" else "provider_error")


def test_existing_database_duplicate_does_not_count(monkeypatch, tmp_path):
    repo = LeadRepository(tmp_path / "test.db")
    repo.create_lead(dict(empresa="A", provider="google_places", provider_place_id="A"))
    api, _ = provider(monkeypatch, [{"places": [place("A"), place("B")]}])
    summary = prospect(city="A", segment="B", provider=api, repository=repo, limit=1, only_without_website=True)
    assert summary.inserted == 1 and summary.stats["duplicadas"] == 1
    assert summary.stats["qualificadas"] == 1


def test_empty_page_with_token_and_score_boundary(monkeypatch, tmp_path):
    api, transport = provider(monkeypatch, [{"places": [], "nextPageToken": "next"}, {"places": [place("A")]}])
    summary = prospect(city="A", segment="B", provider=api, repository=LeadRepository(tmp_path / "test.db"),
        only_without_website=True, min_score=65)
    assert summary.inserted == 1 and transport.call_count == 2
    assert summary.stop_reason == "Fim dos resultados disponíveis na API"


def test_cli_selects_existing_places_service(monkeypatch):
    import main
    import core.prospecting.service as service
    run = Mock()
    monkeypatch.setattr(service, "prospect", run)
    main.cli_main(["--fonte", "google_places", "--cidades", "Campinas", "--segmentos", "dentista", "--sem-site", "--max", "20"])
    assert run.call_args.kwargs["only_without_website"] is True
    assert run.call_args.kwargs["limit"] == 20


def test_ui_passes_shared_mode_snapshot(monkeypatch):
    from test_places_ui import page
    from ui import places_search as ui
    state = page()
    state.no_website_switch.get.return_value = 1
    state.min_score.get.return_value = "65"
    monkeypatch.setattr(ui, "create_provider", Mock())
    run = Mock()
    monkeypatch.setattr(ui, "prospect", run)
    thread = Mock()
    monkeypatch.setattr(ui.threading, "Thread", thread)
    ui.PlacesSearchPage.start(state)
    thread.call_args.kwargs["target"]()
    assert run.call_args.kwargs["only_without_website"] is True
    assert run.call_args.kwargs["min_score"] == 65
    state.no_website_switch.configure.assert_called_with(state="disabled")
