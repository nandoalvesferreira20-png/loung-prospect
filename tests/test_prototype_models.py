import ast
from dataclasses import FrozenInstanceError, asdict
from datetime import datetime, timezone
from pathlib import Path

import pytest

from core.prototype import (
    PrototypeLead, PrototypeTemplate, PrototypeRequest, PrototypeManifest,
    PrototypeResult, PrototypeStatus,
)

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def manifest(**changes):
    values = dict(prototype_id="p1", company_name="Empresa", segment="Barbearia",
                  template_id="barber", template_version="1.0", created_at=NOW)
    return PrototypeManifest(**(values | changes))


def test_valid_contracts_and_optional_defaults():
    lead = PrototypeLead("Empresa", "Barbearia")
    assert all(value is None for key, value in asdict(lead).items() if key not in ("company_name", "segment"))
    template = PrototypeTemplate("barber", "Barber", "Barbearia", "1.0", "templates/barber")
    request = PrototypeRequest(lead, template, "output")
    assert request.requested_at is None
    data = manifest()
    assert data.source is data.qualification_score is None
    result = PrototypeResult("created", "p1", "output/p1", data)
    assert result.status is PrototypeStatus.CREATED
    assert result.errors == result.warnings == []
    assert PrototypeResult("failed").prototype_id is None


@pytest.mark.parametrize("score", [None, 0, 50, 100])
def test_valid_scores(score):
    assert PrototypeLead("E", "S", qualification_score=score).qualification_score == score
    assert manifest(qualification_score=score).qualification_score == score


@pytest.mark.parametrize("score", [-1, 101, True, 1.5, "50"])
def test_invalid_scores(score):
    with pytest.raises(ValueError):
        PrototypeLead("E", "S", qualification_score=score)
    with pytest.raises(ValueError):
        manifest(qualification_score=score)


@pytest.mark.parametrize("value", ["", "  ", None])
def test_required_template_version_and_manifest_id(value):
    with pytest.raises(ValueError):
        PrototypeTemplate("t", "T", "S", value, "templates")
    with pytest.raises(ValueError):
        manifest(prototype_id=value)
    with pytest.raises(ValueError):
        manifest(template_version=value)


def test_created_requires_complete_identity():
    for kwargs in ({}, {"prototype_id": "p1"}, {"prototype_id": "p1", "output_path": "output"}):
        with pytest.raises(ValueError):
            PrototypeResult("created", **kwargs)
    with pytest.raises(ValueError):
        PrototypeResult("created", "other", "output", manifest())


@pytest.mark.parametrize("status", ["pending", "", None])
def test_invalid_status(status):
    with pytest.raises(ValueError):
        PrototypeResult(status)


def test_timestamp_validation():
    lead = PrototypeLead("E", "S")
    template = PrototypeTemplate("t", "T", "S", "v1", "templates")
    assert PrototypeRequest(lead, template, "output", NOW).requested_at == NOW
    for value in (datetime(2026, 1, 1), "2026-01-01"):
        with pytest.raises(ValueError):
            PrototypeRequest(lead, template, "output", value)
        with pytest.raises(ValueError):
            manifest(created_at=value)
    with pytest.raises(ValueError):
        manifest(created_at=None)


def test_independent_defaults_and_copied_collections():
    first, second = PrototypeResult("failed"), PrototypeResult("failed")
    first.errors.append("failure")
    first.warnings.append("warning")
    assert second.errors == second.warnings == []
    shared = ["input"]
    result = PrototypeResult("failed", errors=shared, warnings=shared)
    result.errors.append("local")
    assert shared == result.warnings == ["input"]
    shared.clear()
    assert result.warnings == ["input"]


def test_nested_models_immutable_and_paths_not_resolved(tmp_path):
    # Even unsafe-looking names remain data; future generator must sanitize them.
    lead = PrototypeLead("../Empresa", "S", opportunity="website")
    template = PrototypeTemplate("t", "T", "S", "v1", "missing/template")
    output = tmp_path / "not-created"
    request = PrototypeRequest(lead, template, str(output))
    assert request.lead is lead
    assert not output.exists()
    with pytest.raises(FrozenInstanceError):
        request.lead.company_name = "Changed"


def test_structural_types():
    with pytest.raises(TypeError):
        PrototypeRequest({}, {}, "output")
    with pytest.raises(TypeError):
        PrototypeResult("failed", errors="not a list")
    with pytest.raises(TypeError):
        PrototypeResult("failed", warnings=[123])
    with pytest.raises(ValueError):
        PrototypeLead("", "S")


def test_only_standard_library_dependencies():
    import core.prototype.models as models
    tree = ast.parse(Path(models.__file__).read_text(encoding="utf-8"))
    imports = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    assert imports <= {"dataclasses", "datetime", "enum"}
    assert not any(isinstance(node, ast.Import) for node in ast.walk(tree))
