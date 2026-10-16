"""Real persisted requirements with lightweight UI state; no browser or network."""
from contextlib import closing
from types import SimpleNamespace
from unittest.mock import Mock
from urllib.parse import parse_qs, urlsplit

import pytest

from core.database import LeadRepository
from core.database.connection import connect_database
from core.sales.contact import ContactService
from ui.sales_workspace import ContactPanel
from ui.sales_workspace import SalesWorkspacePage
from ui.sales_workspace_logic import filter_sales_leads


@pytest.fixture
def contact(tmp_path):
    repo = LeadRepository(tmp_path / "sdr.db")
    identity = repo.create_lead(dict(empresa="São José", telefone="(11) 99999-1234"))
    values = dict(status="Novo", consent="Autorizado", source="Formulário sintético",
                  authorized_at="2026-01-01T12:00:00Z", responsible="Ana", notes="")
    service = ContactService(repo)
    saved = dict(status="Novo", responsible="Ana", notes="", contact_at="")
    page = SimpleNamespace(service=service, lead_id=identity,
        fields={key: Mock(get=Mock(return_value=value)) for key, value in saved.items()}, saved_values=saved,
        sales=SimpleNamespace(busy=False, current_id=1, rows={"#1": dict(id=1, status="GERADA")},
            message=Mock(get=Mock(return_value="Olá, São José!\nCafé & ideias + crescimento?"))),
        browser_action=Mock(busy=False, open=Mock(return_value=True)), open_button=Mock(),
        copy_button=Mock(), notice=Mock())
    page.current_url = lambda: ContactPanel.current_url(page)
    page.update_availability = lambda: ContactPanel.update_availability(page)
    return repo, identity, values, page


def test_open_uses_current_message_and_never_marks_contact(contact):
    repo, identity, _, page = contact
    before = dict(repo.get_lead(identity))
    ContactPanel.open_whatsapp(page)
    url = page.browser_action.open.call_args.args[0]
    assert urlsplit(url).netloc == "wa.me" and urlsplit(url).path == "/5511999991234"
    assert parse_qs(urlsplit(url).query)["text"] == [page.sales.message.get.return_value]
    assert dict(repo.get_lead(identity)) == before


@pytest.mark.parametrize("change,hint", [
    ({"telefone": None}, "Telefone não informado"),
    ({"telefone": "abc"}, "inválido"),
    ({"whatsapp_consent": "Revogado"}, "bloqueado")])
def test_invalid_requirements_disable_and_block_even_if_clicked(contact, change, hint):
    repo, identity, _, page = contact
    with closing(connect_database(repo.path)) as connection, connection:
        assignments = ", ".join(f"{key}=?" for key in change)
        connection.execute(f"UPDATE leads SET {assignments} WHERE id=?", [*change.values(), identity])
    page.update_availability()
    page.open_button.configure.assert_called_with(state="disabled")
    page.copy_button.configure.assert_called_with(state="disabled")
    assert hint.casefold() in page.notice.configure.call_args.kwargs["text"].casefold()
    ContactPanel.open_whatsapp(page)
    page.browser_action.open.assert_not_called()


def test_pending_do_not_contact_blocks_opening(contact):
    _, _, _, page = contact
    page.fields["status"].get.return_value = "Não contatar"
    page.update_availability()
    page.open_button.configure.assert_called_with(state="disabled")
    assert "Não contatar" in page.notice.configure.call_args.kwargs["text"]
    ContactPanel.open_whatsapp(page)
    page.browser_action.open.assert_not_called()


@pytest.mark.parametrize("change", [
    {"whatsapp_consent": "Desconhecido", "consent_source": None, "consent_at": None, "consent_number": None},
    {"whatsapp_consent": "Autorizado", "consent_source": "", "consent_at": "data legada inválida", "consent_number": "antigo"},
    {"telefone": "11988881234"}])
def test_missing_legacy_authorization_never_blocks_or_changes_data(contact, change):
    repo, identity, _, page = contact
    with closing(connect_database(repo.path)) as connection, connection:
        assignments = ", ".join(f"{key}=?" for key in change)
        connection.execute(f"UPDATE leads SET {assignments} WHERE id=?", [*change.values(), identity])
    before = dict(repo.get_lead(identity))
    page.update_availability()
    page.open_button.configure.assert_called_with(state="normal")
    ContactPanel.open_whatsapp(page)
    assert page.browser_action.open.call_count == 1
    assert dict(repo.get_lead(identity)) == before


def test_tracking_save_preserves_all_legacy_authorization_fields(contact):
    repo, identity, values, page = contact
    service = ContactService(repo)
    service.save(identity, **values)
    before = dict(repo.get_lead(identity))
    service.save_tracking(identity, status="Em conversa", responsible="Bia", notes="Nota humana")
    after = dict(repo.get_lead(identity))
    for key in ("whatsapp_consent", "consent_source", "consent_at", "consent_number", "do_not_contact"):
        assert after[key] == before[key]
    assert after["status"] == "Em conversa" and after["observacoes"] == "Nota humana"


def test_tracking_save_needs_no_authorization_and_can_record_restriction(contact):
    repo, identity, _, _ = contact
    service = ContactService(repo)
    service.save_tracking(identity, status="Não contatar", responsible="Ana", notes="Não abordar")
    row = repo.get_lead(identity)
    assert row["whatsapp_consent"] == "Desconhecido" and row["consent_source"] is None
    assert row["do_not_contact"] == 1
    repo.update_status(identity, "Novo")
    with pytest.raises(ValueError, match="bloqueado"):
        service.preview_url(identity, "Oi")


def test_actual_message_and_generation_control_availability(contact):
    _, _, _, page = contact
    page.sales.message.get.return_value = ""
    page.update_availability()
    assert "Sem rascunho" in page.notice.configure.call_args.kwargs["text"]
    page.open_button.configure.assert_called_with(state="disabled")
    page.sales.message.get.return_value = "Texto revisado"
    page.update_availability()
    page.open_button.configure.assert_called_with(state="normal")
    page.sales.busy = True
    page.update_availability()
    page.open_button.configure.assert_called_with(state="disabled")
    assert "geração" in page.notice.configure.call_args.kwargs["text"]


def test_discarded_draft_is_never_offered_as_contact_message(contact):
    _, _, _, page = contact
    page.sales.rows["#1"]["status"] = "CANCELADA"
    page.update_availability()
    page.open_button.configure.assert_called_with(state="disabled")
    assert "descartada" in page.notice.configure.call_args.kwargs["text"]


def test_browser_in_progress_disables_action(contact):
    _, _, _, page = contact
    page.browser_action.busy = True
    page.update_availability()
    page.open_button.configure.assert_called_with(state="disabled")
    assert "navegador" in page.notice.configure.call_args.kwargs["text"]


def test_explicit_all_filter_options_keep_every_lead():
    rows = [dict(empresa="A", segmento="dentista", display_status="Novo")]
    assert filter_sales_leads(rows, segment="Todos os segmentos", status="Todas as etapas") == rows


def test_database_loading_error_explains_retry():
    import queue
    pending = queue.Queue()
    pending.put((None, None, None, True))
    page = SimpleNamespace(_closed=False, _load_queue=pending, _reload_requested=False,
                           page_notice=Mock(), list_state=Mock())
    SalesWorkspacePage.poll_load(page)
    assert "Atualizar leads" in page.list_state.configure.call_args.kwargs["text"]
    assert not page._load_busy
