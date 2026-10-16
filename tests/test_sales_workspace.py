from types import SimpleNamespace
from unittest.mock import Mock

from ui import sales_panel, sales_workspace


def test_unsaved_edit_requires_confirmation(monkeypatch):
    ask = Mock(return_value=False)
    monkeypatch.setattr(sales_panel, "resolve_pending", ask)
    page = SimpleNamespace(loaded_text="Original", message=Mock(get=Mock(return_value="Edição humana")))
    assert not sales_panel.SalesPanel.confirm_discard(page)
    ask.assert_called_once()
    page.message.get.return_value = "Original"
    assert sales_panel.SalesPanel.confirm_discard(page)
    assert ask.call_count == 1


def test_cancel_discard_does_not_call_provider(monkeypatch):
    factory = Mock()
    monkeypatch.setattr(sales_panel, "create_sales_provider", factory)
    page = SimpleNamespace(busy=False, loaded_text="Original", confirm_discard=Mock(return_value=False))
    sales_panel.SalesPanel.generate(page, True)
    factory.assert_not_called()


def test_saved_message_loaded_without_provider(monkeypatch):
    factory = Mock()
    monkeypatch.setattr(sales_panel, "create_sales_provider", factory)
    page = SimpleNamespace(busy=False, loaded_text="Salva", confirm_discard=Mock(return_value=True),
        rows={"#1": {"id": 1, "status": "EDITADA"}}, message=Mock(get=Mock(return_value="Salva")),
        refresh=Mock(), feedback=Mock())
    sales_panel.SalesPanel.generate(page)
    page.refresh.assert_called_once_with(1)
    factory.assert_not_called()


def test_whatsapp_rechecks_contact_restrictions_at_click_and_never_marks_sent(monkeypatch):
    browser = Mock(return_value=True)
    service = Mock(preview_url=Mock(side_effect=ValueError("Contato bloqueado")))
    page = SimpleNamespace(service=service, lead_id=7, notice=Mock(), browser_action=Mock(open=browser),
        fields={key: Mock(get=Mock(return_value="")) for key in ("consent", "source", "authorized_at", "status")},
        saved_values=dict(consent="", source="", authorized_at="", status=""), update_availability=Mock(),
        sales=SimpleNamespace(busy=False, current_id=1, rows={}, message=Mock(get=Mock(return_value="Texto editado & revisado"))))
    page.current_url = lambda: sales_workspace.ContactPanel.current_url(page)
    sales_workspace.ContactPanel.open_whatsapp(page)
    browser.assert_not_called()
    page.notice.configure.assert_called_with(text="Contato bloqueado")
    service.preview_url.side_effect = None
    service.preview_url.return_value = "https://wa.me/5511999991234?text=teste"
    sales_workspace.ContactPanel.open_whatsapp(page)
    browser.assert_called_once_with(service.preview_url.return_value)
    service.save.assert_not_called()
    service.preview_url.assert_called_with(7, "Texto editado & revisado")


def test_button_disabled_without_valid_phone():
    page = SimpleNamespace(current_url=Mock(side_effect=ValueError("Telefone não informado")),
        lead_id=7, notice=Mock(), open_button=Mock(), copy_button=Mock())
    sales_workspace.ContactPanel.update_availability(page)
    page.open_button.configure.assert_called_once_with(state="disabled")
