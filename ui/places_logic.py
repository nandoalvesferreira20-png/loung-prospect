"""Presentation helpers without GUI or provider dependencies."""


def parse_search(city, segment, quantity):
    if not city.strip() or not segment.strip():
        raise ValueError("Informe cidade e segmento.")
    try:
        limit = int(quantity)
    except (ValueError, TypeError):
        raise ValueError("Quantidade deve ser um inteiro de 1 a 100.") from None
    if not 1 <= limit <= 100:
        raise ValueError("Quantidade deve ser um inteiro de 1 a 100.")
    return dict(city=city.strip(), segment=segment.strip(), limit=limit)


def summary_text(summary):
    return (f"Encontrados: {summary.received}\nQualificados: {summary.qualified}\n"
            f"Dados insuficientes: {summary.insufficient_data}\n"
            f"Oportunidades website: {summary.website_opportunities}\n"
            f"Inseridos na carteira: {summary.inserted}\nDuplicados: {summary.duplicates}\n"
            f"Erros: {summary.qualification_errors + summary.persistence_errors}\n"
            f"Requests: {summary.requests_made} · Duração: {summary.duration_seconds:.1f}s"
            + ("\nCancelado; inserções anteriores foram preservadas." if summary.cancelled else ""))
