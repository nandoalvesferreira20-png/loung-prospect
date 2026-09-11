from unittest.mock import Mock
from types import SimpleNamespace

import pytest

from ui import prototype_logic as logic
from ui import prototype_studio as studio
from core.prototype.models import PrototypeResult
from core.prototype.registry import TemplateRegistry, TemplateNotFoundError


@pytest.fixture
def fields():
    return dict(company_name="Clínica", segment="dentista", output_directory="prototypes",
                whatsapp="(11) 99999-8888", qualification_score="70")


def test_build_request_and_templates(fields):
    session = logic.PrototypeSession()
    assert session.last_result is None and not session.can_open
    templates = session.templates(" DENTISTA ")
    assert templates[0].template_id == "dentist-modern-v1"
    request = logic.build_request(fields, templates[0].template_id, session.registry)
    assert request.lead.company_name == "Clínica"
    assert request.lead.whatsapp == fields["whatsapp"]
    assert request.lead.qualification_score == 70


@pytest.mark.parametrize("value,expected", [("", None), ("  ", None), ("0", 0), ("100", 100)])
def test_score(value, expected):
    assert logic.parse_score(value) == expected


@pytest.mark.parametrize("value", ["-1", "101", "1.2", "abc"])
def test_invalid_score(value):
    with pytest.raises(ValueError):
        logic.parse_score(value)


@pytest.mark.parametrize("field", ["company_name", "segment", "output_directory"])
def test_required_fields(fields, field):
    fields[field] = ""
    with pytest.raises(ValueError):
        logic.build_request(fields, "dentist-modern-v1", TemplateRegistry())


def test_missing_and_incompatible_template(fields):
    with pytest.raises(ValueError):
        logic.build_request(fields, None, TemplateRegistry())
    with pytest.raises(TemplateNotFoundError):
        logic.build_request(fields, "missing", TemplateRegistry())
    fields["segment"] = "barbearia"
    assert logic.PrototypeSession().templates("barbearia") == []
    with pytest.raises(ValueError, match="incompatível"):
        logic.build_request(fields, "dentist-modern-v1", TemplateRegistry())


def test_explicit_generation_and_last_result(fields, monkeypatch):
    created = Mock(status="created")
    generator = Mock(return_value=created)
    monkeypatch.setattr(logic, "generate_prototype", generator)
    session = logic.PrototypeSession()
    session.templates("dentista")
    generator.assert_not_called()
    assert session.generate(fields, "dentist-modern-v1") is created
    assert session.last_result is created and session.can_open
    generator.return_value = PrototypeResult("failed", errors=["Test"])
    session.generate(fields, "dentist-modern-v1")
    assert not session.can_open


def test_preview_guard(monkeypatch):
    open_preview = Mock()
    monkeypatch.setattr(studio, "open_preview", open_preview)
    page = SimpleNamespace(session=SimpleNamespace(can_open=False, last_result=PrototypeResult("failed")))
    studio.PrototypeStudioPage.preview(page)
    open_preview.assert_not_called()
    page.session.can_open = True
    page.session.last_result = Mock(status="created")
    studio.PrototypeStudioPage.preview(page)
    open_preview.assert_called_once_with(page.session.last_result)


def test_failed_disables_buttons():
    page = SimpleNamespace(session=SimpleNamespace(can_open=False, last_result=PrototypeResult("failed", errors=["Test"])),
                           preview_button=Mock(), folder_button=Mock(), result_label=Mock())
    studio.PrototypeStudioPage.refresh_result(page)
    page.preview_button.configure.assert_called_with(state="disabled")
    page.folder_button.configure.assert_called_with(state="disabled")
