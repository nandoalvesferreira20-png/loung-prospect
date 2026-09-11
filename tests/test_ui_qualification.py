from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from ui import home
from ui.dialogs import format_finish_summary
from core import scraper
from core.qualification.models import QualificationResult


def fake_home():
    page = SimpleNamespace(running=False, stop_requested=False)
    for name in ("cidades", "segmentos", "quantidade", "output", "qualification_switch",
                 "progress", "progress_label", "timer_label", "start_btn", "stop_btn"):
        setattr(page, name, Mock())
    for name in ("log", "update_timer", "stop_timer", "worker", "after",
                 "finish_search", "update_progress", "handle_error"):
        setattr(page, name, Mock())
    page.cidades.get.return_value = "Cidade"
    page.segmentos.get.return_value = "Clínica"
    page.quantidade.get.return_value = "5"
    page.output.get.return_value = "leads.xlsx"
    page.set_form_state = lambda state: home.HomePage.set_form_state(page, state)
    page.restore_interface = lambda: home.HomePage.restore_interface(page)
    return page


def test_switch_default_off_and_label(monkeypatch):
    for name in ("CTkLabel", "CTkFrame", "CTkEntry", "CTkButton", "CTkProgressBar", "CTkTextbox"):
        monkeypatch.setattr(home.ctk, name, Mock())
    switch = Mock()
    monkeypatch.setattr(home.ctk, "CTkSwitch", switch)
    page = SimpleNamespace(log=Mock(), start_search=Mock(), stop_search=Mock())
    home.HomePage.build_ui(page)
    assert switch.call_args.kwargs["text"] == "Qualificar leads automaticamente"
    switch.return_value.deselect.assert_called_once()


@pytest.mark.parametrize("enabled", [False, True])
def test_switch_snapshot_forwarded_and_locked(monkeypatch, enabled):
    page = fake_home()
    page.qualification_switch.get.return_value = int(enabled)
    thread = Mock()
    monkeypatch.setattr(home.threading, "Thread", thread)
    home.HomePage.start_search(page)
    assert thread.call_args.kwargs["args"][-1] is enabled
    page.qualification_switch.configure.assert_called_with(state="disabled")
    thread.return_value.start.assert_called_once()
    run = Mock(return_value={})
    monkeypatch.setattr(home, "run_scraper", run)
    home.HomePage.worker(page, *thread.call_args.kwargs["args"])
    assert run.call_args.kwargs["qualification_enabled"] is enabled
    home.HomePage.stop_search(page)
    assert run.call_args.kwargs["should_stop"]() is True
    page.stop_btn.configure.assert_called_with(state="disabled", text="Parando...")


@pytest.mark.parametrize("status", ["concluído", "cancelado"])
def test_finish_restores_switch(monkeypatch, status):
    page = fake_home()
    monkeypatch.setattr(home, "show_finish_dialog", Mock())
    home.HomePage.finish_search(page, {"status": status})
    assert page.running is False
    page.qualification_switch.configure.assert_called_with(state="normal")


def test_unexpected_error_restores_switch(monkeypatch):
    page = fake_home()
    monkeypatch.setattr(home.messagebox, "showerror", Mock())
    home.HomePage.handle_error(page, "Synthetic")
    page.qualification_switch.configure.assert_called_with(state="normal")


def test_legacy_summary_text():
    text = format_finish_summary({"leads": 2, "falhas": 0, "tempo_segundos": 1.0})
    assert "Leads exportados: 2" in text
    assert "Qualificados" not in text


def test_aggregates_and_display(harness, lead_factory, monkeypatch):
    harness.links.return_value = ["a", "b", "c"]
    harness.extract.side_effect = [lead_factory(Empresa=name) for name in ("A", "B", "C")]
    monkeypatch.setattr(scraper, "qualify_records", Mock(return_value=[
        QualificationResult("qualified", opportunity="website"),
        QualificationResult("insufficient_data", opportunity="needs_review"),
        QualificationResult("error"),
    ]))
    summary = harness.run(qualification_enabled=True)
    assert summary["qualification_summary"] == dict(qualified=1, insufficient_data=1, error=1, website_opportunities=1)
    text = format_finish_summary(summary)
    for expected in ("Leads exportados: 3", "Qualificados: 1", "Oportunidades de website: 1",
                     "Dados insuficientes: 1", "Erros de qualificação: 1"):
        assert expected in text


def test_empty_qualification_aggregates(harness):
    harness.links.return_value = []
    summary = harness.run(qualification_enabled=True)
    assert summary["qualification_summary"] == dict(qualified=0, insufficient_data=0, error=0, website_opportunities=0)
