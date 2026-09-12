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
    state = SimpleNamespace(
        running=False,
        pending=queue.Queue(),
        cancel_event=Event(),
        poll_job=None,
        last_exported_file=None,
        entries={
            key: Mock(
                get=Mock(return_value=value)
            )
            for key, value in (
                ("city", "Taubaté"),
                ("segment", "dentista"),
                ("quantity", "5"),
            )
        },
        run_status=Mock(),
        metrics=Mock(),
        priority_summary=Mock(),
        start_button=Mock(),
        cancel_button=Mock(),
        export_checkbox=Mock(),
        open_excel_button=Mock(),
        open_folder_button=Mock(),
        export_var=Mock(),
        progress=Mock(),
        append=Mock(),
        after=Mock(return_value="job"),
    )

    # Export enabled by default, matching the real UI.
    state.export_var.get.return_value = True

    state.set_running = (
        lambda value:
        ui.PlacesSearchPage.set_running(
            state,
            value,
        )
    )

    state.poll = (
        lambda:
        ui.PlacesSearchPage.poll(
            state
        )
    )

    state.build_export_path = (
        lambda city, segment:
        ui.Path(
            "output/google_places/"
            "taubate_dentista_test.xlsx"
        )
    )

    return state


def test_start_runs_only_on_action_and_uses_worker(
    monkeypatch,
):
    state = page()

    provider = Mock()

    monkeypatch.setattr(
        ui,
        "create_provider",
        Mock(return_value=provider),
    )

    run = Mock(
        return_value=ProspectingSummary(
            requested=5
        )
    )

    monkeypatch.setattr(
        ui,
        "prospect",
        run,
    )

    thread = Mock()

    monkeypatch.setattr(
        ui.threading,
        "Thread",
        thread,
    )

    run.assert_not_called()

    ui.PlacesSearchPage.start(
        state
    )

    assert state.running

    state.start_button.configure.assert_called_with(
        state="disabled"
    )

    state.export_checkbox.configure.assert_called_with(
        state="disabled"
    )

    thread.return_value.start.assert_called_once()

    run.assert_not_called()

    # Calling start again while already running must do nothing.
    ui.PlacesSearchPage.start(
        state
    )

    assert thread.call_count == 1

    # Simulate worker execution.
    # Widget methods must not be invoked directly from worker thread.
    state.progress.reset_mock()

    thread.call_args.kwargs[
        "target"
    ]()

    state.progress.configure.assert_not_called()

    assert (
        run.call_args.kwargs["provider"]
        is provider
    )

    assert (
        run.call_args.kwargs["limit"]
        == 5
    )

    assert (
        run.call_args.kwargs["city"]
        == "Taubaté"
    )

    assert (
        run.call_args.kwargs["segment"]
        == "dentista"
    )

    assert (
        run.call_args.kwargs["export_path"]
        == ui.Path(
            "output/google_places/"
            "taubate_dentista_test.xlsx"
        )
    )

    state.poll()

    assert not state.running

    state.start_button.configure.assert_called_with(
        state="normal"
    )

    state.export_checkbox.configure.assert_called_with(
        state="normal"
    )


def test_start_without_export_passes_none(
    monkeypatch,
):
    state = page()

    state.export_var.get.return_value = False

    provider = Mock()

    monkeypatch.setattr(
        ui,
        "create_provider",
        Mock(return_value=provider),
    )

    run = Mock(
        return_value=ProspectingSummary(
            requested=5
        )
    )

    monkeypatch.setattr(
        ui,
        "prospect",
        run,
    )

    thread = Mock()

    monkeypatch.setattr(
        ui.threading,
        "Thread",
        thread,
    )

    ui.PlacesSearchPage.start(
        state
    )

    thread.call_args.kwargs[
        "target"
    ]()

    assert (
        run.call_args.kwargs["export_path"]
        is None
    )


def test_missing_key_never_starts(
    monkeypatch,
):
    state = page()

    monkeypatch.setattr(
        ui,
        "create_provider",
        Mock(
            side_effect=(
                GooglePlacesConfigurationError(
                    "private"
                )
            )
        ),
    )

    thread = Mock()

    monkeypatch.setattr(
        ui.threading,
        "Thread",
        thread,
    )

    message = Mock()

    monkeypatch.setattr(
        ui.messagebox,
        "showerror",
        message,
    )

    ui.PlacesSearchPage.start(
        state
    )

    assert not state.running

    thread.assert_not_called()

    assert (
        "GOOGLE_PLACES_API_KEY"
        in message.call_args.args[1]
    )

    assert (
        "private"
        not in message.call_args.args[1]
    )


@pytest.mark.parametrize(
    "event",
    [
        (
            "done",
            ProspectingSummary(
                requested=5,
                inserted=1,
            ),
        ),
        (
            "error",
            "Falha segura",
        ),
    ],
)
def test_completion_restores_controls(
    event,
):
    state = page()

    state.set_running(
        True
    )

    state.pending.put(
        (
            "progress",
            0.5,
        )
    )

    state.pending.put(
        event
    )

    state.poll()

    assert not state.running

    for entry in state.entries.values():
        entry.configure.assert_called_with(
            state="normal"
        )

    state.cancel_button.configure.assert_called_with(
        state="disabled"
    )

    state.export_checkbox.configure.assert_called_with(
        state="normal"
    )


def test_done_with_export_enables_buttons():
    state = page()

    result = ProspectingSummary(
        requested=5,
        inserted=3,
        exported_rows=5,
        exported_file=(
            "output/google_places/"
            "teste.xlsx"
        ),
    )

    state.set_running(
        True
    )

    state.pending.put(
        (
            "done",
            result,
        )
    )

    state.poll()

    assert (
        state.last_exported_file
        == ui.Path(
            "output/google_places/"
            "teste.xlsx"
        )
    )

    state.open_excel_button.configure.assert_called_with(
        state="normal"
    )

    state.open_folder_button.configure.assert_called_with(
        state="normal"
    )

    assert any(
        "Excel: 5 leads"
        in call.args[0]
        for call in state.append.call_args_list
        if call.args
    )


def test_cancel_is_cooperative():
    state = page()

    ui.PlacesSearchPage.cancel(
        state
    )

    assert (
        state.cancel_event.is_set()
    )

    state.cancel_button.configure.assert_called_with(
        state="disabled"
    )


def test_environment_loader_is_shared_and_does_not_override(
    tmp_path,
    monkeypatch,
):
    import sys

    from core.providers import environment
    from scripts import test_google_places_real

    (
        tmp_path / ".env"
    ).write_text(
        "GOOGLE_PLACES_API_KEY=",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        environment,
        "ROOT",
        tmp_path,
    )

    loader = Mock()

    monkeypatch.setitem(
        sys.modules,
        "dotenv",
        SimpleNamespace(
            load_dotenv=loader
        ),
    )

    environment.load_environment()

    loader.assert_called_once_with(
        tmp_path / ".env",
        override=False,
        interpolate=False,
    )

    assert (
        test_google_places_real.load_environment
        is environment.load_environment
    )