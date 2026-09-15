"""Pure query context normalization; no inferred lead address data."""


def normalize_neighborhood(value=None):
    if value is not None and not isinstance(value, str):
        raise ValueError("Bairro deve ser texto ou vazio.")
    return value.strip() or None if value is not None else None
