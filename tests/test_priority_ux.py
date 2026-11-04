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
