"""Per-record orchestration only; no persistence or commercial actions."""

from collections.abc import Iterable, Mapping
from dataclasses import replace
from datetime import datetime, timezone
from typing import Any

from .adapter import adapt_record_to_qualification_input
from .models import QualificationNote, QualificationResult, QualificationStatus
from .rules import evaluate_rules


def qualify_record(record: Mapping[str, Any]) -> QualificationResult:
    """Adapt and evaluate one record, reporting isolated failures without tracebacks.

    Error notes identify the stage and exception type, not arbitrary exception
    messages which may contain raw record data. No rule version is claimed when
    evaluation fails to produce a result.
    """
    stage = "adapter"
    try:
        lead = adapt_record_to_qualification_input(record)
        stage = "rules"
        result = evaluate_rules(lead)
    except Exception as error:
        result = QualificationResult(
            status=QualificationStatus.ERROR,
            limitations=[QualificationNote(
                code=f"{stage}_error",
                description=f"Falha na etapa {stage} ({type(error).__name__}); registro não qualificado.",
            )],
        )
    return replace(result, analyzed_at=datetime.now(timezone.utc))


def qualify_records(records: Iterable[Mapping[str, Any]]) -> list[QualificationResult]:
    """Preserve input order, isolating adaptation/evaluation failures per item.

    Errors raised by the iterable itself propagate: unavailable items cannot be
    qualified. Results are associated with input records by their list position.
    """
    return [qualify_record(record) for record in records]
