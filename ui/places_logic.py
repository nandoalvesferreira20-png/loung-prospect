"""Presentation helpers without GUI or provider dependencies."""
from core.providers.search_query import normalize_neighborhood


def parse_search(city, segment, quantity, neighborhood=None):
    if not city.strip() or not segment.strip():
        raise ValueError(
            "Informe cidade e segmento."
        )

    try:
        limit = int(quantity)
    except (ValueError, TypeError):
        raise ValueError(
            "Quantidade deve ser um inteiro de 1 a 100."
        ) from None

    if not 1 <= limit <= 100:
        raise ValueError(
            "Quantidade deve ser um inteiro de 1 a 100."
        )

    return {
        "city": city.strip(),
        "segment": segment.strip(),
        "limit": limit,
        "neighborhood": normalize_neighborhood(neighborhood),
    }


def summary_text(summary):
    total_errors = (
        summary.qualification_errors
        + summary.persistence_errors
    )

    lines = [
        f"Encontrados: {summary.received}",
        f"Qualificados: {summary.qualified}",
        f"Dados insuficientes: {summary.insufficient_data}",
        "",
        "PRIORIDADE COMERCIAL",
        f"Alta: {summary.high_priority}",
        f"Boa: {summary.good_priority}",
        f"Média: {summary.medium_priority}",
        f"Baixa: {summary.low_priority}",
        "",
        "ANÁLISE",
        (
            "Oportunidade de website: "
            f"{summary.website_opportunities}"
        ),
        (
            "Revisão comercial: "
            f"{summary.needs_review}"
        ),
        "",
        "CARTEIRA",
        f"Inseridos: {summary.inserted}",
        f"Duplicados: {summary.duplicates}",
        f"Erros: {total_errors}",
        "",
        (
            f"Requests: {summary.requests_made} · "
            f"Duração: {summary.duration_seconds:.1f}s"
        ),
    ]

    if summary.cancelled:
        lines.extend([
            "",
            (
                "Cancelado; inserções anteriores "
                "foram preservadas."
            ),
        ])

    if summary.stats is not None:
        lines.extend(["", f"Meta: {summary.requested} · Aceitos: {summary.inserted}"])
        lines.extend([f"Candidatos analisados: {summary.candidates_scanned}",
                      f"Com site: {summary.rejected_with_website}",
                      f"Abaixo do score: {summary.rejected_score}",
                      f"Inválidos/inconclusivos: {summary.rejected_unverified}",
                      f"Páginas recebidas: {summary.pages_fetched}"])
        lines.append(summary.stop_reason or "")

    return "\n".join(lines)
