from contextlib import closing
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timezone
from threading import Event
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock
import json
import sqlite3

import pytest

from core.database import (
    LeadRepository,
    connect_database,
    initialize_database,
)
from core.providers.models import LeadCandidate
from core.providers.google_places import (
    GooglePlacesProvider,
    GooglePlacesHTTPError,
)
from core.prospecting.adapter import (
    candidate_to_record,
    record_to_database,
)
from core.prospecting import service
from core.qualification.adapter import (
    adapt_record_to_qualification_input,
)
from core.qualification.models import (
    QualificationResult,
    QualificationNote,
)
from core.qualification.rules import RULES_VERSION
from ui.places_logic import (
    parse_search,
    summary_text,
)


@pytest.fixture
def candidate():
    return LeadCandidate(
        provider="google_places",
        provider_place_id="place-1",
        empresa="Clínica Árvore",
        cidade="Taubaté",
        segmento="dentista",
        telefone="123",
        site="https://example.test",
        endereco="Rua A",
        avaliacao=4.5,
        quantidade_avaliacoes=120,
        google_maps="https://maps.example.test/1",
    )


@pytest.fixture
def repo(tmp_path):
    return LeadRepository(
        tmp_path / "test.db"
    )


def provider_for(candidates):
    return Mock(
        search=Mock(
            return_value=candidates
        ),
        request_count=1,
    )


@pytest.mark.parametrize(
    "website,expected",
    [
        (
            "https://example.test",
            "observed",
        ),
        (
            None,
            "unverified",
        ),
        (
            "",
            "unverified",
        ),
    ],
)
def test_adapter_website_and_nonmutation(
    candidate,
    website,
    expected,
):
    candidate = replace(
        candidate,
        site=website,
    )

    before = deepcopy(candidate)

    record = candidate_to_record(
        candidate
    )

    lead = adapt_record_to_qualification_input(
        record
    )

    assert (
        lead.observation_status(
            "website"
        ).value
        == expected
    )

    assert lead.phone == "123"
    assert lead.whatsapp is None

    assert lead.rating == "4.5"
    assert lead.user_rating_count == "120"

    assert (
        lead.observation_status(
            "rating"
        ).value
        == "observed"
    )

    assert (
        lead.observation_status(
            "user_rating_count"
        ).value
        == "observed"
    )

    assert (
        lead.company_name
        == candidate.empresa
    )

    assert (
        lead.city
        == candidate.cidade
    )

    assert (
        record["provider_place_id"]
        == "place-1"
    )

    assert (
        record["Quantidade Avaliações"]
        == "120"
    )

    assert (
        "_website_verification"
        not in record
    )

    assert candidate == before


def test_database_mapping(candidate):
    result = QualificationResult(
        status="qualified",
        score=80,
        opportunity="website",
        reasons=[
            QualificationNote(
                "reason",
                "Descrição",
            )
        ],
        evidence=[
            QualificationNote(
                "evidence",
                "Fonte",
            )
        ],
        limitations=[
            QualificationNote(
                "limit",
                "Limitação",
            )
        ],
        rules_version=RULES_VERSION,
        analyzed_at=datetime(
            2026,
            1,
            1,
            tzinfo=timezone.utc,
        ),
    )

    record = candidate_to_record(
        candidate
    )

    before = deepcopy(
        (record, result)
    )

    data = record_to_database(
        record,
        result,
    )

    assert (
        data["qualification_score"]
        == 80
    )

    assert (
        data["qualification_status"]
        == "qualified"
    )

    assert (
        data["qualification_reasons"]
        == "reason: Descrição"
    )

    assert (
        data["qualification_evidence"]
        == "evidence: Fonte"
    )

    assert (
        data[
            "qualification_limitations"
        ]
        == "limit: Limitação"
    )

    assert (
        data["analyzed_at"]
        .endswith("+00:00")
    )

    assert (
        data["rules_version"]
        == RULES_VERSION
    )

    assert (
        data["provider"]
        == "google_places"
    )

    assert (
        data["provider_place_id"]
        == "place-1"
    )

    assert (
        data["quantidade_avaliacoes"]
        == "120"
    )

    assert "status" not in data
    assert "responsavel" not in data

    assert (
        record,
        result,
    ) == before


def test_real_qualification_and_persistence(
    candidate,
    repo,
):
    provider = provider_for(
        [candidate]
    )

    summary = service.prospect(
        city="Taubaté",
        segment="dentista",
        limit=5,
        provider=provider,
        repository=repo,
    )

    row = repo.list_leads()[0]

    assert (
        row["rules_version"]
        == RULES_VERSION
    )

    assert (
        row["status"]
        == "Novo"
    )

    assert (
        row["provider_place_id"]
        == "place-1"
    )

    assert row["whatsapp"] is None

    assert (
        row["quantidade_avaliacoes"]
        == 120
    )

    # Site próprio 5
    # telefone 20
    # rating >= 4 10
    # 100+ avaliações 20
    # endereço 5
    assert (
        row["qualification_score"]
        == 60
    )

    assert (
        row["opportunity"]
        == "needs_review"
    )

    assert (
        summary.received
        == summary.inserted
        == summary.requests_made
        == 1
    )

    assert (
        summary.qualified
        + summary.insufficient_data
        == 1
    )

    assert (
        summary.good_priority
        == 1
    )

    assert (
        summary.needs_review
        == 1
    )

    assert (
        summary.duration_seconds
        >= 0
    )

    provider.search.assert_called_once_with(
        city="Taubaté",
        segment="dentista",
        max_results=5,
    )


@pytest.mark.parametrize(
    "identity",
    [
        dict(
            provider="google_places",
            provider_place_id="id",
        ),
        dict(
            google_maps=(
                "https://maps.example.test"
            )
        ),
        dict(
            empresa="D'Ávila",
            endereco="Rua A",
        ),
        dict(
            empresa="D'Ávila",
            telefone="123",
        ),
    ],
)
def test_dedupe_criteria_preserve_existing(
    repo,
    identity,
):
    data = {
        "empresa": "A",
        **identity,
    }

    lead_id = repo.create_lead(
        {
            **data,
            "status": "Em contato",
            "observacoes": "Preservar",
        }
    )

    before = dict(
        repo.get_lead(
            lead_id
        )
    )

    assert (
        repo.create_lead_if_new(
            data
        )
        is None
    )

    assert dict(
        repo.get_lead(
            lead_id
        )
    ) == before


def test_name_only_is_not_duplicate(repo):
    data = {
        "empresa": "A",
        "telefone": "",
        "endereco": None,
    }

    assert (
        repo.create_lead_if_new(
            data
        )
        is not None
    )

    assert (
        repo.create_lead_if_new(
            data
        )
        is not None
    )


def test_atomic_duplicate_insertion(repo):
    data = dict(
        empresa="A",
        provider="google_places",
        provider_place_id="same",
    )

    with ThreadPoolExecutor(
        max_workers=2
    ) as pool:
        ids = list(
            pool.map(
                lambda _: (
                    repo.create_lead_if_new(
                        data
                    )
                ),
                range(2),
            )
        )

    assert (
        ids.count(None)
        == 1
    )

    assert (
        repo.count_leads()
        == 1
    )


def test_duplicate_within_and_across_search(
    candidate,
    repo,
):
    result = service.prospect(
        city="C",
        segment="S",
        provider=provider_for(
            [
                candidate,
                candidate,
            ]
        ),
        repository=repo,
    )

    assert (
        result.inserted
        == result.duplicates
        == 1
    )

    again = service.prospect(
        city="C",
        segment="S",
        provider=provider_for(
            [candidate]
        ),
        repository=repo,
    )

    assert (
        again.inserted
        == 0
    )

    assert (
        again.duplicates
        == 1
    )


def test_isolated_failures_and_summary(
    candidate,
    repo,
    monkeypatch,
):
    candidates = [
        replace(
            candidate,
            provider_place_id=str(i),
            empresa=str(i),
            google_maps=None,
        )
        for i in range(4)
    ]

    monkeypatch.setattr(
        service,
        "qualify_record",
        Mock(
            side_effect=[
                RuntimeError("SECRET"),
                QualificationResult(
                    status="qualified",
                    score=80,
                    opportunity="website",
                ),
                QualificationResult(
                    status="insufficient_data",
                    score=35,
                    opportunity="needs_review",
                ),
                QualificationResult(
                    status="error",
                ),
            ]
        ),
    )

    insert = Mock(
        side_effect=[
            RuntimeError("SECRET"),
            1,
            None,
            99,
        ]
    )

    monkeypatch.setattr(
        repo,
        "create_lead_if_new",
        insert,
    )

    log = Mock()
    progress = Mock()

    summary = service.prospect(
        city="C",
        segment="S",
        provider=provider_for(
            candidates
        ),
        repository=repo,
        log=log,
        progress=progress,
    )

    assert (
        summary.received,
        summary.qualified,
        summary.insufficient_data,
        summary.qualification_errors,
    ) == (
        4,
        1,
        1,
        2,
    )

    assert (
        summary.website_opportunities
        == 1
    )

    assert (
        summary.needs_review
        == 1
    )

    assert (
        summary.high_priority
        == 1
    )

    assert (
        summary.medium_priority
        == 1
    )

    assert (
        summary.inserted,
        summary.duplicates,
        summary.persistence_errors,
    ) == (
        2,
        1,
        1,
    )

    assert (
        insert
        .call_args_list[0]
        .args[0][
            "qualification_status"
        ]
        == "error"
    )

    assert (
        progress.call_count
        == 4
    )

    assert (
        "SECRET"
        not in (
            repr(summary)
            + repr(log.call_args_list)
        )
    )


def test_error_qualification_still_saved(
    candidate,
    repo,
    monkeypatch,
):
    monkeypatch.setattr(
        service,
        "qualify_record",
        Mock(
            side_effect=RuntimeError(
                "SECRET"
            )
        ),
    )

    result = service.prospect(
        city="C",
        segment="S",
        provider=provider_for(
            [candidate]
        ),
        repository=repo,
    )

    assert (
        result.inserted
        == result.qualification_errors
        == 1
    )

    assert (
        repo.list_leads()[0][
            "qualification_status"
        ]
        == "error"
    )


def test_zero_results_does_not_open_database(
    monkeypatch,
):
    constructor = Mock()

    monkeypatch.setattr(
        service,
        "LeadRepository",
        constructor,
    )

    summary = service.prospect(
        city="C",
        segment="S",
        provider=provider_for([]),
    )

    assert (
        summary.received
        == summary.inserted
        == 0
    )

    assert (
        summary.requests_made
        == 1
    )

    constructor.assert_not_called()


def test_api_error_sanitized(repo):
    provider = provider_for([])

    provider.search.side_effect = (
        GooglePlacesHTTPError(
            400,
            api_message="SECRET",
        )
    )

    with pytest.raises(
        service.ProspectingError
    ) as error:
        service.prospect(
            city="C",
            segment="S",
            provider=provider,
            repository=repo,
        )

    assert (
        "HTTP 400"
        in str(error.value)
    )

    assert (
        "SECRET"
        not in str(error.value)
    )

    assert (
        error.value.summary.requests_made
        == 1
    )

    assert (
        repo.count_leads()
        == 0
    )

    assert (
        error.value.__cause__
        is None
    )


def test_missing_key_no_database(
    monkeypatch,
):
    monkeypatch.setattr(
        service,
        "load_environment",
        Mock(),
    )

    monkeypatch.delenv(
        "GOOGLE_PLACES_API_KEY",
        raising=False,
    )

    constructor = Mock()

    monkeypatch.setattr(
        service,
        "LeadRepository",
        constructor,
    )

    with pytest.raises(
        service.ProspectingError,
        match="Chave ausente",
    ) as error:
        service.prospect(
            city="C",
            segment="S",
        )

    assert (
        error.value.summary.requests_made
        == 0
    )

    constructor.assert_not_called()


def test_cancel_between_leads(
    candidate,
    repo,
):
    event = Event()

    summary = service.prospect(
        city="C",
        segment="S",
        provider=provider_for(
            [
                candidate,
                candidate,
            ]
        ),
        repository=repo,
        cancel_event=event,
        progress=lambda *_: (
            event.set()
        ),
    )

    assert summary.cancelled

    assert (
        summary.inserted
        == 1
    )

    assert (
        summary.duplicates
        == 0
    )


def test_cancel_before_search():
    event = Event()
    event.set()

    provider = provider_for([])

    assert service.prospect(
        city="C",
        segment="S",
        provider=provider,
        cancel_event=event,
    ).cancelled

    provider.search.assert_not_called()


def test_old_schema_migration_preserves_data(
    tmp_path,
):
    path = tmp_path / "old.db"

    # Real legacy schema:
    # intentionally excludes provider,
    # provider_place_id and quantidade_avaliacoes.
    legacy_schema = """
    CREATE TABLE leads (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        empresa TEXT NOT NULL,
        cidade TEXT,
        segmento TEXT,
        telefone TEXT,
        whatsapp TEXT,
        email TEXT,
        site TEXT,
        endereco TEXT,
        avaliacao TEXT,
        google_maps TEXT,
        qualification_status TEXT,
        qualification_score INTEGER,
        opportunity TEXT,
        qualification_reasons TEXT,
        qualification_evidence TEXT,
        qualification_limitations TEXT,
        rules_version TEXT,
        analyzed_at TEXT,
        responsavel TEXT,
        status TEXT NOT NULL DEFAULT 'Novo',
        observacoes TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """

    with closing(
        connect_database(path)
    ) as connection:
        with connection:
            connection.execute(
                legacy_schema
            )

            connection.execute(
                """
                INSERT INTO leads (
                    empresa,
                    created_at,
                    updated_at
                )
                VALUES (
                    'Antiga',
                    'old',
                    'old'
                )
                """
            )

    initialize_database(path)
    initialize_database(path)

    repo = LeadRepository(path)

    row = repo.list_leads()[0]

    assert (
        row["empresa"]
        == "Antiga"
    )

    assert (
        row["created_at"]
        == "old"
    )

    assert (
        row["provider"]
        is None
    )

    assert (
        row["provider_place_id"]
        is None
    )

    assert (
        row["quantidade_avaliacoes"]
        is None
    )

    assert (
        repo.count_leads()
        == 1
    )


def test_insert_rollback(repo):
    with pytest.raises(
        sqlite3.IntegrityError
    ):
        repo.create_lead_if_new(
            {
                "empresa": None,
            }
        )

    assert (
        repo.count_leads()
        == 0
    )

    assert repo.create_lead_if_new(
        {
            "empresa": "Após falha",
        }
    )


@pytest.mark.parametrize(
    "city,segment,quantity",
    [
        ("", "S", "5"),
        ("C", "", "5"),
        ("C", "S", "0"),
        ("C", "S", "101"),
        ("C", "S", "1.5"),
        ("C", "S", "abc"),
    ],
)
def test_ui_validation(
    city,
    segment,
    quantity,
):
    with pytest.raises(
        ValueError
    ):
        parse_search(
            city,
            segment,
            quantity,
        )


def test_ui_presentation():
    summary = service.ProspectingSummary(
        requested=5,
        received=5,
        qualified=2,
        insufficient_data=2,

        high_priority=1,
        good_priority=1,
        medium_priority=1,
        low_priority=1,

        website_opportunities=1,
        needs_review=2,

        inserted=3,
        duplicates=1,

        qualification_errors=1,
        persistence_errors=1,

        requests_made=2,
        duration_seconds=1.25,
    )

    text = summary_text(
        summary
    )

    assert (
        "Encontrados: 5"
        in text
    )

    assert (
        "Qualificados: 2"
        in text
    )

    assert (
        "Dados insuficientes: 2"
        in text
    )

    assert (
        "PRIORIDADE COMERCIAL"
        in text
    )

    assert (
        "🔥 Alta: 1"
        in text
    )

    assert (
        "✓ Boa: 1"
        in text
    )

    assert (
        "• Média: 1"
        in text
    )

    assert (
        "○ Baixa: 1"
        in text
    )

    assert (
        "ANÁLISE"
        in text
    )

    assert (
        "Oportunidade de website: 1"
        in text
    )

    assert (
        "Revisão comercial: 2"
        in text
    )

    assert (
        "CARTEIRA"
        in text
    )

    assert (
        "Inseridos: 3"
        in text
    )

    assert (
        "Duplicados: 1"
        in text
    )

    assert (
        "Erros: 2"
        in text
    )

    assert (
        "Requests: 2"
        in text
    )

    assert (
        "Duração: 1.2s"
        in text
        or
        "Duração: 1.3s"
        in text
    )


def test_provider_to_database_offline(
    repo,
    monkeypatch,
):
    monkeypatch.setenv(
        "GOOGLE_PLACES_API_KEY",
        "synthetic-secret",
    )

    transport = Mock(
        return_value=(
            200,
            json.dumps(
                {
                    "places": [
                        {
                            "id": "id",
                            "displayName": {
                                "text": "Empresa"
                            },
                            "rating": 4.8,
                            "userRatingCount": 150,
                            "googleMapsLinks": {
                                "placeUri": (
                                    "https://maps.example.test"
                                )
                            },
                        }
                    ]
                }
            ).encode(),
        )
    )

    summary = service.prospect(
        city="C",
        segment="S",
        provider=GooglePlacesProvider(
            transport=transport
        ),
        repository=repo,
    )

    row = repo.list_leads()[0]

    assert (
        summary.inserted
        == 1
    )

    assert (
        summary.requests_made
        == 1
    )

    assert (
        row["provider_place_id"]
        == "id"
    )

    assert (
        row["site"]
        is None
    )

    assert (
        row["avaliacao"]
        == "4.8"
    )

    assert (
        row["quantidade_avaliacoes"]
        == 150
    )

    assert (
        "website_unverified"
        in row[
            "qualification_limitations"
        ]
    )

    assert (
        "synthetic-secret"
        not in repr(
            dict(row)
        )
    )


def test_persistence_failure_does_not_block_next(
    candidate,
    repo,
    monkeypatch,
):
    insert = (
        repo.create_lead_if_new
    )

    calls = 0

    def fail_first(data):
        nonlocal calls

        calls += 1

        if calls == 1:
            raise sqlite3.OperationalError(
                "private"
            )

        return insert(data)

    monkeypatch.setattr(
        repo,
        "create_lead_if_new",
        fail_first,
    )

    summary = service.prospect(
        city="C",
        segment="S",
        provider=provider_for(
            [
                candidate,
                candidate,
            ]
        ),
        repository=repo,
    )

    assert (
        summary.persistence_errors
        == 1
    )

    assert (
        summary.inserted
        == 1
    )

    assert (
        repo.count_leads()
        == 1
    )