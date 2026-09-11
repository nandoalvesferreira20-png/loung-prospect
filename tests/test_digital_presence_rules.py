from copy import deepcopy

import pytest

from core.qualification.adapter import (
    adapt_record_to_qualification_input,
)
from core.qualification.rules import evaluate_rules


@pytest.mark.parametrize(
    "url,state,score,opportunity,code",
    [
        (
            None,
            "not_found",
            55,
            "website",
            "website_not_found",
        ),
        (
            "https://instagram.com/test",
            "observed",
            50,
            "website",
            "social_media_presence",
        ),
        (
            "https://facebook.com/test",
            "observed",
            50,
            "website",
            "social_media_presence",
        ),
        (
            "https://booksy.com/test",
            "observed",
            45,
            "website",
            "third_party_platform",
        ),
        (
            "https://apps.apple.com/test",
            "observed",
            45,
            "website",
            "third_party_platform",
        ),
        (
            "https://company.com.br",
            "observed",
            30,
            "needs_review",
            "own_website_observed",
        ),
        (
            None,
            "unverified",
            25,
            "needs_review",
            "website_unverified",
        ),
        (
            "https://instagram.com/test",
            "unverified",
            25,
            "needs_review",
            "website_unverified",
        ),
        (
            None,
            "error",
            25,
            "needs_review",
            "website_error",
        ),
        (
            "not a url",
            "observed",
            25,
            "needs_review",
            "website_inconsistent",
        ),
    ],
)
def test_v3_pilot_patterns(
    url,
    state,
    score,
    opportunity,
    code,
):
    record = {
        "Empresa": "Exemplo",
        "Segmento": "Barbearia",
        "Site": url,
        "Telefone": "123",
        "Endereço": "Rua A",
        "Status Comercial": "Novo Lead",
        "Próxima Ação": "Revisar",
        "Potencial (1-5)": "",
    }

    original_record = deepcopy(record)

    lead = adapt_record_to_qualification_input(
        record
    )

    lead.observations["website"] = state

    original_lead = deepcopy(lead)

    result = evaluate_rules(lead)

    assert result.score == score
    assert result.opportunity == opportunity

    expected_status = (
        "qualified"
        if state == "observed"
        or state == "not_found"
        else "insufficient_data"
    )

    # Invalid/inconsistent observed website is not sufficient.
    if (
        state == "observed"
        and url == "not a url"
    ):
        expected_status = "insufficient_data"

    assert result.status == expected_status

    assert code in {
        note.code
        for note in (
            result.evidence
            + result.limitations
        )
    }

    assert result.rules_version == "3.0.0"

    assert result == evaluate_rules(lead)
    assert lead == original_lead
    assert record == original_record

    assert (
        "human_review_required"
        in {
            note.code
            for note in result.limitations
        }
    )

    if code in (
        "social_media_presence",
        "third_party_platform",
    ):
        assert code in {
            note.code
            for note in result.reasons
        }

        assert (
            "independent_website_unconfirmed"
            in {
                note.code
                for note in result.limitations
            }
        )

        assert (
            "website_not_found"
            not in {
                note.code
                for note in (
                    result.reasons
                    + result.evidence
                )
            }
        )


@pytest.mark.parametrize(
    "field",
    ["Empresa", "Segmento"],
)
def test_external_presence_still_requires_context(field):
    record = {
        "Empresa": "Exemplo",
        "Segmento": "Barbearia",
        "Site": "https://instagram.com/test",
    }

    record[field] = ""

    result = evaluate_rules(
        adapt_record_to_qualification_input(
            record
        )
    )

    assert result.status == "insufficient_data"
    assert result.opportunity == "needs_review"

    # Digital signal still exists even though identity context
    # is insufficient.
    assert result.score == 25