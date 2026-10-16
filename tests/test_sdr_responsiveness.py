import queue
from types import SimpleNamespace
from unittest.mock import Mock
import pytest

from ui.responsive_text import WrappedLabels
from ui.sales_workspace import SalesWorkspacePage
from ui.sales_workspace_logic import filter_sales_leads
from ui.sdr_diagnostics import callback_error


def test_resize_ignores_height_changes_and_coalesces_width():
    container = Mock()
    container._reverse_widget_scaling.side_effect = lambda width: width / 1.5
    label = Mock(cget=Mock(return_value=230))
    wrapper = WrappedLabels(container, [label])
    event = SimpleNamespace(widget=container._canvas, width=600)
    wrapper.resize(event)
    assert wrapper.width == 372
    for _ in range(200):
        wrapper.resize(event)
    container.after.assert_called_once()
    wrapper.apply()
    label.configure.assert_called_once_with(wraplength=372)
    wrapper.resize(SimpleNamespace(widget=container._canvas, width=750))
    wrapper.resize(SimpleNamespace(widget=container._canvas, width=900))
    container.after_cancel.assert_called_once()
    wrapper.destroy(SimpleNamespace(widget=container._canvas))
    assert wrapper.closed and wrapper.job is None
    count = label.configure.call_count
    wrapper.apply()
    assert label.configure.call_count == count


def test_filters_reuse_loaded_rows():
    rows = [dict(id=1, empresa="Clínica São José", segmento="dentista", display_status="Novo"),
            dict(id=2, empresa="Outra", segmento="advogado", display_status="Contatado")]
    assert filter_sales_leads(rows, search="SÃO", segment="DENTISTA", status="Novo") == rows[:1]
    assert filter_sales_leads(rows, status="Contatado") == rows[1:]


def test_load_worker_never_calls_widgets(monkeypatch):
    from ui import sales_workspace as module
    thread = Mock()
    monkeypatch.setattr(module.threading, "Thread", thread)
    query = Mock(return_value=[])
    monkeypatch.setattr(module, "list_sales_leads", query)
    page = SimpleNamespace(_closed=False, _load_busy=False, repository=object(), _load_queue=queue.Queue(),
        page_notice=Mock(), after=Mock(), poll_load=Mock())
    SalesWorkspacePage.refresh(page)
    query.assert_not_called()
    count = len(page.page_notice.mock_calls)
    thread.call_args.kwargs["target"]()
    assert len(page.page_notice.mock_calls) == count
    assert page._load_queue.get_nowait()[1] == []
    SalesWorkspacePage.refresh(page)
    assert page._reload_requested and thread.call_count == 1


def test_closed_page_drops_late_load():
    page = SimpleNamespace(_closed=True, _load_queue=queue.Queue(), page_notice=Mock())
    page._load_queue.put((None, [], {}, False))
    SalesWorkspacePage.poll_load(page)
    assert not page._load_queue.empty()
    page.page_notice.configure.assert_not_called()


def test_filter_debounce():
    page = SimpleNamespace(_filter_job="old", after_cancel=Mock(), after=Mock(return_value="new"), apply_filters=Mock())
    SalesWorkspacePage.schedule_filter(page)
    page.after_cancel.assert_called_once_with("old")
    page.after.assert_called_once_with(180, page.apply_filters)


def test_clean_hidden_editors_are_released_only():
    clean = Mock(can_release=Mock(return_value=True))
    pending = Mock(can_release=Mock(return_value=False))
    selected = Mock()
    dirty = Mock(can_release=Mock(return_value=False))
    page = SimpleNamespace(selected_id=3, editors={1: clean, 2: pending, 3: selected, 4: dirty})
    SalesWorkspacePage.prune_editors(page)
    clean.destroy.assert_called_once()
    assert set(page.editors) == {2, 3, 4}
    pending.destroy.assert_not_called()
    selected.destroy.assert_not_called()
    dirty.destroy.assert_not_called()


def test_callback_log_does_not_expose_exception_payload(caplog):
    try:
        raise ValueError("synthetic-secret and personal lead name")
    except ValueError as error:
        callback_error(type(error), error, error.__traceback__)
    assert "ValueError" in caplog.text
    assert "synthetic-secret" not in caplog.text and "personal lead" not in caplog.text


def test_duplicate_sidebar_navigation_does_not_destroy_page():
    from app import LoungLeadsApp
    current = Mock(spec=SalesWorkspacePage)
    app = SimpleNamespace(content=Mock(winfo_children=Mock(return_value=[current])), clear_content=Mock())
    LoungLeadsApp.show_sales(app)
    app.clear_content.assert_not_called()
