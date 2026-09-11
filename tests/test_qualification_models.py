from dataclasses import FrozenInstanceError
from datetime import datetime, timezone

import pytest

from core.qualification import (
    ObservationStatus, QualificationInput, QualificationNote,
    QualificationResult, QualificationStatus,
)


def test_input_defaults():
    lead = QualificationInput("Empresa", "Cidade", "Segmento")
    assert (lead.company_name, lead.city, lead.segment) == ("Empresa", "Cidade", "Segmento")
    for name in ("lead_id", "source_url", "phone", "whatsapp", "website", "address", "rating"):
        assert getattr(lead, name) is None
        assert lead.observation_status(name) is ObservationStatus.UNVERIFIED
    assert lead.observations == {}


def test_input_preserves_values_without_inference():
    lead = QualificationInput(
        "Empresa", "Cidade", "Segmento", lead_id="id-1",
        source_url="https://source.example.test", phone="123", whatsapp="123",
        website="", address="Rua A", rating="4,5 estrelas",
        observations={"phone": ObservationStatus.OBSERVED},
    )
    assert lead.website == ""
    assert lead.rating == "4,5 estrelas"
    assert lead.phone == lead.whatsapp == "123"
    assert lead.observation_status("phone") is ObservationStatus.OBSERVED
    assert lead.observation_status("whatsapp") is ObservationStatus.UNVERIFIED


@pytest.mark.parametrize("status", list(ObservationStatus))
def test_unavailable_value_can_have_distinct_observation_states(status):
    lead = QualificationInput("E", "C", "S", observations={"website": status.value})
    assert lead.website is None
    assert lead.observation_status("website") is status


def test_observation_dictionaries_are_independent():
    original = {"website": ObservationStatus.NOT_FOUND}
    first = QualificationInput("E", "C", "S", observations=original)
    second = QualificationInput("E", "C", "S", observations=original)
    first.observations.clear()
    assert second.observations == original
    original.clear()
    assert second.observation_status("website") is ObservationStatus.NOT_FOUND
    empty = QualificationInput("E", "C", "S")
    first.observations["phone"] = ObservationStatus.ERROR
    assert empty.observations == {}


def test_unknown_observation_field_and_status_are_rejected():
    with pytest.raises(ValueError):
        QualificationInput("E", "C", "S", observations={"Site": "observed"})
    with pytest.raises(ValueError):
        QualificationInput("E", "C", "S", observations={"website": "invalid"})
    with pytest.raises(ValueError):
        QualificationInput("E", "C", "S").observation_status("Site")


@pytest.mark.parametrize("status", list(QualificationStatus))
def test_result_statuses_and_defaults(status):
    result = QualificationResult(status.value)
    assert result.status is status
    assert result.score is result.opportunity is None
    assert result.rules_version is result.analyzed_at is None
    assert result.reasons == result.evidence == result.limitations == []


def test_result_requires_explicit_valid_status():
    with pytest.raises(TypeError):
        QualificationResult()
    with pytest.raises(ValueError):
        QualificationResult("pending")


@pytest.mark.parametrize("score", [None, 0, 50, 100])
def test_optional_score_is_stored_without_calculation(score):
    assert QualificationResult("qualified", score=score).score == score


@pytest.mark.parametrize("score", [-1, 101, True, 0.5, "50"])
def test_invalid_score_representation_is_rejected(score):
    with pytest.raises(ValueError):
        QualificationResult("qualified", score=score)


def test_result_preserves_structured_notes_and_traceability():
    note = QualificationNote("sample", "Synthetic observation", "website", "https://example.test")
    instant = datetime(2026, 1, 1, tzinfo=timezone.utc)
    result = QualificationResult("qualified", opportunity="Synthetic", evidence=[note],
                                 rules_version="test-v1", analyzed_at=instant)
    assert result.evidence == [note]
    assert result.opportunity == "Synthetic"
    assert result.rules_version == "test-v1"
    assert result.analyzed_at == instant
    with pytest.raises(ValueError):
        QualificationResult("error", analyzed_at=datetime(2026, 1, 1))


@pytest.mark.parametrize("collection", ["reasons", "evidence", "limitations"])
def test_default_lists_are_independent(collection):
    first = QualificationResult("error")
    second = QualificationResult("error")
    getattr(first, collection).append(QualificationNote("test", "Test"))
    assert getattr(second, collection) == []
    for other in {"reasons", "evidence", "limitations"} - {collection}:
        assert getattr(first, other) == []


def test_caller_lists_are_copied_and_shared_notes_are_immutable():
    note = QualificationNote("test", "Test")
    shared = [note]
    first = QualificationResult("error", reasons=shared, evidence=shared, limitations=shared)
    second = QualificationResult("error", reasons=shared)
    shared.clear()
    first.reasons.clear()
    assert first.evidence == first.limitations == second.reasons == [note]
    with pytest.raises(FrozenInstanceError):
        note.description = "Changed"
