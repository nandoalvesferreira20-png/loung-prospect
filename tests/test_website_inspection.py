from copy import deepcopy
from unittest.mock import Mock

import pandas as pd
import pytest

from core.extractor import extract_company_data
from core.qualification.adapter import adapt_record_to_qualification_input
from core.validator import WEBSITE_VERIFICATION_KEY
from core.website_inspection import enrich_website_verification


def page_for(site=""):
    page = Mock(url="https://maps.example.test/1")
    empty = Mock()
    empty.count.return_value = 0
    name = Mock()
    name.count.return_value = 1
    name.first.inner_text.return_value = "Empresa"
    controls = Mock()
    controls.count.return_value = 1 if site else 0
    controls.nth.return_value.get_attribute.side_effect = lambda attr: "Site:" if attr == "aria-label" else site
    page.locator.side_effect = lambda selector: name if selector == "h1.DUwDvf" else controls if selector == "button[aria-label], a[aria-label]" else empty
    page.evaluate.return_value = {"name": "Empresa", "url": page.url,
                                  "websites": [site] if site else [], "signature": "stable panel"}
    return page


@pytest.mark.parametrize("site,expected", [("https://company.example.test", "observed"), ("", "not_found")])
def test_real_extractor_to_adapter(site, expected):
    page = page_for(site)
    record = extract_company_data(page, "Cidade", "Segmento", verify_website=True)
    assert record["Site"] == site
    assert record[WEBSITE_VERIFICATION_KEY].completed is True
    assert adapt_record_to_qualification_input(record).observation_status("website") == expected


@pytest.mark.parametrize("mode", ["missing", "changing", "wrong_name", "wrong_url", "unknown_control", "generic_link"])
def test_uncertain_dom_never_produces_not_found(mode):
    page = page_for()
    if mode == "missing":
        page.evaluate.return_value = None
    elif mode == "changing":
        snapshot = page.evaluate.return_value
        page.evaluate.side_effect = [snapshot, {**snapshot, "signature": "changed"}]
    elif mode == "wrong_name":
        page.evaluate.return_value["name"] = "Outra"
    elif mode == "wrong_url":
        page.evaluate.return_value["url"] = "https://maps.example.test/other"
    elif mode == "unknown_control":
        page.evaluate.return_value["websites"] = [""]
    record = extract_company_data(page, "Cidade", "Segmento")
    if mode == "generic_link":
        record["Site"] = "https://social.example.test"
    original = deepcopy(record)
    enriched = enrich_website_verification(page, record)
    assert adapt_record_to_qualification_input(enriched).observation_status("website") == "unverified"
    assert record == original


def test_inspection_exception_becomes_error():
    page = page_for()
    page.evaluate.side_effect = TimeoutError("Synthetic timeout")
    record = extract_company_data(page, "C", "S", verify_website=True)
    assert record[WEBSITE_VERIFICATION_KEY].error is True
    assert adapt_record_to_qualification_input(record).observation_status("website") == "error"


def test_legacy_extractor_does_not_inspect():
    page = page_for()
    record = extract_company_data(page, "C", "S")
    assert WEBSITE_VERIFICATION_KEY not in record
    page.evaluate.assert_not_called()


@pytest.mark.parametrize("enabled", [False, True])
def test_metadata_never_exported_and_reaches_qualification(harness, enabled):
    record = extract_company_data(page_for(), "C", "S", verify_website=True)
    harness.extract.side_effect = [record]
    summary = harness.run(qualification_enabled=enabled)
    assert WEBSITE_VERIFICATION_KEY not in pd.read_excel(harness.output).columns
    if enabled:
        assert summary["qualificacoes"][0]["resultado"].opportunity == "website"
        assert summary["qualificacoes"][0]["registro"][WEBSITE_VERIFICATION_KEY] == record[WEBSITE_VERIFICATION_KEY]
