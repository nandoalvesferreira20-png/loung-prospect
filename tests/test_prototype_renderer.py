import json
from pathlib import Path

import pytest

from core.prototype.generator import generate_prototype
from core.prototype.models import PrototypeLead, PrototypeRequest
from core.prototype.registry import get_template
from core.prototype.renderer import render_index


def test_fields_unicode_and_contact():
    lead = PrototypeLead("Clínica São José", "dentista", city="São Paulo", address="Rua A, 10",
                         phone="(11) 3333-4444", whatsapp="+55 (11) 99999-8888")
    text = render_index("{{ company_name }} {{ city }} {{ address }} {{ phone }} {{ whatsapp }} {{ contact_url }}", lead)
    assert text == "Clínica São José São Paulo Rua A, 10 (11) 3333-4444 +55 (11) 99999-8888 https://wa.me/5511999998888"


def test_phone_fallback():
    lead = PrototypeLead("E", "S", phone="+55 (11) 3333-4444")
    assert render_index("{{ contact_url }}", lead) == "tel:+551133334444"


def test_missing_optionals_hide_blocks():
    text = render_index('{{#if city}}Cidade {{ city }}{{/if}}{{#if contact_url}}<a href="{{ contact_url }}">Contato</a>{{/if}}', PrototypeLead("E", "S"))
    assert text == ""


def test_html_escape_and_no_recursive_template_evaluation():
    lead = PrototypeLead('<script>alert("x")</script>{{ city }}', "S", address='" onmouseover="x')
    text = render_index('{{ company_name }} <p title="{{ address }}">x</p>', lead)
    assert "<script>" not in text
    assert "&lt;script&gt;" in text
    assert "&quot; onmouseover=&quot;x" in text
    assert "{{ city }}" in text  # Literal lead content, not evaluated as syntax.


@pytest.mark.parametrize("template", ["{{ unknown }}", "{{ company_name", "{{/if}}", "{{#if city}}", "{{#if city}}{{#if phone}}{{/if}}{{/if}}"])
def test_bad_placeholders_fail(template):
    with pytest.raises(ValueError):
        render_index(template, PrototypeLead("E", "S"))


def test_invalid_contact_has_no_clickable_cta():
    lead = PrototypeLead("E", "S", whatsapp='javascript:alert(123456789)', phone="abc")
    assert render_index("{{ contact_url }}", lead) == ""


def test_template_generation_isolated_and_unchanged(tmp_path):
    template = get_template("dentist-modern-v1")
    source = Path(template.template_path)
    before = {p.relative_to(source): p.read_bytes() for p in source.rglob("*") if p.is_file()}
    results = [generate_prototype(PrototypeRequest(PrototypeLead(name, "dentista", city="São Paulo"), template, str(tmp_path / "output"))) for name in ("Clínica Árvore", "Clínica Segunda")]
    for result, name in zip(results, ("Clínica Árvore", "Clínica Segunda")):
        assert result.status == "created"
        output = Path(result.output_path)
        html = (output / "index.html").read_text(encoding="utf-8")
        assert name in html and "São Paulo" in html
        assert "{{" not in html
        assert "https://wa.me/" not in html and "tel:" not in html
        assert (output / "css/style.css").read_bytes() == before[Path("css/style.css")]
        assert (output / "js/script.js").read_bytes() == before[Path("js/script.js")]
        assert json.loads((output / "prototype.json").read_text(encoding="utf-8"))["company_name"] == name
    assert "Clínica Segunda" not in (Path(results[0].output_path) / "index.html").read_text(encoding="utf-8")
    assert before == {p.relative_to(source): p.read_bytes() for p in source.rglob("*") if p.is_file()}
