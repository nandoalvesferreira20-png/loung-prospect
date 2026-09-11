from copy import deepcopy
from itertools import product

import pytest

from core.qualification.models import QualificationInput
from core.qualification.rules import RULES_VERSION, WEIGHTS, evaluate_rules


def lead(**changes):
    values = dict(company_name="Empresa", city="Cidade", segment="Clínica",
                  observations={"company_name": "observed", "segment": "observed", "website": "not_found"})
    values.update(changes)
    return QualificationInput(**values)


def codes(notes):
    return {note.code for note in notes}


def test_explicit_site_not_found_is_source_scoped_opportunity():
    result = evaluate_rules(lead())
    assert (result.status, result.opportunity, result.score) == ("qualified", "website", 60)
    assert "website_not_found" in codes(result.reasons) & codes(result.evidence)
    assert "website_absence_unconfirmed" in codes(result.limitations)


@pytest.mark.parametrize("website", [None, "", "https://example.test"])
def test_unverified_site_never_generates_website_signal(website):
    result = evaluate_rules(lead(website=website, observations={"company_name": "observed", "segment": "observed"}))
    assert (result.status, result.opportunity, result.score) == ("insufficient_data", "needs_review", 0)
    assert "website_unverified" in codes(result.limitations)
    assert not result.reasons


@pytest.mark.parametrize("field", ["phone", "address"])
def test_observed_operational_signal(field):
    data = lead(**{field: "Synthetic"})
    data.observations[field] = "observed"
    result = evaluate_rules(data)
    assert result.score == 70
    assert f"{field}_observed" in codes(result.reasons) & codes(result.evidence)


@pytest.mark.parametrize("state", ["unverified", "error", "not_found"])
def test_present_but_unobserved_phone_and_address_do_not_score(state):
    data = lead(phone="123", address="Rua A")
    data.observations.update(phone=state, address=state)
    assert evaluate_rules(data).score == 60


@pytest.mark.parametrize("field", ["company_name", "segment"])
@pytest.mark.parametrize("value", [None, "", "  "])
def test_missing_context_is_insufficient_even_with_site_signal(field, value):
    result = evaluate_rules(lead(**{field: value}))
    assert result.status == "insufficient_data"
    assert result.opportunity == "needs_review"
    assert f"{field}_unavailable" in codes(result.limitations)


def test_minimum_and_sparse_data():
    result = evaluate_rules(QualificationInput(None, None, None))
    assert (result.status, result.opportunity, result.score) == ("insufficient_data", "needs_review", 0)


def test_maximum_supported_score_and_consistent_reasons():
    data = lead(phone="123", address="Rua A", source_url="https://source.example.test")
    data.observations.update(phone="observed", address="observed")
    result = evaluate_rules(data)
    assert result.score == WEIGHTS["website_not_found"] + WEIGHTS["phone_observed"] + WEIGHTS["address_observed"] == 80
    assert codes(result.reasons) == {"website_not_found", "phone_observed", "address_observed"}
    assert codes(result.reasons) <= codes(result.evidence)
    assert all(note.source_url == data.source_url for note in result.evidence)


def test_determinism_version_no_mutation_or_shared_results():
    data = lead()
    original = deepcopy(data)
    first, second = evaluate_rules(data), evaluate_rules(data)
    assert first == second
    assert data == original
    assert first.rules_version == RULES_VERSION == "2.0.0"
    assert first.analyzed_at is None
    first.reasons.clear()
    assert second.reasons


def test_observed_site_has_no_supported_website_opportunity():
    data = lead(website="https://example.test")
    data.observations["website"] = "observed"
    result = evaluate_rules(data)
    assert (result.status, result.opportunity, result.score) == ("qualified", "none", 0)
    assert "website_not_inspected" in codes(result.limitations)


@pytest.mark.parametrize("state,value,code", [
    ("error", None, "website_error"),
    ("observed", None, "website_inconsistent"),
    ("not_found", "https://example.test", "website_inconsistent"),
])
def test_bad_site_evidence_needs_review(state, value, code):
    data = lead(website=value)
    data.observations["website"] = state
    result = evaluate_rules(data)
    assert (result.status, result.opportunity, result.score) == ("insufficient_data", "needs_review", 0)
    assert code in codes(result.limitations)


def test_whatsapp_alone_neither_scores_nor_authorizes_contact():
    data = lead(whatsapp="123")
    data.observations["whatsapp"] = "observed"
    result = evaluate_rules(data)
    assert result.score == 60
    assert {"contact_unverified", "human_review_required"} <= codes(result.limitations)


def test_all_signal_combinations_remain_in_score_range():
    for website, phone, address in product((False, True), repeat=3):
        data = lead(phone="123" if phone else None, address="Rua A" if address else None)
        data.observations.update(website="not_found" if website else "unverified",
                                 phone="observed", address="observed")
        result = evaluate_rules(data)
        assert result.score == 60 * website + 10 * phone + 10 * address
        assert 0 <= result.score <= 100
