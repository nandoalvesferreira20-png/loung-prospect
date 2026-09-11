from concurrent.futures import ThreadPoolExecutor
from html.parser import HTMLParser
import json
from pathlib import Path

import pytest

from core.prototype.registry import list_templates, find_templates_for_segment
from core.prototype.generator import generate_prototype
from core.prototype.models import PrototypeLead, PrototypeRequest

TEMPLATES = {
    "dentista": "dentist-modern-v1", "veterinario": "veterinarian-friendly-v1",
    "estetica": "aesthetics-luxury-v1", "advogado": "lawyer-corporate-v1",
}


class HTMLStructure(HTMLParser):
    """Basic balance, IDs and resource checks, not a full HTML validator."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.ids = set()
        self.anchors = []
        self.resources = []
        self.headings = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag not in {"meta", "link", "br", "img", "hr", "input", "source", "wbr"}:
            self.stack.append(tag)
        if "id" in attrs:
            assert attrs["id"] not in self.ids
            self.ids.add(attrs["id"])
        if tag == "h1":
            self.headings += 1
        if tag == "a" and attrs.get("href", "").startswith("#"):
            self.anchors.append(attrs["href"][1:])
        if tag == "script":
            self.resources.append(attrs["src"])
        if tag == "link" and attrs.get("rel") == "stylesheet":
            self.resources.append(attrs["href"])

    def handle_endtag(self, tag):
        assert self.stack and self.stack.pop() == tag


def test_all_registry_ids():
    assert {template.template_id for template in list_templates()} == set(TEMPLATES.values())


@pytest.mark.parametrize("segment,template_id", TEMPLATES.items())
def test_canonical_filter(segment, template_id):
    templates = find_templates_for_segment(segment)
    assert [template.template_id for template in templates] == [template_id]
    assert templates[0].version == "1.0.0"


@pytest.mark.parametrize("segment", TEMPLATES)
@pytest.mark.parametrize("with_optional", [False, True])
def test_render_structure_and_original_preservation(tmp_path, segment, with_optional):
    template = find_templates_for_segment(segment)[0]
    source = Path(template.template_path)
    before = {path.relative_to(source): path.read_bytes() for path in source.rglob("*") if path.is_file()}
    extra = dict(city="São José", address="Rua Açucena, 10", phone="1133334444", whatsapp="5511999998888") if with_optional else {}
    lead = PrototypeLead("Espaço Saúde & Atenção", segment, **extra)
    result = generate_prototype(PrototypeRequest(lead, template, str(tmp_path / "output")))
    assert result.status == "created", result.errors
    root = Path(result.output_path)
    html = (root / "index.html").read_text(encoding="utf-8")
    assert "Espaço Saúde &amp; Atenção" in html
    assert "{{" not in html and "}}" not in html
    parser = HTMLStructure()
    parser.feed(html)
    parser.close()
    assert not parser.stack and parser.headings == 1
    assert set(parser.anchors) <= parser.ids
    assert set(parser.resources) == {"css/style.css", "js/script.js"}
    for resource in parser.resources:
        assert (root / resource).read_bytes() == before[Path(resource)]
    manifest = json.loads((root / "prototype.json").read_text(encoding="utf-8"))
    assert manifest["template_id"] == template.template_id
    assert manifest["template_version"] == "1.0.0"
    assert manifest["segment"] == segment
    if with_optional:
        assert "São José" in html and "Rua Açucena, 10" in html
        assert "https://wa.me/5511999998888" in html
    else:
        assert "https://wa.me/" not in html and 'href="tel:' not in html
        assert "Endereço informado" not in html
    assert before == {path.relative_to(source): path.read_bytes() for path in source.rglob("*") if path.is_file()}


def test_parallel_generation_independent(tmp_path):
    requests = [PrototypeRequest(PrototypeLead("Empresa " + template.segment, template.segment), template,
                                 str(tmp_path / "output")) for template in list_templates()]
    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(generate_prototype, requests))
    assert all(result.status == "created" for result in results), [result.errors for result in results]
    assert len({result.prototype_id for result in results}) == 4
    assert len({result.output_path for result in results}) == 4
    for request, result in zip(requests, results):
        html = (Path(result.output_path) / "index.html").read_text(encoding="utf-8")
        assert request.lead.company_name in html
        for other in requests:
            if other is not request:
                assert other.lead.company_name not in html
