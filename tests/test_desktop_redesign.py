from types import SimpleNamespace
from unittest.mock import Mock
from urllib.parse import parse_qs, urlsplit

import pytest

from core.sales.contact import normalize_phone, whatsapp_url
from ui.browser_action import BrowserAction
from ui.sales_workspace import ContactPanel
from ui.presentation import overview_details
from ui.theme import COLORS


@pytest.mark.parametrize("value,expected", [
    ("(11) 99999-9999", "5511999999999"),
    ("(12) 99184-4481", "5512991844481"),
    ("+55 (11) 99999-9999", "5511999999999"),
    ("55 11 99999-9999", "5511999999999"),
    ("(11)\u00a099999-9999", "5511999999999"),
    ("+351 912 345 678", "351912345678"),
])
def test_phone_formatting(value, expected):
    assert normalize_phone(value) == expected


def authorized():
    return dict(telefone="(11) 99999-9999", whatsapp=" ", whatsapp_consent="Autorizado",
                consent_source="Formulário", consent_at="2026-01-01T00:00:00Z",
                consent_number="5511999999999", status="Novo", do_not_contact=0)


def test_url_preserves_current_text_and_never_mutates_lead():
    lead = authorized()
    before = lead.copy()
    text = "Olá! Edição humana & revisão?\nSão Paulo + 10% #ideia"
    url = whatsapp_url(lead, text)
    assert urlsplit(url).netloc == "wa.me"
    assert urlsplit(url).path == "/5511999999999"
    assert parse_qs(urlsplit(url).query)["text"] == [text]
    assert lead == before


@pytest.mark.parametrize("change", [dict(do_not_contact=1),
                                   dict(status="Não contatar"), dict(whatsapp_consent="Revogado")])
def test_no_link_for_explicit_contact_restrictions(change):
    with pytest.raises(ValueError):
        whatsapp_url(authorized() | change, "Mensagem")


@pytest.mark.parametrize("text", ["", " \n "])
def test_no_empty_message(text):
    with pytest.raises(ValueError, match="vazia"):
        whatsapp_url(authorized(), text)


def test_current_editor_and_selected_identity_used_each_time():
    page = SimpleNamespace(lead_id=7, service=Mock(),
                           fields={key: Mock(get=Mock(return_value="")) for key in ("consent", "source", "authorized_at", "status")},
                           saved_values=dict(consent="", source="", authorized_at="", status=""), sales=SimpleNamespace(busy=False, current_id=1, rows={},
                           message=Mock(get=Mock(return_value="Editada, não salva"))))
    ContactPanel.current_url(page)
    page.service.preview_url.assert_called_with(7, "Editada, não salva")
    page.lead_id = 8
    page.sales.message.get.return_value = "Outro editor"
    ContactPanel.current_url(page)
    page.service.preview_url.assert_called_with(8, "Outro editor")
    page.service.save.assert_not_called()


def test_browser_worker_uses_new_tab_and_no_widgets(monkeypatch):
    launch = Mock(return_value=True)
    monkeypatch.setattr("core.browser_launcher.webbrowser.open", launch)
    threads = []
    monkeypatch.setattr("ui.browser_action.threading.Thread", lambda **kw: threads.append(kw) or Mock())
    owner, completed = Mock(), Mock()
    action = BrowserAction(owner, completed)
    assert action.open("https://wa.me/5511999999999?text=Oi")
    assert not action.open("https://wa.me/other")
    owner.reset_mock()
    threads[0]["target"]()
    assert not owner.mock_calls
    completed.assert_not_called()
    launch.assert_called_once_with("https://wa.me/5511999999999?text=Oi", new=2)
    action.poll()
    completed.assert_called_once_with(True)


@pytest.mark.parametrize("failure", [False, OSError("private-url-must-not-be-shown")])
def test_browser_failure_is_reported_safely(monkeypatch, failure):
    browser = Mock(side_effect=failure) if isinstance(failure, Exception) else Mock(return_value=False)
    monkeypatch.setattr("core.browser_launcher.webbrowser.open", browser)
    threads = []
    monkeypatch.setattr("ui.browser_action.threading.Thread", lambda **kw: threads.append(kw) or Mock())
    done = Mock()
    action = BrowserAction(Mock(), done)
    action.open("https://wa.me/5511999999999")
    threads[0]["target"]()
    action.poll()
    done.assert_called_once_with(False)
    notice = Mock()
    ContactPanel.browser_completed(SimpleNamespace(notice=notice, update_availability=Mock()), False)
    assert "Copiar link" in notice.configure.call_args.kwargs["text"]


def test_browser_timeout_and_destroy_ignore_late_result(monkeypatch):
    monkeypatch.setattr("ui.browser_action.threading.Thread", Mock())
    done, owner = Mock(), Mock()
    action = BrowserAction(owner, done)
    action.open("https://wa.me/5511999999999")
    action.started -= 11
    action.poll()
    done.assert_called_once_with(False)
    action.close()
    action.pending.put(True)
    action.poll()
    assert done.call_count == 1


def test_copy_link_revalidates_and_uses_clipboard(monkeypatch):
    clipboard = Mock(return_value="Copiado!")
    monkeypatch.setattr("ui.sales_workspace.copy_to_clipboard", clipboard)
    page = SimpleNamespace(current_url=Mock(return_value="https://wa.me/5511999999999?text=Editada"), notice=Mock())
    ContactPanel.copy_link(page)
    clipboard.assert_called_once_with(page, page.current_url.return_value)
    page.current_url.side_effect = ValueError("Contato bloqueado")
    ContactPanel.copy_link(page)
    assert clipboard.call_count == 1
    page.notice.configure.assert_called_with(text="Contato bloqueado")


def test_dashboard_aggregates_only_real_data():
    rows = [dict(id=1, empresa="A", segmento="dentista", opportunity="website"),
            dict(id=2, empresa="B", segmento="dentista", opportunity=None)]
    result = overview_details(rows)
    assert result["segments"] == [("dentista", 2)]
    assert result["opportunities"] == [("Não informada", 1), ("website", 1)]
    assert [row["id"] for row in result["recent"]] == [2, 1]
    assert rows[0]["id"] == 1
    assert overview_details([]) == dict(segments=[], opportunities=[], recent=[])


def test_shared_palette():
    assert COLORS["bg"] == "#090E18"
    assert COLORS["surface"] == "#151F30"
    assert COLORS["primary"] == "#2563EB"
    assert COLORS["primary_hover"] == "#1D4ED8"


def test_legacy_worker_callbacks_only_enqueue():
    import queue
    from ui.home import HomePage
    page = SimpleNamespace(pending=queue.Queue(), after=Mock())
    HomePage.log(page, "Atividade")
    HomePage.update_progress(page, 1, 5, "Processando")
    assert page.pending.get_nowait() == ("log", ("Atividade",))
    assert page.pending.get_nowait() == ("progress", (1, 5, "Processando"))
    page.after.assert_not_called()


def test_unsaved_contact_can_block_navigation(monkeypatch):
    from ui.sales_workspace import SalesWorkspacePage
    confirm = Mock(return_value=False)
    monkeypatch.setattr("ui.sales_workspace.messagebox.askyesno", confirm)
    frame = SimpleNamespace(sales=Mock(confirm_discard=Mock(return_value=True)),
                            contact_is_saved=Mock(return_value=False))
    page = SimpleNamespace(editors={1: frame})
    assert not SalesWorkspacePage.can_leave(page)
    confirm.assert_called_once()


def test_same_page_navigation_preserves_form():
    from app import LoungLeadsApp
    from ui.places_search import PlacesSearchPage
    page = Mock(spec=PlacesSearchPage)
    app = SimpleNamespace(current_page=page, clear_content=Mock())
    LoungLeadsApp.show_places(app)
    app.clear_content.assert_not_called()
