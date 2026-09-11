"""Headless UI lifecycle checks: no Tk root, thread, browser or API."""
import queue
from threading import Event
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from ui import places_search as ui
from core.prospecting.service import ProspectingSummary
from core.providers.google_places import GooglePlacesConfigurationError


def page():
    state = SimpleNamespace(running=False, pending=queue.Queue(), cancel_event=Event(), poll_job=None,
        entries={key: Mock(get=Mock(return_value=value)) for key, value in
                 (("city", "Taubaté"), ("segment", "dentista"), ("quantity", "5"))},
        start_button=Mock(), cancel_button=Mock(), progress=Mock(), append=Mock(), after=Mock(return_value="job"))
    state.set_running = lambda value: ui.PlacesSearchPage.set_running(state, value)
    state.poll = lambda: ui.PlacesSearchPage.poll(state)
    return state


def test_start_runs_only_on_action_and_uses_worker(monkeypatch):
    state = page()
    provider = Mock()
    monkeypatch.setattr(ui, "create_provider", Mock(return_value=provider))
    run = Mock(return_value=ProspectingSummary(requested=5))
    monkeypatch.setattr(ui, "prospect", run)
    thread = Mock()
    monkeypatch.setattr(ui.threading, "Thread", thread)
    run.assert_not_called()
    ui.PlacesSearchPage.start(state)
    assert state.running
    state.start_button.configure.assert_called_with(state="disabled")
    thread.return_value.start.assert_called_once()
    run.assert_not_called()
    ui.PlacesSearchPage.start(state)
    assert thread.call_count == 1
    # Simulate worker execution; widget methods are never invoked by the worker.
    state.progress.reset_mock()
    thread.call_args.kwargs["target"]()
    state.progress.configure.assert_not_called()
    assert run.call_args.kwargs["provider"] is provider
    assert run.call_args.kwargs["limit"] == 5
    state.poll()
    assert not state.running
    state.start_button.configure.assert_called_with(state="normal")


def test_missing_key_never_starts(monkeypatch):
    state = page()
    monkeypatch.setattr(ui, "create_provider", Mock(side_effect=GooglePlacesConfigurationError("private")))
    thread = Mock()
    monkeypatch.setattr(ui.threading, "Thread", thread)
    message = Mock()
    monkeypatch.setattr(ui.messagebox, "showerror", message)
    ui.PlacesSearchPage.start(state)
    assert not state.running
    thread.assert_not_called()
    assert "GOOGLE_PLACES_API_KEY" in message.call_args.args[1]
    assert "private" not in message.call_args.args[1]


@pytest.mark.parametrize("event", [("done", ProspectingSummary(requested=5, inserted=1)), ("error", "Falha segura")])
def test_completion_restores_controls(event):
    state = page()
    state.set_running(True)
    state.pending.put(("progress", 0.5))
    state.pending.put(event)
    state.poll()
    assert not state.running
    for entry in state.entries.values():
        entry.configure.assert_called_with(state="normal")
    state.cancel_button.configure.assert_called_with(state="disabled")


def test_cancel_is_cooperative():
    state = page()
    ui.PlacesSearchPage.cancel(state)
    assert state.cancel_event.is_set()


def test_environment_loader_is_shared_and_does_not_override(tmp_path, monkeypatch):
    import sys
    from core.providers import environment
    from scripts import test_google_places_real
    (tmp_path / ".env").write_text("GOOGLE_PLACES_API_KEY=", encoding="utf-8")
    monkeypatch.setattr(environment, "ROOT", tmp_path)
    loader = Mock()
    monkeypatch.setitem(sys.modules, "dotenv", SimpleNamespace(load_dotenv=loader))
    environment.load_environment()
    loader.assert_called_once_with(tmp_path / ".env", override=False, interpolate=False)
    assert test_google_places_real.load_environment is environment.load_environment
