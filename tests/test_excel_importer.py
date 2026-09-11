from openpyxl import Workbook
import pytest

from core.database import LeadRepository
from core.importers.excel_leads import import_leads_from_excel


@pytest.fixture
def env(tmp_path):
    repo = LeadRepository(tmp_path / "test.db")
    def write(rows):
        path = tmp_path / "leads.xlsx"
        workbook = Workbook()
        for row in rows:
            workbook.active.append(row)
        workbook.save(path)
        workbook.close()
        return path
    return repo, write


def test_complete_mapping(env):
    repo, write = env
    path = write([["Empresa", "Segmento", "Qualification Status", "Qualification Score", "Opportunity",
                   "Qualification Reasons", "Qualification Evidence", "Qualification Limitations", "Rules Version",
                   "Analyzed At", "Email", "Responsável", "Status Comercial", "Observações", "Próxima Ação", "Extra"],
                  ["Clínica D'Ávila", "dentista", "qualified", 70, "website", "reason", "evidence", "limit", "2.0.0",
                   "2026-01-01T00:00:00+00:00", "a@example.test", "José", "Em revisão", "Notas", "NÃO STATUS", "ignore"]])
    summary = import_leads_from_excel(path, repo, default_responsible="Outro")
    assert summary.imported == summary.total_rows == 1
    row = repo.list_leads()[0]
    for key, expected in dict(empresa="Clínica D'Ávila", segmento="dentista", qualification_status="qualified",
                              qualification_score=70, opportunity="website", qualification_reasons="reason",
                              qualification_evidence="evidence", qualification_limitations="limit", rules_version="2.0.0",
                              analyzed_at="2026-01-01T00:00:00+00:00", email="a@example.test", responsavel="José",
                              status="Em revisão", observacoes="Notas").items():
        assert row[key] == expected


@pytest.mark.parametrize("rows,error", [([], False), ([["Cidade"], ["Santos"]], True), ([[None], ["Empresa"]], True)])
def test_empty_and_headers(env, rows, error):
    repo, write = env
    summary = import_leads_from_excel(write(rows), repo)
    assert bool(summary.errors) is error
    assert repo.count_leads() == 0


@pytest.mark.parametrize("score", [0, 100, 70, "50", None])
def test_score_values_and_missing_qualification(env, score):
    repo, write = env
    summary = import_leads_from_excel(write([["Empresa", "Qualification Score"], ["Empresa", score]]), repo)
    assert summary.imported == 1
    row = repo.list_leads()[0]
    assert row["qualification_score"] == (int(score) if score is not None else None)
    assert row["email"] is row["qualification_status"] is row["analyzed_at"] is None
    assert row["status"] == "Novo"


@pytest.mark.parametrize("score", [-1, 101, "bad", 2.5, True])
def test_invalid_rows_isolated(env, score):
    repo, write = env
    summary = import_leads_from_excel(write([["Empresa", "Qualification Score"], ["Bad", score], [None, 50], ["Good", 60]]), repo)
    assert (summary.total_rows, summary.imported, summary.skipped_invalid) == (3, 1, 2)
    assert [issue.row for issue in summary.errors] == [2, 3]


@pytest.mark.parametrize("column", ["Responsavel", "Responsável"])
def test_responsible_fallback(env, column):
    repo, write = env
    import_leads_from_excel(write([["Empresa", column], ["A", "Ana"], ["B", None]]), repo, default_responsible="José")
    assert [r["responsavel"] for r in repo.list_leads()] == ["Ana", "José"]


@pytest.mark.parametrize("column,one,two", [("Google Maps", "https://maps.example.test/1", "https://maps.example.test/1"),
    ("Endereço", " Rua  A ", "rua a"), ("Telefone", "(11) 3333-4444", "1133334444")])
def test_dedupe_in_file_and_database(env, column, one, two):
    repo, write = env
    path = write([["Empresa", column], [" Empresa ", one], ["empresa", two]])
    first = import_leads_from_excel(path, repo)
    assert (first.imported, first.skipped_duplicates) == (1, 1)
    second = import_leads_from_excel(path, repo)
    assert (second.imported, second.skipped_duplicates) == (0, 2)
    assert repo.list_leads()[0]["empresa"] == " Empresa "


def test_name_only_not_deduplicated(env):
    repo, write = env
    summary = import_leads_from_excel(write([["Empresa"], ["Same"], ["Same"]]), repo)
    assert summary.imported == 2
    assert repo.list_leads()[0]["responsavel"] is None


def test_formula_not_executed(env):
    repo, write = env
    summary = import_leads_from_excel(write([["Empresa", "Qualification Score"], ["=1+1", 10], ["Safe", "=50+20"]]), repo)
    assert summary.skipped_invalid == 1
    assert repo.list_leads()[0]["qualification_score"] is None


def test_database_error_isolated(env, monkeypatch):
    repo, write = env
    original = repo.create_lead
    def insert(data):
        if data["empresa"] == "Bad":
            raise RuntimeError("Synthetic failure")
        return original(data)
    monkeypatch.setattr(repo, "create_lead", insert)
    summary = import_leads_from_excel(write([["Empresa"], ["Bad"], ["Good"]]), repo)
    assert summary.imported == summary.skipped_invalid == 1
    assert summary.errors[0].code == "write_error"
