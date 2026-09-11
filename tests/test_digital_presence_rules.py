from copy import deepcopy

import pytest

from core.qualification.adapter import adapt_record_to_qualification_input
from core.qualification.rules import evaluate_rules


@pytest.mark.parametrize("url,state,score,opportunity,code", [
    (None, "not_found", 80, "website", "website_not_found"),
    ("https://instagram.com/test", "observed", 70, "website", "social_media_presence"),
    ("https://facebook.com/test", "observed", 70, "website", "social_media_presence"),
    ("https://booksy.com/test", "observed", 60, "website", "third_party_platform"),
    ("https://apps.apple.com/test", "observed", 60, "website", "third_party_platform"),
    ("https://company.com.br", "observed", 20, "none", "own_website_observed"),
    (None, "unverified", 20, "needs_review", "website_unverified"),
    ("https://instagram.com/test", "unverified", 20, "needs_review", "website_unverified"),
    (None, "error", 20, "needs_review", "website_error"),
    ("not a url", "observed", 20, "needs_review", "website_inconsistent"),
])
def test_v2_pilot_patterns(url, state, score, opportunity, code):
    record = {"Empresa": "Exemplo", "Segmento": "Barbearia", "Site": url,
              "Telefone": "123", "Endereço": "Rua A", "Status Comercial": "Novo Lead",
              "Próxima Ação": "Revisar", "Potencial (1-5)": ""}
    original_record = deepcopy(record)
    lead = adapt_record_to_qualification_input(record)
    lead.observations["website"] = state
    original_lead = deepcopy(lead)
    result = evaluate_rules(lead)
    assert result.score == score
    assert result.opportunity == opportunity
    assert result.status == ("insufficient_data" if opportunity == "needs_review" else "qualified")
    assert code in {n.code for n in result.evidence + result.limitations}
    assert result.rules_version == "2.0.0"
    assert result == evaluate_rules(lead)
    assert lead == original_lead
    assert record == original_record
    assert "human_review_required" in {n.code for n in result.limitations}
    if code in ("social_media_presence", "third_party_platform"):
        assert code in {n.code for n in result.reasons}
        assert "independent_website_unconfirmed" in {n.code for n in result.limitations}
        assert "website_not_found" not in {n.code for n in result.reasons + result.evidence}


@pytest.mark.parametrize("field", ["Empresa", "Segmento"])
def test_external_presence_still_requires_context(field):
    record = {"Empresa": "Exemplo", "Segmento": "Barbearia", "Site": "https://instagram.com/test"}
    record[field] = ""
    result = evaluate_rules(adapt_record_to_qualification_input(record))
    assert result.status == "insufficient_data"
    assert result.opportunity == "needs_review"
    assert result.score == 50
