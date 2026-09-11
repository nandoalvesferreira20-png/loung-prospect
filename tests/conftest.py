"""Synthetic inputs and fail-closed external integrations."""
import socket
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from playwright.sync_api import BrowserType, PlaywrightContextManager

from core import scraper


@pytest.fixture(autouse=True)
def forbid_external_io(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Network/browser access forbidden in characterization tests")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket.socket, "connect_ex", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(socket, "getaddrinfo", forbidden)
    monkeypatch.setattr(PlaywrightContextManager, "__enter__", forbidden)
    for method in ("launch", "launch_persistent_context", "connect", "connect_over_cdp"):
        monkeypatch.setattr(BrowserType, method, forbidden)


@pytest.fixture
def columns():
    return [
        "Empresa", "Cidade", "Segmento", "Telefone", "WhatsApp", "Site",
        "Endereço", "Avaliação", "Google Maps", "Status Comercial",
        "Próxima Ação", "Potencial (1-5)", "Observações",
    ]


@pytest.fixture
def lead_factory(columns):
    def make(**overrides):
        lead = dict.fromkeys(columns, "")
        lead.update({
            "Empresa": "Clínica Sintética", "Cidade": "Cidade Teste",
            "Segmento": "clínica", "Endereço": "Rua Fictícia, 1",
            "Google Maps": "https://maps.example.test/place/1",
            "Status Comercial": "Novo Lead", "Próxima Ação": "Qualificar lead",
        })
        lead.update(overrides)
        return lead
    return make


@pytest.fixture
def harness(monkeypatch, tmp_path, lead_factory):
    page = Mock()
    context = Mock()
    context.new_page.return_value = page
    browser = Mock()
    browser.new_context.return_value = context
    playwright = Mock()
    playwright.chromium.launch.return_value = browser
    manager = Mock()
    manager.__enter__ = Mock(return_value=playwright)
    manager.__exit__ = Mock(return_value=False)
    monkeypatch.setattr(scraper, "sync_playwright", Mock(return_value=manager))
    links = Mock(return_value=["https://maps.example.test/place/1"])
    extract = Mock(side_effect=lambda **kwargs: lead_factory())
    monkeypatch.setattr(scraper, "collect_links", links)
    monkeypatch.setattr(scraper, "extract_company_data", extract)
    monkeypatch.setattr(scraper, "time", SimpleNamespace(
        monotonic=Mock(side_effect=[100.0, 102.5]), sleep=Mock(),
    ))
    output = tmp_path / "exports" / "leads.xlsx"
    progress = Mock()

    def run(**overrides):
        args = dict(cidades=["Cidade Teste"], segmentos=["clínica"],
                    max_results=5, output=str(output), log=Mock(),
                    on_progress=progress)
        args.update(overrides)
        return scraper.run_scraper(**args)

    return SimpleNamespace(run=run, page=page, context=context, browser=browser,
                           playwright=playwright, links=links, extract=extract,
                           output=output, progress=progress)
