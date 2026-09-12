from copy import deepcopy
from types import MappingProxyType

import pytest

from core.qualification.adapter import adapt_record_to_qualification_input
from core.qualification.models import ObservationStatus, QualificationInput


@pytest.fixture
def record():
    return {
        "Empresa": "Clínica Sintética", "Cidade": "Cidade Teste",
        "Segmento": "clínica", "Telefone": "(00) 0000-0000",
        "WhatsApp": "(00) 0000-0000", "Site": "https://clinic.example.test",
        "Endereço": "Rua Fictícia, 1", "Avaliação": "4,5 estrelas",
        "Google Maps": "https://maps.example.test/place/1",
    }


def test_current_complete_record(record):
    result = adapt_record_to_qualification_input(record)
    assert isinstance(result, QualificationInput)
    expected = dict(company_name="Clínica Sintética", city="Cidade Teste",
                    segment="clínica", phone="(00) 0000-0000",
                    whatsapp="(00) 0000-0000", website="https://clinic.example.test",
                    address="Rua Fictícia, 1", rating="4,5 estrelas",
                    source_url="https://maps.example.test/place/1")
    for name, value in expected.items():
        assert getattr(result, name) == value
        assert result.observation_status(name) is ObservationStatus.OBSERVED
    assert result.lead_id is None
    assert result.observation_status("lead_id") is ObservationStatus.UNVERIFIED


def test_legacy_segment(record):
    record["Segmento pesquisado"] = record.pop("Segmento")
    assert adapt_record_to_qualification_input(record).segment == "clínica"


@pytest.mark.parametrize("current, expected", [("atual", "atual"), ("", None), (None, None)])
def test_current_segment_key_wins(current, expected):
    result = adapt_record_to_qualification_input({"Segmento": current, "Segmento pesquisado": "legado"})
    assert result.segment == expected


@pytest.mark.parametrize("empty", ["", " \t\n", None])
def test_empty_values_are_unverified(record, empty):
    result = adapt_record_to_qualification_input(dict.fromkeys(record, empty))
    for name, status in result.observations.items():
        assert getattr(result, name) is None
        assert status is ObservationStatus.UNVERIFIED


def test_missing_fields():
    result = adapt_record_to_qualification_input({})
    assert set(result.observations) == {
        "company_name", "city", "segment", "source_url", "phone", "whatsapp",
        "website", "address", "rating", "user_rating_count", "lead_id",
    }
    for name in result.observations:
        assert getattr(result, name) is None
        assert result.observation_status(name) is ObservationStatus.UNVERIFIED


def test_extras_ignored_and_original_not_mutated(record):
    record.update({"extra": {"items": [1, 2]}, "Status Comercial": "Novo Lead"})
    original = deepcopy(record)
    result = adapt_record_to_qualification_input(MappingProxyType(record))
    assert result == adapt_record_to_qualification_input({key: value for key, value in record.items()
                                                        if key not in ("extra", "Status Comercial")})
    result.observations.clear()
    result.company_name = "Outro"
    assert record == original


def test_nonempty_text_is_not_normalized():
    result = adapt_record_to_qualification_input({"Empresa": "  Empresa  ", "Telefone": " +55 (00) 123 ", "Avaliação": "4,5 estrelas"})
    assert result.company_name == "  Empresa  "
    assert result.phone == " +55 (00) 123 "
    assert result.rating == "4,5 estrelas"
    assert result.whatsapp is None


def test_explicit_identifier_is_preserved():
    assert adapt_record_to_qualification_input({"lead_id": "external-123"}).lead_id == "external-123"


@pytest.mark.parametrize("value", [123, False, [], {}])
def test_known_nontext_value_rejected_without_mutation(value):
    record = {"Telefone": value}
    original = deepcopy(record)
    with pytest.raises(TypeError, match="Telefone"):
        adapt_record_to_qualification_input(record)
    assert record == original
