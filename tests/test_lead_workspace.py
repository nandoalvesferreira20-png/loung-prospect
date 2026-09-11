import sqlite3
from unittest.mock import Mock

import pytest

from core.database import LeadRepository
from ui import lead_workspace_logic as logic


@pytest.fixture
def workspace(tmp_path):
    return logic.LeadWorkspace(LeadRepository(tmp_path / "test.db"))


@pytest.mark.parametrize("text,expected", [("", None), ("0", 0), ("100", 100)])
def test_score(text, expected):
    assert logic.parse_min_score(text) == expected


@pytest.mark.parametrize("text", ["-1", "101", "1.5", "abc"])
def test_bad_score(text):
    with pytest.raises(ValueError):
        logic.parse_min_score(text)


@pytest.mark.parametrize("url,valid", [(None, False), ("javascript:alert(1)", False),
    ("file:///test", False), ("https://example.test", True), ("http://example.test/a", True),
    ("https://a b.com", False), ("https://example.com:bad", False), ("https://user@host.com", False)])
def test_urls(url, valid):
    assert logic.valid_url(url) is valid


def test_filters_counts_and_unknown_status(workspace):
    repo = workspace.repository
    a = repo.create_lead(dict(empresa="Clínica Árvore", cidade="São José", segmento="dentista", responsavel="Laís", qualification_score=70))
    repo.create_lead(dict(empresa="B", status="Legado", qualification_score=20))
    rows = workspace.list(segmento="dentista", responsavel="Laís", score="50", search="SÃO JOSÉ")
    assert [row["id"] for row in rows] == [a]
    assert len(workspace.list(status="Legado")) == 1
    assert logic.counts(repo.list_leads()) == dict(total=2, novos=1, contatados=0, responderam=0, reuniao=0)
    assert logic.list_values(rows[0]) == (70, "Clínica Árvore", "São José", "dentista", "", "Laís", "Novo")


def test_atomic_save_and_rollback(workspace):
    repo = workspace.repository
    identity = repo.create_lead({"empresa": "Empresa"})
    workspace.save(identity, "Status antigo", "José", "Revisar")
    before = dict(repo.get_lead(identity))
    assert (before["status"], before["responsavel"], before["observacoes"]) == ("Status antigo", "José", "Revisar")
    with pytest.raises(sqlite3.IntegrityError):
        repo.update_details(identity, status=None, responsavel="Changed", observacoes="Changed")
    assert dict(repo.get_lead(identity)) == before
    with pytest.raises(ValueError):
        workspace.save(identity, "", "", "")


def test_import_delegates_to_existing_importer(workspace, monkeypatch):
    importer = Mock(return_value="summary")
    monkeypatch.setattr(logic, "import_leads_from_excel", importer)
    assert workspace.import_file("example.xlsx") == "summary"
    importer.assert_called_once_with("example.xlsx", workspace.repository)


def test_link_opening_only_by_action(monkeypatch):
    from ui.lead_workspace import LeadWorkspacePage
    browser = Mock(return_value=True)
    monkeypatch.setattr("ui.lead_workspace.webbrowser.open", browser)
    page = Mock()
    LeadWorkspacePage.open_url(page, "javascript:alert(1)")
    browser.assert_not_called()
    LeadWorkspacePage.open_url(page, "https://example.test")
    browser.assert_called_once_with("https://example.test", new=2)
