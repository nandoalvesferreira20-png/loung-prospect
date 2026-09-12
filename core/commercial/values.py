"""Shared commercial options and validation, independent of UI and storage."""
from datetime import datetime, timezone

STATUSES = ("Novo", "Contato realizado", "Em conversa", "Reunião agendada",
            "Proposta enviada", "Fechado", "Não respondeu", "Retornar depois",
            "Sem interesse", "Perdido")
TERMINAL_STATUSES = frozenset(("Fechado", "Sem interesse", "Perdido"))
INTERACTION_TYPES = ("Primeiro contato", "Follow-up", "Ligação", "Mensagem",
                     "Reunião", "Proposta", "Observação", "Outro")
CHANNELS = ("whatsapp", "telefone", "instagram", "email", "outro")


def required_text(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Informe {label}.")
    return value


def utc_iso(value):
    """Accept aware datetimes/ISO strings or None; reject ambiguous dates."""
    if value is None:
        return None
    try:
        parsed = datetime.fromisoformat(value) if isinstance(value, str) else value
        if not isinstance(parsed, datetime) or parsed.utcoffset() is None:
            raise ValueError
        return parsed.astimezone(timezone.utc).isoformat()
    except (ValueError, TypeError):
        raise ValueError("Data deve incluir hora e fuso horário em ISO 8601.") from None


def commercial_values(values):
    """Copy and validate only supplied fields; legacy nonempty statuses are valid."""
    allowed = {"status", "responsavel", "observacoes", "proxima_acao",
               "proximo_contato", "ultimo_contato", "canal_preferencial"}
    if set(values) - allowed:
        raise ValueError("Campo comercial desconhecido.")
    result = dict(values)
    for name, value in result.items():
        if name in ("proximo_contato", "ultimo_contato"):
            result[name] = utc_iso(value)
        elif name == "status":
            required_text(value, "um status")
        elif value is not None and not isinstance(value, str):
            raise ValueError(f"{name} deve ser texto ou vazio.")
    if result.get("proxima_acao") and len(result["proxima_acao"]) > 240:
        raise ValueError("Próxima ação deve ter no máximo 240 caracteres.")
    return result
