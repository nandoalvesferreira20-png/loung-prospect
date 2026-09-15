"""Accepted-lead targets with synthetic records, pages and real V3 rules."""
from copy import deepcopy
from unittest.mock import Mock

import pandas as pd
import pytest

from core import scraper, maps
from core.lead_filter import possui_site, classificar_status_site, WebsiteStatus
from core.validator import WebsiteVerification, with_website_verification


@pytest.mark.parametrize("value,present", [(None, False), ("", False), ("  ", False),
    ("None", False), ("N/A", False), (float("nan"), False), ("https://example.test", True),
    ("https://instagram.com/test", True)])
def test_website_field_presence_is_not_absence_evidence(value, present):
    row = {"Site": value}
    assert possui_site(row) is present
    assert classificar_status_site(row) == (WebsiteStatus.PRESENT if present else WebsiteStatus.UNVERIFIED)
    assert possui_site({"site": value}) is present


@pytest.fixture
def target(harness, lead_factory, monkeypatch):
    discovery = Mock(return_value=iter(()))
    monkeypatch.setattr(scraper, "iter_links", discovery)

    def lead(name, site="", verified=True, **values):
        row = lead_factory(Empresa=name, Site=site, Telefone="11999999999", Avaliação="4.5", **values)
        if verified:
            row = with_website_verification(row, WebsiteVerification(
                source_url=row["Google Maps"], completed=True, website_found=bool(site), website_source="explicit_control"))
        return row

    def run(records, links=None, **options):
        discovery.return_value = iter(links if links is not None else [str(i) for i in range(len(records))])
        harness.extract.side_effect = records
        return harness.run(only_without_website=True, **options)

    return run, lead, discovery


def test_target_counts_only_accepted_and_stops_consuming(target, harness):
    run, lead, discovery = target
    records = [lead("Com site", "https://example.test"), lead("A"), lead("A")]
    low = lead("Baixo")
    low["Telefone"] = ""
    records += [low, lead("B"), lead("Não abrir")]
    original = deepcopy(records)
    summary = run(records, max_results=2)
    assert summary["leads"] == 2 and summary["processados"] == 5
    assert summary["stats"] == dict(analisadas=5, com_site=1, sem_site=3, duplicadas=1, descartadas=3, qualificadas=2)
    assert summary["motivo_parada"] == "Meta atingida"
    assert harness.extract.call_count == 5
    harness.links.assert_not_called()
    frame = pd.read_excel(harness.output)
    assert list(frame["Empresa"]) == ["A", "B"]
    assert set(frame["Status Site"]) == {"SEM_SITE_NO_GOOGLE"}
    assert all(frame["Score"] >= 60)
    assert list(frame["Score"]) == list(frame["Qualification Score"])
    assert "_website_verification" not in frame
    assert set(frame["Status Comercial"]) == {"Novo Lead"}
    assert len(summary["qualificacoes"]) == 2
    assert records == original
    assert harness.progress.call_args.args[:2] == (2, 2)


@pytest.mark.parametrize("score,accepted", [(65, 1), (66, 0), (0, 1), (100, 0)])
def test_minimum_score_inclusive(target, score, accepted):
    run, lead, _ = target
    assert run([lead("A")], min_score=score)["leads"] == accepted


def test_inconclusive_or_error_never_accepted(target):
    run, lead, _ = target
    unknown = lead("Não verificado", verified=False)
    error = lead("Erro")
    error["_website_verification"] = WebsiteVerification(error["Google Maps"], error=True)
    result = run([unknown, error], min_score=0)
    assert result["leads"] == 0 and result["stats"]["sem_site"] == 0
    assert result["arquivo"] is None


def test_duplicate_links_do_not_consume_goal(target):
    run, lead, _ = target
    summary = run([lead("A"), lead("B")], links=["a", "a", "b"], max_results=2)
    assert summary["leads"] == 2 and summary["processados"] == 2
    assert summary["stats"]["duplicadas"] == 1


def test_cancel_exports_partial(target, harness):
    run, lead, _ = target
    stop = False
    def progress(accepted, total, message):
        nonlocal stop
        stop = accepted == 1
    summary = run([lead("A"), lead("B")], should_stop=lambda: stop, on_progress=progress)
    assert summary["status"] == "cancelado" and summary["leads"] == 1
    assert len(pd.read_excel(harness.output)) == 1


def test_empty_and_exhausted_search(target):
    run, lead, _ = target
    summary = run([lead("A")], max_results=30)
    assert summary["leads"] == 1 and summary["meta"] == 30
    assert "limites de rolagem" in summary["motivo_parada"]


def test_no_links(target):
    run, _, _ = target
    summary = run([])
    assert summary["leads"] == summary["processados"] == 0


def test_cancel_before_discovery(target):
    run, lead, discover = target
    summary = run([lead("A")], should_stop=lambda: True)
    assert summary["status"] == "cancelado"
    discover.assert_not_called()


def test_qualification_failure_continues(target, monkeypatch):
    run, lead, _ = target
    original = scraper.qualify_records
    def qualify(records):
        if records[0]["Empresa"] == "Falha":
            raise RuntimeError("Falha sintética")
        return original(records)
    monkeypatch.setattr(scraper, "qualify_records", qualify)
    summary = run([lead("Falha"), lead("A")])
    assert summary["leads"] == 1 and summary["falhas"] == 1


def test_incremental_discovery_stops_without_new_links(monkeypatch):
    page = Mock()
    anchors = page.locator.return_value
    anchors.count.return_value = 1
    anchors.nth.return_value.get_attribute.return_value = "a"
    scroll = Mock()
    monkeypatch.setattr(maps, "scroll_results", scroll)
    assert list(maps.iter_links(page, "Dentista em Campinas", log=Mock())) == ["a"]
    assert scroll.call_count == 3


def test_incremental_discovery_is_lazy_and_cancellable(monkeypatch):
    page = Mock()
    anchors = page.locator.return_value
    anchors.count.return_value = 2
    anchors.nth.return_value.get_attribute.side_effect = ["a", "b"]
    scroll = Mock()
    monkeypatch.setattr(maps, "scroll_results", scroll)
    stop = False
    iterator = maps.iter_links(page, "query", should_stop=lambda: stop)
    assert next(iterator) == "a"
    stop = True
    assert list(iterator) == []
    scroll.assert_not_called()
    assert anchors.nth.return_value.get_attribute.call_count == 1


def test_invalid_score_before_browser(harness):
    with pytest.raises(ValueError):
        harness.run(only_without_website=True, min_score=101)
    harness.playwright.chromium.launch.assert_not_called()


def test_multiple_searches_share_one_goal(target, harness):
    _, lead, discovery = target
    discovery.side_effect = [iter(["a"]), iter(["a", "b", "c"])]
    harness.extract.side_effect = [lead("A"), lead("B"), lead("Não abrir")]
    summary = harness.run(only_without_website=True, cidades=["A", "B", "Não buscar"], max_results=2)
    assert summary["leads"] == 2 and discovery.call_count == 2
    assert harness.extract.call_count == 2
    assert summary["stats"]["duplicadas"] == 1


def test_discovery_failure_moves_to_next_search(target, harness):
    _, lead, discovery = target
    discovery.side_effect = [RuntimeError("Falha sintética"), iter(["b"])]
    harness.extract.side_effect = [lead("B")]
    summary = harness.run(only_without_website=True, cidades=["A", "B"])
    assert summary["leads"] == 1 and summary["falhas"] == 1
    assert "falhas" in summary["motivo_parada"]


def test_returned_qualification_error_does_not_enter_export(target, monkeypatch):
    from core.qualification.models import QualificationResult
    run, lead, _ = target
    actual = scraper.qualify_records
    calls = []
    def qualify(records):
        calls.append(records[0]["Empresa"])
        return [QualificationResult("error")] if len(calls) == 1 else actual(records)
    monkeypatch.setattr(scraper, "qualify_records", qualify)
    summary = run([lead("Erro"), lead("A")])
    assert summary["leads"] == 1
    assert calls == ["Erro", "A"]  # accepted leads are not qualified a second time


def test_discovery_scroll_safety_limit(monkeypatch):
    page = Mock()
    page.locator.return_value.count.return_value = 1
    page.locator.return_value.nth.return_value.get_attribute.side_effect = ["a", "b", "c"]
    scroll = Mock()
    monkeypatch.setattr(maps, "scroll_results", scroll)
    assert list(maps.iter_links(page, "query", log=Mock(), max_scroll_attempts=2)) == ["a", "b", "c"]
    assert scroll.call_count == 2


def test_cli_routes_explicit_mode_and_preserves_legacy(monkeypatch):
    import main
    legacy = Mock()
    modular = Mock()
    monkeypatch.setattr(main, "run", legacy)
    monkeypatch.setattr(scraper, "run_scraper", modular)
    arguments = ["--cidades", "Campinas", "--segmentos", "dentista", "--max", "30"]
    main.cli_main(arguments)
    legacy.assert_called_once()
    modular.assert_not_called()
    main.cli_main(arguments + ["--sem-site", "--min-score", "65"])
    assert modular.call_args.args[:3] == (["Campinas"], ["dentista"], 30)
    assert modular.call_args.kwargs["only_without_website"] is True
    assert modular.call_args.kwargs["min_score"] == 65


def test_ui_target_snapshot_validation_and_locked_fields(monkeypatch):
    from test_ui_qualification import fake_home
    from ui import home
    page = fake_home()
    page.no_website_switch.get.return_value = 1
    page.min_score.get.return_value = "65"
    page.qualification_switch.get.return_value = 0
    thread = Mock()
    monkeypatch.setattr(home.threading, "Thread", thread)
    run = Mock(return_value={})
    monkeypatch.setattr(home, "run_scraper", run)
    home.HomePage.start_search(page)
    home.HomePage.worker(page, *thread.call_args.kwargs["args"])
    assert run.call_args.kwargs["only_without_website"] is True
    assert run.call_args.kwargs["min_score"] == 65
    page.no_website_switch.configure.assert_called_with(state="disabled")
    page.min_score.configure.assert_called_with(state="disabled")
    home.HomePage.restore_interface(page)
    page.no_website_switch.configure.assert_called_with(state="normal")


def test_finish_summary_explains_target(target):
    from ui.dialogs import format_finish_summary
    run, lead, _ = target
    summary = run([lead("A")], max_results=30)
    text = format_finish_summary(summary)
    assert "Meta: 30 · Aceitos: 1" in text
    assert "Analisadas: 1" in text and "limites de rolagem" in text


def test_target_ui_default_enabled(monkeypatch):
    from types import SimpleNamespace
    from ui import home
    for name in ("CTkLabel", "CTkFrame", "CTkEntry", "CTkButton", "CTkProgressBar", "CTkTextbox"):
        monkeypatch.setattr(home.ctk, name, Mock())
    target_switch, qualification_switch = Mock(), Mock()
    monkeypatch.setattr(home.ctk, "CTkSwitch", Mock(side_effect=[target_switch, qualification_switch]))
    page = SimpleNamespace(log=Mock(), start_search=Mock(), stop_search=Mock())
    home.HomePage.build_ui(page)
    target_switch.select.assert_called_once()
    qualification_switch.deselect.assert_called_once()
