from copy import deepcopy
from dataclasses import FrozenInstanceError

import pytest

from core.qualification.digital_presence import classify_digital_presence
from core.qualification.adapter import adapt_record_to_qualification_input
from core.qualification.rules import evaluate_rules


@pytest.mark.parametrize("url,kind,provider", [
    ("https://empresa.com.br", "own_website", None),
    ("https://clinicax.com", "own_website", None),
    ("https://instagram.com/barbearia", "social_media", "Instagram"),
    ("https://facebook.com/barbearia", "social_media", "Facebook"),
    ("https://fb.com/barbearia", "social_media", "Facebook"),
    ("https://tiktok.com/@barbearia", "social_media", "TikTok"),
    ("https://linkedin.com/company/test", "social_media", "LinkedIn"),
    ("https://youtube.com/channel/test", "social_media", "YouTube"),
    ("https://youtu.be/test", "social_media", "YouTube"),
    ("https://apps.apple.com/br/app/example/id123", "third_party_platform", "App Store"),
    ("https://play.google.com/store/apps/details?id=test", "third_party_platform", "Google Play"),
    ("https://linktr.ee/barbearia", "third_party_platform", "Linktree"),
    ("https://booksy.com/pt-br/test", "third_party_platform", "Booksy"),
    ("https://calendly.com/test", "third_party_platform", "Calendly"),
    ("https://empresa.wixsite.com/home", "third_party_platform", "Wix"),
    ("https://empresa.wordpress.com", "third_party_platform", "WordPress.com"),
    ("https://m.facebook.com/test", "social_media", "Facebook"),
    ("https://WWW.Instagram.COM/test", "social_media", "Instagram"),
    ("https://agenda.plataforma-desconhecida.com", "own_website", None),
    ("https://instagram.com.example.test", "own_website", None),
    ("https://notinstagram.com", "own_website", None),
])
def test_observed_provider_patterns(url, kind, provider):
    result = classify_digital_presence(url, "observed")
    assert result.presence_type == kind
    assert result.provider == provider
    assert result.url == url
    assert result.reason


def test_hostname_normalization_preserves_original_url():
    url = "https://WWW.Instagram.COM/Test?A=B"
    result = classify_digital_presence(url, "observed")
    assert result.hostname == "instagram.com"
    assert result.url == url


@pytest.mark.parametrize("url", [None, "", "  "])
def test_empty_needs_explicit_absence(url):
    assert classify_digital_presence(url).presence_type == "unverified"
    assert classify_digital_presence(url, "not_found").presence_type == "not_found"


@pytest.mark.parametrize("url", ["", "https://instagram.com/test"])
def test_explicit_error_preserved(url):
    assert classify_digital_presence(url, "error").presence_type == "error"


@pytest.mark.parametrize("url", ["not a url", "empresa.com.br", "ftp://example.com", "https://",
                                 "https://[broken", "https://example.com:bad", "https://a b.com",
                                 "https://user@instagram.com"])
def test_invalid_or_ambiguous_url(url):
    assert classify_digital_presence(url, "observed").presence_type == "unverified"


def test_fallback_and_contradictory_absence_are_unverified():
    assert classify_digital_presence("https://instagram.com", "unverified").presence_type == "unverified"
    assert classify_digital_presence("https://example.com", "not_found").presence_type == "unverified"


def test_determinism_nonmutation_and_no_commercial_effect():
    lead = adapt_record_to_qualification_input({"Empresa": "Exemplo", "Segmento": "Barbearia", "Site": "https://instagram.com/exemplo"})
    original = deepcopy(lead)
    before = evaluate_rules(lead)
    first = classify_digital_presence(lead.website, lead.observation_status("website"))
    second = classify_digital_presence(lead.website, lead.observation_status("website"))
    assert first == second
    assert lead == original
    assert evaluate_rules(lead) == before
    with pytest.raises(FrozenInstanceError):
        first.provider = "Changed"
