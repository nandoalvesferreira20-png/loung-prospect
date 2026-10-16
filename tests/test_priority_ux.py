"""Compatibility and loss-prevention regressions, using disposable SQLite only."""
from datetime import date, timezone
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from core.commercial.day import build_day
from core.commercial.values import STATUSES, commercial_status
from core.database import LeadRepository
from core.database.template_draft_repository import TemplateDraftRepository
from core.database.outreach_repository import OutreachRepository
from core.sales.contact import ContactService, SDR_STATUSES
from core.sales.models import SalesGeneration
from ui import pending_edits
from ui.commercial_panel import CommercialPanel
from ui.lead_workspace_logic import LeadWorkspace, counts
from ui.outreach_panel import OutreachPanel
from ui.sales_panel import SalesPanel
from ui.sales_workspace_logic import list_sales_leads, sales_counts


@pytest.mark.parametrize("legacy,canonical", [
    ("Reunião marcada", "Reunião agendada"), ("Reunião", "Reunião agendada"),
    ("Contatado", "Contato realizado"), ("Respondeu", "Em conversa"),
    ("Não interessado", "Sem interesse"), ("Novo Lead", "Novo"),
    ("Mensagem gerada", "Novo"), ("Revisado", "Novo"), ("Personalizado", "Personalizado")])
def test_legacy_stage_read_filters_and_no_rewrite(tmp_path, legacy, canonical):
    repo = LeadRepository(tmp_path / "legacy.db")
    identity = repo.create_lead(dict(empresa="Teste", status=legacy))
    before = dict(repo.get_lead(identity))
    assert SDR_STATUSES == STATUSES
    assert commercial_status(legacy) == canonical
    assert [r["id"] for r in LeadWorkspace(repo).list(status=canonical)] == [identity]
    rows = list_sales_leads(repo, status=canonical)
    assert len(rows) == 1 and rows[0]["display_status"] == canonical
    day = build_day(repo.list_leads(), date(2026, 10, 15), tz=timezone.utc)
    assert day.counts["reunioes"] == (canonical == "Reunião agendada")
    assert sales_counts(rows)["meetings"] == day.counts["reunioes"]
    assert sales_counts(rows)["contacted"] == (canonical == "Contato realizado")
    assert counts(repo.list_leads())["reuniao"] == day.counts["reunioes"]
    assert dict(repo.get_lead(identity)) == before


def test_alias_write_and_terminal_indicator(tmp_path):
    repo = LeadRepository(tmp_path / "stages.db")
    identity = repo.create_lead(dict(empresa="Teste"))
    service = ContactService(repo)
    service.save(identity, status="Reunião marcada", consent="Desconhecido", source="",
                 authorized_at="", responsible="Ana", notes="")
    assert repo.get_lead(identity)["status"] == "Reunião agendada"
    for status in ("Não interessado", "Não contatar"):
        row = dict(repo.get_lead(identity), status=status, proximo_contato="2026-01-01T12:00:00Z")
        assert build_day([row], date(2026, 10, 15), tz=timezone.utc).counts["atrasados"] == 0


def test_template_draft_survives_restart_without_altering_lead_or_ai(tmp_path):
    repo = LeadRepository(tmp_path / "draft.db")
    identity = repo.create_lead(dict(empresa="Teste"))
    before = dict(repo.get_lead(identity))
    drafts = TemplateDraftRepository(repo.path)
    assert drafts.load(identity) is None
    drafts.save(identity, "Texto humano\ncom edição", "phone", "follow_up", "direct")
    reopened = TemplateDraftRepository(LeadRepository(repo.path).path)
    assert reopened.load(identity)["message"] == "Texto humano\ncom edição"
    assert reopened.load(identity)["channel"] == "phone"
    assert OutreachRepository(repo.path).history(identity) == []
    assert dict(repo.get_lead(identity)) == before
    with pytest.raises(ValueError):
        drafts.save(identity, " ", "phone", "follow_up", "direct")
    assert reopened.load(identity)["message"] == "Texto humano\ncom edição"


@pytest.mark.parametrize("action,success,allowed", [
    ("continue", True, False), ("discard", True, True),
    ("save", True, True), ("save", False, False)])
def test_three_way_decision_never_continues_after_failed_save(monkeypatch, action, success, allowed):
    monkeypatch.setattr(pending_edits, "ask_pending_action", lambda *args: action)
    save = Mock(return_value=success)
    assert pending_edits.resolve_pending(Mock(), "Mensagem", save) is allowed
    assert save.call_count == (action == "save")


@pytest.mark.parametrize("field", ["status", "responsavel", "proximo_contato", "proxima_acao", "canal_preferencial", "observacoes"])
def test_commercial_dirty_detection_covers_entire_form(field):
    saved = dict(status="Novo", responsavel="Ana", proximo_contato="", proxima_acao="", canal_preferencial="", observacoes="")
    current = saved | {field: "Editado"}
    panel = SimpleNamespace(saved_values=saved, entries={key: Mock(get=Mock(return_value=value))
        for key, value in current.items() if key != "observacoes"},
        notes=Mock(get=Mock(return_value=current["observacoes"])))
    panel.values = lambda: CommercialPanel.values(panel)
    assert CommercialPanel.has_pending_edits(panel)


def test_ai_save_before_replacement_persists_and_refreshes_cached_text(tmp_path, monkeypatch):
    repo = LeadRepository(tmp_path / "ai.db")
    identity = repo.create_lead(dict(empresa="Teste"))
    outreach = OutreachRepository(repo.path)
    draft = outreach.create(identity, SalesGeneration("Original", "Teste", .8))
    panel = SimpleNamespace(loaded_text="Original", current_id=draft, busy=False,
        lead_id=identity, outreach=outreach, message=Mock(get=Mock(return_value="Edição humana")),
        rows={"Original": dict(outreach.history(identity)[0])}, feedback=Mock())
    monkeypatch.setattr(pending_edits, "ask_pending_action", lambda *args: "save")
    assert SalesPanel.confirm_discard(panel)
    assert outreach.history(identity)[0]["mensagem"] == "Edição humana"
    assert panel.rows["Original"]["mensagem"] == panel.loaded_text == "Edição humana"
    assert repo.get_lead(identity)["status"] == "Novo"


def test_continue_editing_blocks_template_replacement():
    panel = SimpleNamespace(has_pending_edits=Mock(return_value=True),
        confirm_pending=Mock(return_value=False), load_lead=Mock(), message=Mock())
    OutreachPanel.generate(panel, another=True)
    panel.load_lead.assert_not_called()
    panel.message.delete.assert_not_called()


def test_template_failed_save_keeps_message_and_dirty_snapshot():
    panel = SimpleNamespace(drafts=Mock(save=Mock(side_effect=OSError("Disco indisponível"))),
        lead_id=1, loaded_text="Anterior", message=Mock(get=Mock(return_value="Edição pendente")),
        selectors=[(Mock(get=Mock(return_value=value)), {value: value})
                   for value in ("whatsapp", "first_contact", "direct")], feedback=Mock())
    assert not OutreachPanel.save(panel)
    assert panel.loaded_text == "Anterior"
    panel.message.delete.assert_not_called()
