from tkinter import TclError
from unittest.mock import Mock, call

import pytest

from ui import copy_field


@pytest.mark.parametrize("value,expected", [(None, None), ("", None), ("  ", None),
    ("+55 (12) 1234-5678", "+55 (12) 1234-5678"), (" Rua São José, 1 ", " Rua São José, 1 ")])
def test_available_text(value, expected):
    assert copy_field.available_text(value) == expected


def test_clipboard_clears_then_appends_complete_value():
    widget = Mock()
    assert copy_field.copy_to_clipboard(widget, "São José, 1") == "Copiado!"
    assert widget.mock_calls == [call.clipboard_clear(), call.clipboard_append("São José, 1")]


@pytest.mark.parametrize("value", [None, "", "  "])
def test_empty_does_not_clear_clipboard(value):
    widget = Mock()
    assert copy_field.copy_to_clipboard(widget, value) == "Não disponível"
    assert widget.mock_calls == []


def test_clipboard_failure_inline():
    widget = Mock()
    widget.clipboard_clear.side_effect = TclError("busy")
    assert copy_field.copy_to_clipboard(widget, "123") == "Não foi possível copiar"
    widget.clipboard_append.assert_not_called()


def test_ctrl_c_copies_selection():
    entry = Mock()
    entry.get.return_value = "Telefone: 123"
    entry.index.side_effect = [10, 13]
    assert copy_field.copy_selection(entry) == "break"
    entry.clipboard_append.assert_called_once_with("123")


def test_ctrl_c_without_selection_preserves_clipboard():
    entry = Mock()
    entry.select_present.return_value = False
    assert copy_field.copy_selection(entry) == "break"
    entry.clipboard_clear.assert_not_called()


@pytest.mark.parametrize("value,state,display", [(None, "disabled", "Não disponível"),
    ("", "disabled", "Não disponível"), ("123", "normal", "123")])
def test_field_readonly_and_copy_button(monkeypatch, value, state, display):
    for name in ("CTkFrame", "CTkLabel", "CTkEntry", "CTkButton"):
        monkeypatch.setattr(copy_field.ctk, name, Mock())
    entry, button = copy_field.add_copy_field(Mock(), "Telefone", value)
    entry.insert.assert_called_once_with(0, display)
    entry.configure.assert_called_once_with(state="readonly")
    assert copy_field.ctk.CTkButton.call_args.kwargs["state"] == state
    assert "<Control-c>" in [c.args[0] for c in entry.bind.call_args_list]
    if value:
        command = button.configure.call_args.kwargs["command"]
        command()
        button.configure.assert_called_with(text="Copiado!")
