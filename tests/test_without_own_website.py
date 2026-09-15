"""Central host classification and accepted-lead filter, entirely offline."""
from copy import deepcopy

import pandas as pd
import pytest

from core.lead_filter import is_without_own_website
from core.qualification.digital_presence import classify_digital_presence as classify
from core.prospecting.service import prospect
from core.database import LeadRepository
from test_places_target import place, provider


@pytest.mark.parametrize("host,kind", [
    *[(host, "social_media") for host in ("instagram.com", "www.instagram.com", "m.facebook.com", "facebook.com", "fb.com", "tiktok.com", "linkedin.com", "youtube.com", "x.com", "twitter.com", "threads.net")],
    *[(host, "third_party_platform") for host in ("linktr.ee", "beacons.ai", "bio.site", "restaurante.my.canva.site", "sites.google.com", "empresa.wixsite.com", "empresa.wordpress.com", "empresa.carrd.co", "ifood.com.br", "rappi.com.br", "tripadvisor.com.br", "restaurantguru.com")],
])
def test_supported_hosts(host, kind):
    url = f"https://{host.upper()}/perfil?q=site#contato"
    presence = classify(url, "observed")
    assert presence.presence_type == kind
    assert presence.url == url and is_without_own_website(presence)


@pytest.mark.parametrize("host", ["instagram.com.fake-domain.com", "facebook.com.example.org", "linktr.ee.example.com", "canva.site.example.net", "restaurante.com.br", "www.empresa.com"])
def test_independent_hosts_not_matched_by_substring(host):
    presence = classify(f"http://{host}/instagram.com?canva.site", "observed")
    assert presence.presence_type == "own_website"
    assert not is_without_own_website(presence)


@pytest.mark.parametrize("url,state,accepted", [(None, "not_found", True), (None, "unverified", False),
    (None, "error", False), ("https://instagram.com/a", "unverified", False),
    ("https://instagram.com/a", "error", False), ("not a URL", "observed", False),
    ("https://user@instagram.com/a", "observed", False), ("https://instagram.com:invalid/a", "observed", False)])
def test_conservative_observations(url, state, accepted):
    assert is_without_own_website(classify(url, state)) is accepted


def test_mixed_places_export_and_target(monkeypatch, tmp_path):
    urls = ["https://empresa.test"] * 35 + ["https://instagram.com/a"] * 8 + ["https://empresa.my.canva.site"] * 5 + [None] * 4 + ["invalid"] * 8
    records = [place(str(i), websiteUri=url, userRatingCount=120) for i, url in enumerate(urls)]
    original = deepcopy(records)
    pages = [{"places": records[i:i+20], **({"nextPageToken": str(i)} if i < 40 else {})} for i in range(0, 60, 20)]
    api, _ = provider(monkeypatch, pages)
    path = tmp_path / "leads.xlsx"
    summary = prospect(city="Campinas", segment="dentista", limit=30, only_without_website=True,
        provider=api, repository=LeadRepository(tmp_path / "test.db"), export_path=path)
    assert summary.accepted == 17 and summary.rejected_with_website == 35
    assert summary.rejected_unverified == 8
    frame = pd.read_excel(path)
    assert sum(frame["Status Site"] == "Sem site próprio — Instagram") == 8
    assert sum(frame["Status Site"] == "Sem site próprio — Canva Sites") == 5
    assert sum(frame["Status Site"] == "SEM_SITE_NO_GOOGLE") == 4
    assert frame.iloc[0]["Site"] == "https://instagram.com/a"
    assert not frame["Possui Site"].any()
    assert records == original


def test_social_still_requires_minimum_score(monkeypatch, tmp_path):
    api, _ = provider(monkeypatch, [{"places": [place("Social", websiteUri="https://instagram.com/a")]}])
    summary = prospect(city="A", segment="B", only_without_website=True, min_score=100,
        provider=api, repository=LeadRepository(tmp_path / "test.db"))
    assert summary.accepted == 0 and summary.rejected_score == 1
