import json
from copy import deepcopy
from pathlib import Path
from uuid import UUID

import pytest

from core.prototype import generator
from core.prototype.models import PrototypeLead, PrototypeTemplate, PrototypeRequest


@pytest.fixture
def request_data(tmp_path):
    source = tmp_path / "template"
    source.mkdir()
    (source / "template.json").write_text("{}")
    (source / "README.template.txt").write_text("Neutral fixture", encoding="utf-8")
    (source / "assets").mkdir()
    (source / "assets" / "data.txt").write_text("unchanged")
    return PrototypeRequest(PrototypeLead("Clínica São José & Filhos", "dentista", qualification_score=70),
                            PrototypeTemplate("dentist", "Dentist", "dentista", "1.0.0", str(source)),
                            str(tmp_path / "output"))


@pytest.mark.parametrize("name,expected", [("Clínica São José & Filhos", "clinica-sao-jose-filhos"),
    ("A/B\\C:*?", "a-b-c"), ("../../outside", "outside"), ("..", "prototype"),
    ("", "prototype"), ("😀", "prototype"), ("CON", "prototype-con")])
def test_slug(name, expected):
    assert generator.safe_slug(name) == expected


def test_success_copy_manifest_and_nonmutation(request_data):
    before = deepcopy(request_data)
    result = generator.generate_prototype(request_data)
    assert result.status == "created"
    assert UUID(result.prototype_id).version == 4
    path = Path(result.output_path)
    assert path.parent == Path(request_data.output_directory)
    assert path.name.startswith("clinica-sao-jose-filhos-")
    assert (path / "README.template.txt").read_text() == "Neutral fixture"
    assert (path / "assets/data.txt").read_text() == "unchanged"
    assert not (path / "template.json").exists()
    data = json.loads((path / "prototype.json").read_text(encoding="utf-8"))
    assert data == dict(prototype_id=result.prototype_id, company_name=request_data.lead.company_name,
                       segment="dentista", template_id="dentist", template_version="1.0.0",
                       created_at=result.manifest.created_at.isoformat(), source="loung_prospect", qualification_score=70)
    assert data["created_at"].endswith("+00:00")
    assert "Clínica" in generator.serialize_manifest(result.manifest)
    assert generator.serialize_manifest(result.manifest) == generator.serialize_manifest(result.manifest)
    assert request_data == before


def test_unique_ids_existing_output_root(request_data):
    first = generator.generate_prototype(request_data)
    second = generator.generate_prototype(request_data)
    assert first.prototype_id != second.prototype_id
    assert Path(first.output_path).exists() and Path(second.output_path).exists()


def test_collision_does_not_overwrite(request_data, monkeypatch):
    monkeypatch.setattr(generator, "uuid4", lambda: UUID(int=1))
    first = generator.generate_prototype(request_data)
    second = generator.generate_prototype(request_data)
    assert second.status == "failed"
    assert "FileExistsError" in second.errors[0]
    assert (Path(first.output_path) / "prototype.json").exists()


def test_copy_failure_rolls_back(request_data, monkeypatch):
    def fail(source, target):
        Path(target).write_text("partial")
        raise OSError("Synthetic copy failure")
    monkeypatch.setattr(generator.shutil, "copy2", fail)
    result = generator.generate_prototype(request_data)
    assert result.status == "failed"
    assert "Synthetic copy failure" in result.errors[0]
    assert list(Path(request_data.output_directory).iterdir()) == []
    assert not result.warnings


def test_manifest_failure_rolls_back(request_data, monkeypatch):
    monkeypatch.setattr(generator, "serialize_manifest", lambda _: (_ for _ in ()).throw(ValueError("serialization failed")))
    assert generator.generate_prototype(request_data).status == "failed"
    assert list(Path(request_data.output_directory).iterdir()) == []


def test_symlink_rejected_without_following(request_data, monkeypatch):
    # Simulate detection on Windows without requiring symlink creation privileges.
    original = Path.is_symlink
    monkeypatch.setattr(Path, "is_symlink", lambda path: path.name == "README.template.txt" or original(path))
    result = generator.generate_prototype(request_data)
    assert result.status == "failed"
    assert "Links/junctions" in result.errors[0]
    assert not Path(request_data.output_directory).exists()


def test_reserved_manifest_rejected(request_data):
    (Path(request_data.template.template_path) / "prototype.json").write_text("reserved")
    assert generator.generate_prototype(request_data).status == "failed"


def test_invalid_request():
    assert generator.generate_prototype(None).status == "failed"


def test_overlap_rejected(request_data):
    request = PrototypeRequest(request_data.lead, request_data.template, request_data.template.template_path + "/output")
    result = generator.generate_prototype(request)
    assert result.status == "failed"
    assert "overlap" in result.errors[0]
