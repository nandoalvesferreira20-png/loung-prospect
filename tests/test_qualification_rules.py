from copy import deepcopy
from itertools import product

import pytest

from core.qualification.models import QualificationInput
from core.qualification.rules import (
    RULES_VERSION,
    WEIGHTS,
    CommercialPriority,
    classify_priority,
    evaluate_rules,
)


def lead(**changes):
    values = dict(
        company_name="Empresa",
        city="Cidade",
        segment="Clínica",
        observations={
            "company_name": "observed",
            "segment": "observed",
            "website": "not_found",
        },
    )
    values.update(changes)
    return QualificationInput(**values)


def codes(notes):
    return {note.code for note in notes}


def test_explicit_site_not_found_is_source_scoped_opportunity():
    result = evaluate_rules(lead())

    assert (
        result.status,
        result.opportunity,
        result.score,
    ) == (
        "qualified",
        "website",
        30,
    )

    assert "website_not_found" in codes(result.reasons)
    assert "website_not_found" in codes(result.evidence)
    assert "website_absence_unconfirmed" in codes(result.limitations)


@pytest.mark.parametrize(
    "website",
    [None, "", "https://example.test"],
)
def test_unverified_site_never_generates_website_signal(website):
    result = evaluate_rules(
        lead(
            website=website,
            observations={
                "company_name": "observed",
                "segment": "observed",
            },
        )
    )

    assert (
        result.status,
        result.opportunity,
        result.score,
    ) == (
        "insufficient_data",
        "needs_review",
        0,
    )

    assert "website_unverified" in codes(result.limitations)
    assert not result.reasons


@pytest.mark.parametrize(
    "field,expected_score",
    [
        ("phone", 50),
        ("address", 35),
    ],
)
def test_observed_operational_signal(field, expected_score):
    data = lead(**{field: "Synthetic"})
    data.observations[field] = "observed"

    result = evaluate_rules(data)

    assert result.score == expected_score
    assert f"{field}_observed" in codes(result.reasons)
    assert f"{field}_observed" in codes(result.evidence)


@pytest.mark.parametrize(
    "state",
    ["unverified", "error", "not_found"],
)
def test_present_but_unobserved_phone_and_address_do_not_score(state):
    data = lead(
        phone="123",
        address="Rua A",
    )

    data.observations.update(
        phone=state,
        address=state,
    )

    assert evaluate_rules(data).score == 30


@pytest.mark.parametrize(
    "field",
    ["company_name", "segment"],
)
@pytest.mark.parametrize(
    "value",
    [None, "", "  "],
)
def test_missing_context_is_insufficient_even_with_site_signal(
    field,
    value,
):
    result = evaluate_rules(
        lead(**{field: value})
    )

    assert result.status == "insufficient_data"
    assert result.opportunity == "needs_review"
    assert f"{field}_unavailable" in codes(result.limitations)


def test_minimum_and_sparse_data():
    result = evaluate_rules(
        QualificationInput(
            None,
            None,
            None,
        )
    )

    assert (
        result.status,
        result.opportunity,
        result.score,
    ) == (
        "insufficient_data",
        "needs_review",
        0,
    )


def test_supported_score_and_consistent_reasons():
    data = lead(
        phone="123",
        address="Rua A",
        source_url="https://source.example.test",
    )

    data.observations.update(
        phone="observed",
        address="observed",
    )

    result = evaluate_rules(data)

    expected = (
        WEIGHTS["website_not_found"]
        + WEIGHTS["phone_observed"]
        + WEIGHTS["address_observed"]
    )

    assert result.score == expected == 55

    assert codes(result.reasons) == {
        "website_not_found",
        "phone_observed",
        "address_observed",
    }

    assert codes(result.reasons) <= codes(result.evidence)

    assert all(
        note.source_url == data.source_url
        for note in result.evidence
    )


def test_determinism_version_no_mutation_or_shared_results():
    data = lead()
    original = deepcopy(data)

    first = evaluate_rules(data)
    second = evaluate_rules(data)

    assert first == second
    assert data == original
    assert first.rules_version == RULES_VERSION == "3.0.0"
    assert first.analyzed_at is None

    first.reasons.clear()

    assert second.reasons


def test_observed_site_remains_commercial_lead_but_needs_review():
    data = lead(
        website="https://example.test",
    )

    data.observations["website"] = "observed"

    result = evaluate_rules(data)

    assert (
        result.status,
        result.opportunity,
        result.score,
    ) == (
        "qualified",
        "needs_review",
        5,
    )

    assert "own_website_observed" in codes(result.evidence)
    assert "own_website_observed" in codes(result.reasons)
    assert "website_not_inspected" in codes(result.limitations)


@pytest.mark.parametrize(
    "state,value,code",
    [
        ("error", None, "website_error"),
        ("observed", None, "website_inconsistent"),
        (
            "not_found",
            "https://example.test",
            "website_inconsistent",
        ),
    ],
)
def test_bad_site_evidence_needs_review(
    state,
    value,
    code,
):
    data = lead(
        website=value,
    )

    data.observations["website"] = state

    result = evaluate_rules(data)

    assert (
        result.status,
        result.opportunity,
        result.score,
    ) == (
        "insufficient_data",
        "needs_review",
        0,
    )

    assert code in codes(result.limitations)


def test_observed_whatsapp_scores_but_never_authorizes_contact():
    data = lead(
        whatsapp="5512999999999",
    )

    data.observations["whatsapp"] = "observed"

    result = evaluate_rules(data)

    assert result.score == 40

    assert "whatsapp_observed" in codes(result.reasons)
    assert "whatsapp_observed" in codes(result.evidence)

    assert "human_review_required" in codes(
        result.limitations
    )

    assert not hasattr(
        result,
        "contact_authorized",
    )


@pytest.mark.parametrize(
    "rating",
    [4, 4.0, 4.7, "4.8", "4,9"],
)
def test_rating_four_or_more_scores(rating):
    data = lead(
        rating=rating,
    )

    data.observations["rating"] = "observed"

    result = evaluate_rules(data)

    assert result.score == 40
    assert "rating_4_plus" in codes(result.reasons)
    assert "rating_observed" in codes(result.evidence)


@pytest.mark.parametrize(
    "rating",
    [0, 2.5, 3.9, "3,8"],
)
def test_rating_below_four_is_evidence_without_bonus(rating):
    data = lead(
        rating=rating,
    )

    data.observations["rating"] = "observed"

    result = evaluate_rules(data)

    assert result.score == 30
    assert "rating_observed" in codes(result.evidence)
    assert "rating_4_plus" not in codes(result.reasons)


@pytest.mark.parametrize(
    "rating",
    [" estrelas", "abc", -1, 6],
)
def test_invalid_rating_does_not_score(rating):
    data = lead(
        rating=rating,
    )

    data.observations["rating"] = "observed"

    result = evaluate_rules(data)

    assert result.score == 30
    assert "rating_invalid" in codes(result.limitations)


@pytest.mark.parametrize(
    "count,bonus,code",
    [
        (0, 0, None),
        (19, 0, None),
        (20, 5, "reviews_20_49"),
        (49, 5, "reviews_20_49"),
        (50, 10, "reviews_50_99"),
        (99, 10, "reviews_50_99"),
        (100, 20, "reviews_100_plus"),
        (500, 20, "reviews_100_plus"),
        ("150", 20, "reviews_100_plus"),
    ],
)
def test_review_count_scoring(
    count,
    bonus,
    code,
):
    data = lead(
        user_rating_count=count,
    )

    data.observations[
        "user_rating_count"
    ] = "observed"

    result = evaluate_rules(data)

    assert result.score == 30 + bonus

    assert (
        "user_rating_count_observed"
        in codes(result.evidence)
    )

    if code is not None:
        assert code in codes(result.reasons)


@pytest.mark.parametrize(
    "value",
    ["abc", "-10", -1],
)
def test_invalid_review_count_does_not_score(value):
    data = lead(
        user_rating_count=value,
    )

    data.observations[
        "user_rating_count"
    ] = "observed"

    result = evaluate_rules(data)

    assert result.score == 30

    assert (
        "user_rating_count_invalid"
        in codes(result.limitations)
    )


def test_full_commercial_signal_set_is_capped_at_100():
    data = lead(
        phone="123",
        whatsapp="5512999999999",
        address="Rua A",
        rating=4.9,
        user_rating_count=300,
    )

    data.observations.update(
        phone="observed",
        whatsapp="observed",
        address="observed",
        rating="observed",
        user_rating_count="observed",
    )

    result = evaluate_rules(data)

    assert result.score == 95
    assert 0 <= result.score <= 100


@pytest.mark.parametrize(
    "score,expected",
    [
        (0, CommercialPriority.LOW),
        (29, CommercialPriority.LOW),
        (30, CommercialPriority.MEDIUM),
        (49, CommercialPriority.MEDIUM),
        (50, CommercialPriority.GOOD),
        (69, CommercialPriority.GOOD),
        (70, CommercialPriority.HIGH),
        (100, CommercialPriority.HIGH),
    ],
)
def test_commercial_priority_ranges(
    score,
    expected,
):
    assert classify_priority(score) == expected


def test_priority_is_exposed_as_evidence():
    result = evaluate_rules(lead())

    priority_notes = [
        note
        for note in result.evidence
        if note.code == "commercial_priority"
    ]

    assert len(priority_notes) == 1
    assert "medium" in priority_notes[0].description


def test_all_basic_signal_combinations_remain_in_score_range():
    for website, phone, address in product(
        (False, True),
        repeat=3,
    ):
        data = lead(
            phone="123" if phone else None,
            address="Rua A" if address else None,
        )

        data.observations.update(
            website=(
                "not_found"
                if website
                else "unverified"
            ),
            phone=(
                "observed"
                if phone
                else "unverified"
            ),
            address=(
                "observed"
                if address
                else "unverified"
            ),
        )

        result = evaluate_rules(data)

        expected = (
            WEIGHTS["website_not_found"] * website
            + WEIGHTS["phone_observed"] * phone
            + WEIGHTS["address_observed"] * address
        )

        assert result.score == expected
        assert 0 <= result.score <= 100