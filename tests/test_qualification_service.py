from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timezone
from types import MappingProxyType
from unittest.mock import Mock

import pytest

from core.qualification import service
from core.qualification.adapter import (
    adapt_record_to_qualification_input,
)
from core.qualification.models import QualificationInput
from core.qualification.rules import (
    RULES_VERSION,
    evaluate_rules,
)


@pytest.fixture
def record():
    return {
        "Empresa": "Empresa Teste",
        "Cidade": "Cidade",
        "Segmento": "Clínica",
        "Site": "https://example.test",
        "Telefone": "123",
        "Status Comercial": "Novo Lead",
        "extra": {"items": [1]},
    }


@pytest.fixture(autouse=True)
def fixed_clock(monkeypatch):
    instant = datetime(
        2026,
        1,
        1,
        tzinfo=timezone.utc,
    )

    clock = Mock()
    clock.now.return_value = instant

    monkeypatch.setattr(
        service,
        "datetime",
        clock,
    )

    return instant


def test_valid_record_matches_rules_exactly_except_timestamp(
    record,
    fixed_clock,
):
    expected = evaluate_rules(
        adapt_record_to_qualification_input(
            record
        )
    )

    result = service.qualify_record(record)

    assert result == replace(
        expected,
        analyzed_at=fixed_clock,
    )

    assert result.status == "qualified"
    assert result.rules_version == RULES_VERSION

    assert (
        result.analyzed_at
        .utcoffset()
        .total_seconds()
        == 0
    )

    service.datetime.now.assert_called_once_with(
        timezone.utc
    )


def test_insufficient_record():
    result = service.qualify_record({})

    assert result.status == "insufficient_data"
    assert result.opportunity == "needs_review"
    assert result.score == 0


def test_website_opportunity_uses_explicit_adapter_output(
    monkeypatch,
    record,
):
    lead = QualificationInput(
        "Empresa",
        "Cidade",
        "Clínica",
        observations={
            "company_name": "observed",
            "segment": "observed",
            "website": "not_found",
        },
    )

    adapter = Mock(
        return_value=lead
    )

    rules = Mock(
        wraps=evaluate_rules
    )

    monkeypatch.setattr(
        service,
        "adapt_record_to_qualification_input",
        adapter,
    )

    monkeypatch.setattr(
        service,
        "evaluate_rules",
        rules,
    )

    result = service.qualify_record(
        record
    )

    adapter.assert_called_once_with(
        record
    )

    rules.assert_called_once_with(
        lead
    )

    assert (
        result.status,
        result.opportunity,
        result.score,
    ) == (
        "qualified",
        "website",
        30,
    )


@pytest.mark.parametrize(
    "stage,function",
    [
        (
            "adapter",
            "adapt_record_to_qualification_input",
        ),
        (
            "rules",
            "evaluate_rules",
        ),
    ],
)
def test_internal_failure_is_structured_without_raw_exception(
    monkeypatch,
    record,
    fixed_clock,
    stage,
    function,
):
    monkeypatch.setattr(
        service,
        function,
        Mock(
            side_effect=RuntimeError(
                "private raw data\nTraceback"
            )
        ),
    )

    result = service.qualify_record(
        record
    )

    assert result.status == "error"

    assert (
        result.score
        is result.opportunity
        is result.rules_version
        is None
    )

    assert result.analyzed_at == fixed_clock
    assert len(result.limitations) == 1

    assert (
        result.limitations[0].code
        == f"{stage}_error"
    )

    assert (
        "RuntimeError"
        in result.limitations[0].description
    )

    assert (
        "private raw data"
        not in result.limitations[0].description
    )

    assert (
        "Traceback"
        not in result.limitations[0].description
    )


def test_rules_not_called_after_adapter_failure(
    monkeypatch,
):
    rules = Mock()

    monkeypatch.setattr(
        service,
        "evaluate_rules",
        rules,
    )

    assert (
        service.qualify_record(
            {"Telefone": 123}
        ).status
        == "error"
    )

    rules.assert_not_called()


def test_batch_order_continuity_and_no_mutation(
    record,
):
    records = [
        record,
        {"Telefone": 123},
        {},
    ]

    original = deepcopy(records)

    results = service.qualify_records(
        MappingProxyType(item)
        for item in records
    )

    assert [
        result.status
        for result in results
    ] == [
        "qualified",
        "error",
        "insufficient_data",
    ]

    # Own website + phone + no address.
    assert [
        result.score
        for result in results
    ] == [
        25,
        None,
        0,
    ]

    assert records == original


def test_batch_continues_after_rules_failure(
    monkeypatch,
    record,
):
    result = evaluate_rules(
        adapt_record_to_qualification_input(
            record
        )
    )

    monkeypatch.setattr(
        service,
        "evaluate_rules",
        Mock(
            side_effect=[
                result,
                RuntimeError("failure"),
                result,
            ]
        ),
    )

    assert [
        item.status
        for item in service.qualify_records(
            [record] * 3
        )
    ] == [
        "qualified",
        "error",
        "qualified",
    ]


def test_empty_batch():
    assert service.qualify_records([]) == []


def test_preserves_rule_output_version_and_does_not_mutate_it(
    monkeypatch,
    record,
):
    result = evaluate_rules(
        adapt_record_to_qualification_input(
            record
        )
    )

    result.rules_version = (
        "synthetic-version"
    )

    original = deepcopy(result)

    monkeypatch.setattr(
        service,
        "evaluate_rules",
        Mock(return_value=result),
    )

    actual = service.qualify_record(
        record
    )

    assert (
        actual.rules_version
        == "synthetic-version"
    )

    assert result == original
    assert actual is not result


def test_no_commercial_status_change_or_contact_authorization(
    record,
):
    original = deepcopy(record)

    result = service.qualify_record(
        MappingProxyType(record)
    )

    assert record == original

    assert (
        record["Status Comercial"]
        == "Novo Lead"
    )

    assert (
        "human_review_required"
        in {
            note.code
            for note in result.limitations
        }
    )

    assert not hasattr(
        result,
        "contact_authorized",
    )


def test_iterable_failure_propagates():
    def records():
        yield {}
        raise RuntimeError(
            "Input unavailable"
        )

    with pytest.raises(
        RuntimeError,
        match="Input unavailable",
    ):
        service.qualify_records(
            records()
        )