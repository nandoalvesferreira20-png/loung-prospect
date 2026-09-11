import pandas as pd
import pytest


def test_summary_success_and_exported_schema(harness, columns):
    summary = harness.run()
    assert summary == {
        "status": "concluído", "leads": 1, "processados": 1, "total": 1,
        "falhas": 0, "tempo_segundos": 2.5,
        "arquivo": str(harness.output.resolve()), "erros": [],
    }
    assert list(pd.read_excel(harness.output).columns) == columns
    assert harness.progress.call_args.args[:2] == (1, 1)
    harness.context.close.assert_called_once()
    harness.browser.close.assert_called_once()


def test_duplicate_links_keep_first_search_context(harness):
    harness.links.return_value *= 2
    summary = harness.run(cidades=["Cidade A", "Cidade B"])
    assert summary["total"] == summary["processados"] == 1
    harness.extract.assert_called_once_with(page=harness.page, cidade="Cidade A", segmento="clínica", verify_website=True)


@pytest.mark.parametrize("address", ["Rua Fictícia, 1", ""])
def test_known_dedup_by_name_address_keeps_first_even_empty_address(harness, lead_factory, address):
    harness.links.return_value = ["https://maps.example.test/1", "https://maps.example.test/2"]
    harness.extract.side_effect = [
        lead_factory(**{"Endereço": address, "Telefone": "primeiro"}),
        lead_factory(**{"Endereço": address, "Telefone": "segundo"}),
    ]
    summary = harness.run()
    assert summary["processados"] == 2
    assert summary["leads"] == 1
    assert pd.read_excel(harness.output).iloc[0]["Telefone"] == "primeiro"


def test_same_name_different_addresses_are_preserved(harness, lead_factory):
    harness.links.return_value = ["https://maps.example.test/1", "https://maps.example.test/2"]
    harness.extract.side_effect = [lead_factory(), lead_factory(**{"Endereço": "Rua Fictícia, 2"})]
    assert harness.run()["leads"] == 2


@pytest.mark.parametrize("failure", [RuntimeError("Synthetic lead failure"), "empty_name"])
def test_failed_lead_does_not_prevent_next_lead(harness, lead_factory, failure):
    harness.links.return_value = ["https://maps.example.test/1", "https://maps.example.test/2"]
    first = lead_factory(Empresa=" ") if failure == "empty_name" else failure
    harness.extract.side_effect = [first, lead_factory()]
    summary = harness.run()
    assert summary["processados"] == summary["total"] == 2
    assert summary["leads"] == summary["falhas"] == 1
    assert summary["erros"][0]["etapa"] == ("extração" if failure == "empty_name" else "processamento")
    assert len(pd.read_excel(harness.output)) == 1


def test_empty_search_does_not_create_excel(harness):
    harness.links.return_value = []
    summary = harness.run()
    assert summary["status"] == "concluído"
    assert summary["leads"] == summary["processados"] == summary["total"] == 0
    assert summary["arquivo"] is None
    assert not harness.output.exists()


def test_cancel_before_search(harness):
    summary = harness.run(should_stop=lambda: True)
    assert summary["status"] == "cancelado"
    assert summary["processados"] == summary["total"] == 0
    assert summary["arquivo"] is None
    harness.links.assert_not_called()
    harness.extract.assert_not_called()
    harness.context.close.assert_called_once()
    harness.browser.close.assert_called_once()


def test_cancel_after_first_lead_exports_partial_results(harness):
    harness.links.return_value = ["https://maps.example.test/1", "https://maps.example.test/2"]
    stopped = False

    def progress(processed, total, message):
        nonlocal stopped
        if processed == 1:
            stopped = True

    summary = harness.run(should_stop=lambda: stopped, on_progress=progress)
    assert summary["status"] == "cancelado"
    assert summary["processados"] == summary["leads"] == 1
    assert summary["total"] == 2
    assert len(pd.read_excel(harness.output)) == 1
    harness.extract.assert_called_once()


def test_search_failure_does_not_prevent_next_search(harness):
    harness.links.side_effect = [RuntimeError("Synthetic search failure"), ["https://maps.example.test/2"]]
    summary = harness.run(cidades=["Cidade A", "Cidade B"])
    assert summary["leads"] == 1
    assert summary["falhas"] == 1
    assert summary["erros"][0]["etapa"] == "busca"


def test_known_browser_failure_still_returns_concluded(harness):
    harness.playwright.chromium.launch.side_effect = RuntimeError("Synthetic browser failure")
    summary = harness.run()
    assert summary["status"] == "concluído"
    assert summary["falhas"] == 1
    assert summary["erros"] == [{"etapa": "navegador", "erro": "Synthetic browser failure"}]
    assert summary["arquivo"] is None
    assert not harness.output.exists()
