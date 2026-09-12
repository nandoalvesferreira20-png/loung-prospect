"""Headless callback tests; no layout/pixel assertions or real clipboard."""
from types import SimpleNamespace
from unittest.mock import Mock

from core.commercial.day import DaySummary
from ui import my_day
from ui.commercial_panel import CommercialPanel


def test_day_refresh_applies_filters_and_opens_lead(monkeypatch):
    page = SimpleNamespace(repository=Mock(), reference=Mock(get=Mock(return_value="11/09/2026")),
        responsible=Mock(get=Mock(return_value="Ana")), summary=Mock(), metrics=Mock(), table=Mock(), on_open=Mock())
    page.table.get_children.return_value = []
    row = dict(id=7, empresa="Clínica", responsavel="Ana", status="Novo", qualification_score=70,
               proxima_acao="Ligar", proximo_contato=None)
    get = Mock(return_value=DaySummary([row], dict(atrasados=0, hoje=0, novos=1, reunioes=0, propostas=0)))
    monkeypatch.setattr(my_day, "get_my_day", get)
    my_day.MyDayPage.refresh(page)
    assert get.call_args.kwargs["responsavel"] == "Ana"
    assert "Novos: 1" in page.summary.configure.call_args.kwargs["text"]
    assert page.table.insert.call_args.kwargs["iid"] == "7"
    page.table.selection.return_value = ["7"]
    my_day.MyDayPage.open_selected(page)
    page.on_open.assert_called_once_with(7)


def test_day_empty_selection_no_navigation():
    page = SimpleNamespace(table=Mock(selection=Mock(return_value=[])), on_open=Mock())
    my_day.MyDayPage.open_selected(page)
    page.on_open.assert_not_called()


def test_commercial_save_refreshes_without_closing(monkeypatch):
    fields = dict(status="Novo", responsavel="Ana", proxima_acao="Ligar", proximo_contato="", canal_preferencial="telefone")
    page = SimpleNamespace(entries={k: Mock(get=Mock(return_value=v)) for k, v in fields.items()},
        notes=Mock(get=Mock(return_value="Notas")), logic=Mock(), feedback=Mock(), on_change=Mock(), parent=Mock())
    CommercialPanel.save(page)
    page.logic.save.assert_called_once_with(**fields, observacoes="Notas")
    page.on_change.assert_called_once()
    page.parent.destroy.assert_not_called()


def test_history_refresh_preserves_unsaved_form():
    page = SimpleNamespace(logic=Mock(), last_contact=Mock(), history=Mock(), notes=Mock(), entries={"status": Mock()})
    page.logic.load.return_value = {"ultimo_contato": "2026-09-11T13:00:00+00:00"}
    page.logic.history.return_value = [dict(created_at="2026-09-11T13:00:00+00:00", canal="telefone", tipo="Ligação", descricao="Retornar")]
    CommercialPanel.refresh_history(page)
    assert "Retornar" in page.history.insert.call_args.args[1]
    page.history.configure.assert_called_with(state="disabled")
    page.notes.delete.assert_not_called()
    page.entries["status"].set.assert_not_called()
