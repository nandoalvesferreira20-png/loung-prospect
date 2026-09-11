from unittest.mock import Mock

import pytest

from core.extractor import extract_company_data


def locator(items=()):
    result = Mock()
    result.count.return_value = len(items)
    result.first = items[0] if items else Mock()
    result.nth.side_effect = items.__getitem__
    return result


def element(text="", **attributes):
    result = Mock()
    result.inner_text.return_value = text
    result.get_attribute.side_effect = lambda name: attributes.get(name)
    return result


def page_with(selectors=None):
    page = Mock(url="https://maps.example.test/place/1")
    page.locator.side_effect = lambda selector: (selectors or {}).get(selector, locator())
    return page


def test_record_schema_empty_fields_and_commercial_defaults(columns):
    data = extract_company_data(page_with(), "Cidade Teste", "clínica")
    assert list(data) == columns
    assert data["Segmento"] == "clínica"
    assert "Segmento pesquisado" not in data
    assert data["Cidade"] == "Cidade Teste"
    assert data["Google Maps"] == "https://maps.example.test/place/1"
    assert data["Status Comercial"] == "Novo Lead"
    assert data["Próxima Ação"] == "Qualificar lead"
    for field in ("Empresa", "Telefone", "WhatsApp", "Site", "Endereço",
                  "Avaliação", "Potencial (1-5)", "Observações"):
        assert data[field] == ""


@pytest.mark.parametrize("labels", [
    ("Telefone:", "Endereço:", "Site:"),
    ("Phone:", "Address:", "Website:"),
])
def test_panel_values_and_known_phone_copied_to_whatsapp(labels):
    phone, address, site = labels
    page = page_with({
        "h1.DUwDvf": locator([element(" Clínica Sintética ")]),
        "button[aria-label], a[aria-label]": locator([
            element(**{"aria-label": f"{phone} (00) 0000-0000"}),
            element(**{"aria-label": f"{address} Rua Fictícia, 1"}),
            element(**{"aria-label": site, "href": "https://clinic.example.test"}),
        ]),
        "[aria-label*='estrelas'], [aria-label*='stars']": locator([
            element(**{"aria-label": "4,5 estrelas"}),
        ]),
    })
    data = extract_company_data(page, "Cidade Teste", "clínica")
    assert data["Empresa"] == "Clínica Sintética"
    assert data["Telefone"] == data["WhatsApp"] == "(00) 0000-0000"
    assert data["Endereço"] == "Rua Fictícia, 1"
    assert data["Site"] == "https://clinic.example.test"
    assert data["Avaliação"] == "4,5 estrelas"


def test_known_missing_site_and_extraction_error_are_indistinguishable():
    absent = page_with()
    broken = page_with()
    broken.locator.side_effect = RuntimeError("Synthetic selector failure")
    assert extract_company_data(absent, "C", "S") == extract_company_data(broken, "C", "S")


def test_fallback_name_and_known_first_external_link_used_as_site():
    page = page_with({
        "h1": locator([element("Empresa Sintética")]),
        "a[href^='http']": locator([
            element(href="https://google.com/example"),
            element(href="https://gstatic.com/example"),
            element(href="https://social.example.test/profile"),
            element(href="https://clinic.example.test"),
        ]),
    })
    data = extract_company_data(page, "C", "S")
    assert data["Empresa"] == "Empresa Sintética"
    assert data["Site"] == "https://social.example.test/profile"
