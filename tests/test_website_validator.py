from copy import deepcopy

import pytest

from core.validator import (
    WEBSITE_VERIFICATION_KEY, WebsiteVerification,
    website_observation, with_website_verification,
)
from core.qualification.adapter import adapt_record_to_qualification_input

SOURCE = "https://maps.example.test/place/1"


@pytest.mark.parametrize("value,expected", [("https://example.test", "observed"),
                                           ("", "unverified"), (None, "unverified"),
                                           ("  ", "unverified")])
def test_legacy_records(value, expected):
    record = {"Site": value}
    assert website_observation(record) == expected
    assert adapt_record_to_qualification_input(record).observation_status("website") == expected


def test_absent_field_alone_is_unverified():
    assert website_observation({}) == "unverified"


@pytest.mark.parametrize("site,found,expected", [
    ("", False, "not_found"), ("https://example.test", True, "observed"),
    ("https://example.test", False, "error"), ("", True, "error"),
])
def test_completed_report_and_contradictions(site, found, expected):
    record = with_website_verification({"Site": site, "Google Maps": SOURCE},
                                      WebsiteVerification(SOURCE, completed=True, website_found=found))
    assert website_observation(record) == expected
    result = adapt_record_to_qualification_input(record)
    assert result.observation_status("website") == expected
    assert result.website == (site or None)


@pytest.mark.parametrize("site", ["", "https://example.test"])
def test_verification_error_takes_precedence(site):
    record = with_website_verification({"Site": site, "Google Maps": SOURCE},
                                      WebsiteVerification(SOURCE, completed=True, website_found=False, error=True))
    assert adapt_record_to_qualification_input(record).observation_status("website") == "error"


@pytest.mark.parametrize("check", [
    WebsiteVerification(SOURCE),
    WebsiteVerification(SOURCE, website_found=False),
    WebsiteVerification(SOURCE, completed=True),
])
def test_incomplete_verification_cannot_establish_not_found(check):
    assert website_observation(with_website_verification({"Site": "", "Google Maps": SOURCE}, check)) == "unverified"


@pytest.mark.parametrize("check", [
    WebsiteVerification("https://different.example.test", True, False),
    WebsiteVerification("", True, False),
    WebsiteVerification(SOURCE, "yes", False),
    {"completed": True, "website_found": False},
])
def test_invalid_or_wrong_source_report_is_not_absence(check):
    record = {"Site": "", "Google Maps": SOURCE, WEBSITE_VERIFICATION_KEY: check}
    assert website_observation(record) == "error"


def test_nonmutation_and_other_fields_unchanged():
    original = {"Empresa": "Empresa", "Segmento pesquisado": "Clínica", "Telefone": "123",
                "WhatsApp": "123", "Site": "", "Google Maps": SOURCE}
    snapshot = deepcopy(original)
    enriched = with_website_verification(original, WebsiteVerification(SOURCE, True, False))
    before = deepcopy(enriched)
    result = adapt_record_to_qualification_input(enriched)
    legacy = adapt_record_to_qualification_input(original)
    assert original == snapshot
    assert enriched == before
    assert result.website is legacy.website is None
    assert result.observation_status("website") == "not_found"
    assert legacy.observation_status("website") == "unverified"
    result.observations["website"] = legacy.observations["website"]
    assert result == legacy
