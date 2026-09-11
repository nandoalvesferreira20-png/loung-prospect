"""Pure, ordered spreadsheet values; no dependency on an Excel library."""

from .models import QualificationNote, QualificationResult


def _notes_to_text(notes: list[QualificationNote]) -> str:
    return " | ".join(f"{note.code}: {note.description}" for note in notes)


def qualification_result_to_columns(result: QualificationResult) -> dict[str, str | int | None]:
    """Preserve note order and timezone; missing scalars remain empty cells.

    Notes expose codes/descriptions, not their optional field/source metadata.
    Text is intended for reading, not as a reversible interchange format.
    """
    return {
        "Qualification Status": result.status.value,
        "Qualification Score": result.score,
        "Opportunity": result.opportunity,
        "Qualification Reasons": _notes_to_text(result.reasons),
        "Qualification Evidence": _notes_to_text(result.evidence),
        "Qualification Limitations": _notes_to_text(result.limitations),
        "Rules Version": result.rules_version,
        "Analyzed At": result.analyzed_at.isoformat() if result.analyzed_at else None,
    }
