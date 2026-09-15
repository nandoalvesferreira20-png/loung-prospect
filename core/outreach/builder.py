"""Pure local generation: no repository, transport, or interaction recording."""
from typing import Any, Mapping

from .models import OutreachContext, OutreachRequest, OutreachResult
from .templates import GREETINGS, FIRST_CONTACT, CONTINUATIONS, SUBJECTS, CLOSINGS, normalize_segment, template_id

DEFAULT_SENDER = "Fernando"
MESSAGE_LIMITS = {"whatsapp": 450, "instagram": 350}


def text(value):
    return " ".join(str(value).split()) if value is not None else ""


def sender_name(responsible, fallback=DEFAULT_SENDER):
    name = text(responsible)
    if name.lower() in {"", "não disponível", "não atribuído", "sem responsável", "nenhum", "-", "—"} or not any(c.isalpha() for c in name):
        return text(fallback) or DEFAULT_SENDER
    return name


def context_from_lead(lead: Mapping[str, Any]) -> OutreachContext:
    row = dict(lead)  # also accepts sqlite3.Row without retaining mutable input
    mapping = {"company_name": "empresa", "segment": "segmento", "city": "cidade", "website": "site",
               "phone": "telefone", "whatsapp": "whatsapp", "rating": "avaliacao", "review_count": "quantidade_avaliacoes",
               "qualification_score": "qualification_score", "priority": "priority", "opportunity": "opportunity", "responsible": "responsavel"}
    return OutreachContext(**{field: row.get(column) for field, column in mapping.items()})


def length_warnings(message, channel):
    limit = MESSAGE_LIMITS.get(channel)
    return (f"Texto com {len(message)} caracteres; recomendado até {limit}. Revise antes de copiar.",) if limit and len(message) > limit else ()


class TemplateOutreachGenerator:
    def __init__(self, fallback_sender=DEFAULT_SENDER):
        self.fallback_sender = fallback_sender

    def generate(self, request: OutreachRequest) -> OutreachResult:
        context = request.context
        sender = sender_name(context.responsible, self.fallback_sender)
        company = text(context.company_name)
        segment = normalize_segment(context.segment)
        intro = f"{GREETINGS[request.tone]} Sou {sender}, da Loung Tech."
        # Preserve the supplied name, without guessing articles or shortening it.
        opening = f"Encontrei {company} e quis entrar em contato." if company else ""
        if request.objective == "first_contact":
            subject = SUBJECTS[segment]
            # A brand already identifying its niche does not need that noun again.
            if company and any(word in company.casefold() for word in ("restaurante", "clínica", "clinica", "consultório", "escritório", "estética")):
                subject = "a presença digital de vocês"
            body = FIRST_CONTACT[request.tone][request.variation].format(subject=subject)
        else:
            opening = ""
            body = CONTINUATIONS[request.objective][request.variation]
        closing = CLOSINGS[request.tone]
        if request.objective == "follow_up":
            closing = "Se fizer sentido, posso explicar a ideia por aqui mesmo."
        if request.channel == "instagram" and request.objective == "first_contact":
            opening = ""
            target = f"de {company}" if company else "de vocês"
            body = (
                f"Queria compartilhar uma ideia sobre a presença digital {target}.",
                f"Tenho uma sugestão para a apresentação online {target}.",
                f"Gostaria de trocar uma ideia sobre a presença digital {target}.",
            )[request.variation]
        if request.channel == "phone":
            question = f"Estou falando com {company}?" if company else "Posso falar com a pessoa responsável pelo negócio?"
            message = f"Abertura: {intro}\nPergunta: {question}\nConvite: {body}\nSe houver interesse: Posso explicar a ideia em um minuto?\nSe não houver interesse: Tudo bem, obrigado pela atenção."
        else:
            message = " ".join(part for part in (intro, opening, body, closing) if part)
        warnings = (() if company else ("Nome da empresa não informado; usada apresentação genérica.",)) + length_warnings(message, request.channel)
        return OutreachResult(message, request.channel, request.objective, request.tone, template_id(request), warnings)
