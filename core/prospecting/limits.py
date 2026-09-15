"""Internal budgets, not a promise of source coverage."""
from enum import Enum

DEFAULT_MAX_REQUESTS = 10  # preserve provider's existing budget
MAX_CANDIDATES_SCANNED = 200  # 10 pages of 20; independent protection


class ProspectingStopReason(str, Enum):
    TARGET_REACHED = "target_reached"
    SOURCE_EXHAUSTED = "source_exhausted"
    SAFETY_LIMIT_REACHED = "safety_limit_reached"
    CANCELLED = "cancelled"
    PROVIDER_ERROR = "provider_error"


STOP_MESSAGES = {
    ProspectingStopReason.TARGET_REACHED: "Meta atingida",
    ProspectingStopReason.SOURCE_EXHAUSTED: "Fim dos resultados disponíveis na API",
    ProspectingStopReason.SAFETY_LIMIT_REACHED: "Limite de segurança atingido; resultados parciais preservados.",
    ProspectingStopReason.CANCELLED: "Cancelado pelo usuário",
    ProspectingStopReason.PROVIDER_ERROR: "Falha na paginação; resultados parciais preservados.",
}
