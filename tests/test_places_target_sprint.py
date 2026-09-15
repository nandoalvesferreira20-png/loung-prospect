"""Synthetic pagination beyond 60 tests orchestration, not real API coverage."""
from threading import Event
from unittest.mock import Mock

import pytest

from test_places_target import place, provider
from core.database import LeadRepository
from core.prospecting.service import prospect


def pages_with_counts(counts):
    pages = []
    for page_index, (total, accepted) in enumerate(counts):
        candidates = [place(f"lead-{page_index}-{i}", **({"websiteUri": "https://example.test"} if i < total - accepted else {})) for i in range(total)]
        pages.append({"places": candidates, "nextPageToken": f"token-{page_index}"})
    pages[-1].pop("nextPageToken")
    return pages


@pytest.mark.parametrize("counts,target,accepted,reason,requests", [
    ([(20, 1), (20, 2), (20, 2), (20, 20)], 5, 5, "target_reached", 3),
    ([(20, 1)] * 3, 30, 3, "source_exhausted", 3),
    ([(20, 0)] * 7 + [(10, 10)], 10, 10, "target_reached", 8),
])
def test_target_scenarios(monkeypatch, tmp_path, counts, target, accepted, reason, requests):
    api, transport = provider(monkeypatch, pages_with_counts(counts))
    progress = Mock()
    summary = prospect(city="A", segment="B", limit=target, provider=api,
                       repository=LeadRepository(tmp_path / "test.db"), only_without_website=True, progress=progress)
    assert summary.accepted == summary.inserted == accepted
    assert summary.target == target and summary.stop_code == reason
    assert summary.requests_made == summary.pages_fetched == transport.call_count == requests
    assert not summary.errors
    assert progress.call_args.args == (accepted, target)


def test_candidate_budget_no_additional_request(monkeypatch, tmp_path):
    api, transport = provider(monkeypatch, pages_with_counts([(20, 1)] * 5))
    summary = prospect(city="A", segment="B", limit=30, provider=api,
        repository=LeadRepository(tmp_path / "test.db"), only_without_website=True, max_candidates_scanned=40)
    assert summary.candidates_scanned == 40 and summary.accepted == 2
    assert summary.stop_code == "safety_limit_reached" and not summary.errors
    assert transport.call_count == 2


def test_existing_first_five_continue_to_five_new(monkeypatch, tmp_path):
    repo = LeadRepository(tmp_path / "test.db")
    candidates = [place(str(i)) for i in range(10)]
    for i in range(5):
        repo.create_lead(dict(empresa=str(i), provider="google_places", provider_place_id=str(i)))
    api, _ = provider(monkeypatch, [{"places": candidates}])
    summary = prospect(city="A", segment="B", limit=5, provider=api, repository=repo, only_without_website=True)
    assert summary.accepted == 5 and summary.duplicates == 5
    assert summary.candidates_scanned == 10 and summary.stop_code == "target_reached"


def test_persistence_failure_not_counted(monkeypatch, tmp_path):
    repo = LeadRepository(tmp_path / "test.db")
    repo.create_lead_if_new = Mock(side_effect=[RuntimeError("synthetic"), 1])
    api, _ = provider(monkeypatch, [{"places": [place("A"), place("B")]}])
    summary = prospect(city="A", segment="B", limit=1, provider=api, repository=repo, only_without_website=True)
    assert summary.persistence_errors == 1 and summary.accepted == 1
    assert summary.candidates_scanned == 2


def test_cancel_after_seven_keeps_rows(monkeypatch, tmp_path):
    api, _ = provider(monkeypatch, pages_with_counts([(20, 20), (20, 20)]))
    event = Event()
    repo = LeadRepository(tmp_path / "test.db")
    def progress(done, total):
        if done == 7:
            event.set()
    summary = prospect(city="A", segment="B", limit=30, provider=api, repository=repo,
                       only_without_website=True, cancel_event=event, progress=progress)
    assert summary.accepted == repo.count_leads() == 7
    assert summary.stop_code == "cancelled" and summary.requests_made == 1


def test_same_name_without_address_uses_distinct_place_ids(monkeypatch, tmp_path):
    api, _ = provider(monkeypatch, [{"places": [place("A") | {"formattedAddress": None, "displayName": {"text": "Marca"}},
                                               place("B") | {"formattedAddress": None, "displayName": {"text": "Marca"}, "nationalPhoneNumber": "222"}]}])
    summary = prospect(city="A", segment="B", provider=api, repository=LeadRepository(tmp_path / "test.db"),
                       only_without_website=True, min_score=0)
    assert summary.accepted == 2


def test_ui_exhaustion_does_not_show_full_progress():
    from test_places_ui import page
    from core.prospecting.service import ProspectingSummary
    state = page()
    summary = ProspectingSummary(requested=20, inserted=5, stats={"analisadas": 60, "com_site": 55})
    state.pending.put(("done", summary))
    state.poll()
    assert state.progress.set.call_args.args == (0.25,)
