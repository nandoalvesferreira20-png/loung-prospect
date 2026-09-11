import ast
import json
from pathlib import Path

import pytest

from core.prototype.models import PrototypeTemplate
from core.prototype import registry


def write_template(root, directory="one", **overrides):
    folder = root / directory
    folder.mkdir()
    data = dict(template_id=directory, name="Template", segment="dentista", version="1.0.0")
    data.update(overrides)
    (folder / "template.json").write_text(json.dumps(data), encoding="utf-8")
    return folder


def test_initial_template_and_default_api():
    templates = registry.list_templates()
    assert len(templates) == 1
    template = registry.get_template("dentist-modern-v1")
    assert isinstance(template, PrototypeTemplate)
    assert template.version == "1.0.0"
    assert template.segment == "dentista"
    assert registry.find_templates_for_segment(" DENTISTA ") == [template]
    assert {p.name for p in Path(template.template_path).iterdir()} == {"template.json", "index.html", "css", "js"}


def test_discovery_path_order_and_id_lookup(tmp_path):
    first = write_template(tmp_path, "a", template_id="z")
    second = write_template(tmp_path, "b", template_id="a")
    reg = registry.TemplateRegistry(tmp_path)
    assert [t.template_id for t in reg.list_templates()] == ["a", "z"]
    assert reg.get_template("z").template_path == str(first.resolve())
    assert reg.get_template("a").template_path == str(second.resolve())
    assert "template_path" not in json.loads((first / "template.json").read_text())


@pytest.mark.parametrize("segment", ["dentista", "DENTISTA", "  Dentista  "])
def test_segment_matching(tmp_path, segment):
    write_template(tmp_path, segment=" Dentista ")
    reg = registry.TemplateRegistry(tmp_path)
    assert len(reg.find_templates_for_segment(segment)) == 1
    assert reg.find_templates_for_segment("barbearia") == []


def test_missing_template(tmp_path):
    with pytest.raises(registry.TemplateNotFoundError, match="missing"):
        registry.TemplateRegistry(tmp_path).get_template("missing")


def test_missing_manifest(tmp_path):
    (tmp_path / "empty").mkdir()
    with pytest.raises(registry.TemplateRegistryError, match="template.json"):
        registry.TemplateRegistry(tmp_path).list_templates()


@pytest.mark.parametrize("content", ["{broken", "[]", "null"])
def test_invalid_json_or_structure(tmp_path, content):
    folder = write_template(tmp_path)
    (folder / "template.json").write_text(content)
    with pytest.raises(registry.TemplateRegistryError, match="Invalid template manifest"):
        registry.TemplateRegistry(tmp_path).list_templates()


@pytest.mark.parametrize("field", ["template_id", "name", "segment", "version"])
def test_missing_required_field(tmp_path, field):
    folder = write_template(tmp_path)
    path = folder / "template.json"
    data = json.loads(path.read_text())
    del data[field]
    path.write_text(json.dumps(data))
    with pytest.raises(registry.TemplateRegistryError):
        registry.TemplateRegistry(tmp_path).list_templates()


def test_duplicate_id(tmp_path):
    write_template(tmp_path, "a", template_id="same")
    write_template(tmp_path, "b", template_id="same")
    with pytest.raises(registry.TemplateRegistryError, match="Duplicate template_id: same"):
        registry.TemplateRegistry(tmp_path).list_templates()


def test_paths_in_manifest_rejected(tmp_path):
    write_template(tmp_path, template_path=str(tmp_path.resolve()))
    with pytest.raises(registry.TemplateRegistryError):
        registry.TemplateRegistry(tmp_path).list_templates()


def test_empty_root_and_missing_root(tmp_path):
    assert registry.TemplateRegistry(tmp_path).list_templates() == []
    with pytest.raises(registry.TemplateRegistryError, match="directory not found"):
        registry.TemplateRegistry(tmp_path / "missing").list_templates()


def test_no_recursive_discovery(tmp_path):
    folder = write_template(tmp_path)
    write_template(folder, "nested")
    (tmp_path / "notes.txt").write_text("ignored")
    assert len(registry.TemplateRegistry(tmp_path).list_templates()) == 1


def test_dependency_boundary():
    tree = ast.parse(Path(registry.__file__).read_text(encoding="utf-8"))
    assert {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)} <= {"pathlib", "models"}
    assert {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names} == {"json"}
