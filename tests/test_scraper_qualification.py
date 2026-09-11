from copy import deepcopy
from unittest.mock import Mock

import pandas as pd
import pytest

from core import scraper
from core.qualification.service import qualify_records


@pytest.mark.parametrize("options", [{}, {"qualification_enabled": False}])
def test_default_and_explicit_disabled_preserve_contract(harness, monkeypatch, columns, options):
    qualify = Mock(side_effect=AssertionError("Must not qualify"))
    monkeypatch.setattr(scraper, "qualify_records", qualify)
    summary = harness.run(**options)
    qualify.assert_not_called()
    assert set(summary) == {"status", "leads", "processados", "total", "falhas",
                            "tempo_segundos", "arquivo", "erros"}
    assert list(pd.read_excel(harness.output).columns) == columns


def test_qualifies_after_dedup_preserving_order_and_association(harness, lead_factory, monkeypatch):
    first = lead_factory(Empresa="Primeira")
    duplicate = lead_factory(Empresa="Primeira", Telefone="ignorado")
    last = lead_factory(Empresa="Última", Site="https://example.test")
    harness.links.return_value = ["a", "b", "c"]
    harness.extract.side_effect = [first, duplicate, last]

    def evaluate(records):
        assert harness.extract.call_count == 3
        harness.browser.close.assert_called_once()
        assert records == [first, last]
        return qualify_records(records)

    qualify = Mock(side_effect=evaluate)
    monkeypatch.setattr(scraper, "qualify_records", qualify)
    summary = harness.run(qualification_enabled=True)
    qualify.assert_called_once()
    pairs = summary["qualificacoes"]
    assert len(pairs) == summary["leads"] == 2
    assert [p["registro"] for p in pairs] == [first, last]
    assert [p["resultado"].status for p in pairs] == ["insufficient_data", "qualified"]


def test_single_qualification_error_does_not_block_export_or_other_leads(harness, lead_factory):
    harness.links.return_value = ["a", "b", "c"]
    harness.extract.side_effect = [
        lead_factory(Empresa="A", Site="https://example.test"),
        lead_factory(Empresa="B", Telefone=123),
        lead_factory(Empresa="C"),
    ]
    summary = harness.run(qualification_enabled=True)
    assert [p["resultado"].status for p in summary["qualificacoes"]] == ["qualified", "error", "insufficient_data"]
    assert summary["leads"] == 3
    assert summary["falhas"] == 0
    assert len(pd.read_excel(harness.output)) == 3


def test_operational_fields_and_excel_unchanged_when_enabled(harness, lead_factory, columns):
    record = lead_factory(**{"Status Comercial": "Em análise", "Próxima Ação": "Revisar manualmente", "Potencial (1-5)": 3})
    original = deepcopy(record)
    harness.extract.side_effect = [record]
    summary = harness.run(qualification_enabled=True)
    assert record == original
    assert summary["qualificacoes"][0]["registro"] == original
    exported = pd.read_excel(harness.output, keep_default_na=False)
    assert list(exported.columns) == columns
    assert exported.to_dict("records") == [original]


def test_enabled_empty_batch_skips_service(harness, monkeypatch):
    harness.links.return_value = []
    qualify = Mock()
    monkeypatch.setattr(scraper, "qualify_records", qualify)
    summary = harness.run(qualification_enabled=True)
    assert summary["qualificacoes"] == []
    assert summary["arquivo"] is None
    qualify.assert_not_called()


def test_cancel_before_collection_keeps_empty_qualification(harness, monkeypatch):
    qualify = Mock()
    monkeypatch.setattr(scraper, "qualify_records", qualify)
    summary = harness.run(qualification_enabled=True, should_stop=lambda: True)
    assert summary["status"] == "cancelado"
    assert summary["qualificacoes"] == []
    qualify.assert_not_called()


def test_cancel_qualifies_and_exports_only_collected_leads(harness):
    harness.links.return_value = ["a", "b"]
    stop = False

    def progress(processed, total, message):
        nonlocal stop
        stop = processed >= 1

    summary = harness.run(qualification_enabled=True, on_progress=progress, should_stop=lambda: stop)
    assert summary["status"] == "cancelado"
    assert summary["total"] == 2
    assert len(summary["qualificacoes"]) == summary["leads"] == summary["processados"] == 1
    assert len(pd.read_excel(harness.output)) == 1
