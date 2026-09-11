from unittest.mock import Mock

import pytest

from core.extractor import extract_company_data
from core.website_inspection import EXPLICIT_WEBSITE
from core.validator import WEBSITE_VERIFICATION_KEY
from core.qualification.adapter import adapt_record_to_qualification_input
from core.qualification.digital_presence import classify_digital_presence


@pytest.mark.parametrize("url,kind", [
    ("https://tribebarbershop.com.br/", "own_website"),
    ("https://hominisbarbershop.com/", "own_website"),
    ("http://jubabarbearia.com/?utm_source=gmb&utm_medium=referral", "own_website"),
    ("https://www.instagram.com/barberhousetaubate/", "social_media"),
    ("https://www.facebook.com/Goldenbarbershop2/", "social_media"),
    ("https://apps.apple.com/br/app/appbarber-cliente/id6450795073", "third_party_platform"),
    ("https://rcmanutencaoeassistencia.my.canva.site/seu-portuga-barbearia", "third_party_platform"),
    ("https://api.whatsapp.com/send?phone=123", "third_party_platform"),
    ("https://www.trinks.com/exemplo", "third_party_platform"),
    ("https://barb.page.link/LchbS", "unverified"),
])
def test_explicit_control_does_not_require_settled_panel(url, kind):
    page = Mock(url="https://maps.example.test/place/1")
    name = Mock()
    name.count.return_value = 1
    name.first.inner_text.return_value = "Empresa"
    empty = Mock()
    empty.count.return_value = 0
    page.locator.side_effect = lambda selector: name if selector == "h1.DUwDvf" else empty
    page.evaluate.side_effect = lambda script: {"name": "Empresa", "url": page.url, "explicit_href": url} if script == EXPLICIT_WEBSITE else None
    record = extract_company_data(page, "Cidade", "Segmento", verify_website=True)
    assert record["Site"] == url
    check = record[WEBSITE_VERIFICATION_KEY]
    assert check.website_source == "explicit_website_control"
    assert check.completed and check.website_found
    lead = adapt_record_to_qualification_input(record)
    assert lead.observation_status("website") == "observed"
    assert classify_digital_presence(lead.website, lead.observation_status("website")).presence_type == kind
    page.wait_for_timeout.assert_not_called()


@pytest.mark.parametrize("url", ["https://example.com", "https://facebook.com/test", "https://api.whatsapp.com/send", "https://barb.page.link/LchbS"])
def test_generic_link_not_promoted_by_provider(url):
    from core.website_inspection import enrich_website_verification, inspect_explicit_website
    page = Mock()
    page.evaluate.return_value = None
    record = {"Empresa": "Empresa", "Google Maps": "https://maps.example.test", "Site": url}
    assert inspect_explicit_website(page, record) is None
    result = enrich_website_verification(page, record)
    assert adapt_record_to_qualification_input(result).observation_status("website") == "unverified"
