from types import SimpleNamespace
from unittest.mock import Mock
from urllib.parse import parse_qs, urlsplit

import pytest

from core.sales.contact import normalize_phone, whatsapp_url


@pytest.mark.parametrize("value,expected", [
    ("(11) 99999-9999", "5511999999999"),
    ("(12) 99184-4481", "5512991844481"),
    ("+55 (11) 99999-9999", "5511999999999"),
    ("55 11 99999-9999", "5511999999999"),
    ("(11)\u00a099999-9999", "5511999999999"),
    ("+351 912 345 678", "351912345678"),
])
def test_phone_formatting(value, expected):
    assert normalize_phone(value) == expected


def authorized():
    return dict(telefone="(11) 99999-9999", whatsapp=" ", whatsapp_consent="Autorizado",
                consent_source="Formulário", consent_at="2026-01-01T00:00:00Z",
                consent_number="5511999999999", status="Novo", do_not_contact=0)


def test_url_preserves_current_text_and_never_mutates_lead():
    lead = authorized()
    before = lead.copy()
    text = "Olá! Edição humana & revisão?\nSão Paulo + 10% #ideia"
    url = whatsapp_url(lead, text)
    assert urlsplit(url).netloc == "wa.me"
    assert urlsplit(url).path == "/5511999999999"
    assert parse_qs(urlsplit(url).query)["text"] == [text]
    assert lead == before


@pytest.mark.parametrize("change", [dict(do_not_contact=1),
                                   dict(status="Não contatar"), dict(whatsapp_consent="Revogado")])
def test_no_link_for_explicit_contact_restrictions(change):
    with pytest.raises(ValueError):
        whatsapp_url(authorized() | change, "Mensagem")


@pytest.mark.parametrize("text", ["", " \n "])
def test_no_empty_message(text):
    with pytest.raises(ValueError, match="vazia"):
        whatsapp_url(authorized(), text)
