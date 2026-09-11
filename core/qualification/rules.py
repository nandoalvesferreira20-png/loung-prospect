"""Conservative, offline rules. Scores express priority, never sale probability.

Version 2 requires observed name, segment and a resolved digital presence to
qualify. Operational signals alone cannot establish a website opportunity.
Insufficient records retain their supported signal score, but need review.
The maximum supported score is 80: these limited inputs do not justify 100.
No timestamp is generated, keeping evaluation deterministic.
"""

from types import MappingProxyType
from core.diagnostics import trace
from .digital_presence import DigitalPresenceType, classify_digital_presence

from .models import (
    ObservationStatus, QualificationInput, QualificationNote,
    QualificationResult, QualificationStatus,
)

RULES_VERSION = "2.0.0"
WEIGHTS = MappingProxyType({
    "website_not_found": 60, "social_media_only": 50, "third_party_presence": 40,
    "phone_observed": 10, "address_observed": 10,
})


def evaluate_rules(lead: QualificationInput) -> QualificationResult:
    """Evaluate supplied observations without changing the input or contacting anyone."""
    reasons = []
    evidence = []
    limitations = []
    score = 0

    def present(name):
        value = getattr(lead, name)
        return isinstance(value, str) and bool(value.strip())

    def observed(name):
        return present(name) and lead.observation_status(name) == ObservationStatus.OBSERVED

    def note(code, text, name=None):
        return QualificationNote(code, text, name, lead.source_url)

    identity_ready = True
    for name, label in (("company_name", "Nome"), ("segment", "Segmento")):
        if observed(name):
            evidence.append(note(f"{name}_observed", f"{label} observado: {getattr(lead, name)}", name))
        else:
            identity_ready = False
            limitations.append(note(f"{name}_unavailable", f"{label} preenchido e observado é necessário para contextualizar a análise.", name))

    website_state = lead.observation_status("website")
    presence = classify_digital_presence(lead.website, website_state)
    trace("DIGITAL_PRESENCE", company=lead.company_name, presence=presence)
    website_missing = presence.presence_type == DigitalPresenceType.NOT_FOUND
    website_present = presence.presence_type == DigitalPresenceType.OWN_WEBSITE
    external_presence = presence.presence_type in (
        DigitalPresenceType.SOCIAL_MEDIA, DigitalPresenceType.THIRD_PARTY_PLATFORM,
    )
    if website_missing:
        evidence.append(note("website_not_found", "Site explicitamente não encontrado na fonte consultada.", "website"))
        reasons.append(note("website_not_found", f"Sinal para revisar uma possível oportunidade de website (+{WEIGHTS['website_not_found']}).", "website"))
        score += WEIGHTS["website_not_found"]
        limitations.append(note("website_absence_unconfirmed", "Não encontrar site na fonte não comprova que a empresa não possui site.", "website"))
    elif external_presence:
        social = presence.presence_type == DigitalPresenceType.SOCIAL_MEDIA
        code = "social_media_presence" if social else "third_party_platform"
        weight = WEIGHTS["social_media_only" if social else "third_party_presence"]
        evidence.append(note(code, f"Presença observada em {presence.provider}: {presence.url}. {presence.reason}", "website"))
        text = (
            "Presença em rede social observada, sem website independente confirmado por esta evidência"
            if social else "Presença observada em plataforma externa, sem website independente confirmado por esta evidência"
        )
        reasons.append(note(code, f"{text}; sinal para revisão de oportunidade de website (+{weight}).", "website"))
        limitations.append(note("independent_website_unconfirmed", "A presença observada não comprova que a empresa não possui outro website independente.", "website"))
        score += weight
    elif website_present:
        evidence.append(note("own_website_observed", f"URL observada: {presence.url}. {presence.reason}", "website"))
        limitations.append(note("website_not_inspected", "Conteúdo, funcionamento e qualidade do site não foram avaliados.", "website"))
    else:
        if presence.presence_type == DigitalPresenceType.ERROR:
            code, text = "website_error", "Observação do site contém erro; é necessária revisão."
        elif website_state in (ObservationStatus.NOT_FOUND, ObservationStatus.OBSERVED):
            code, text = "website_inconsistent", presence.reason + " É necessária revisão."
        else:
            code, text = "website_unverified", "Site não verificado; nenhuma conclusão sobre sua existência."
        limitations.append(note(code, text, "website"))

    for name, label in (("phone", "Telefone"), ("address", "Endereço")):
        if observed(name):
            code = f"{name}_observed"
            evidence.append(note(code, f"{label} observado: {getattr(lead, name)}", name))
            reasons.append(note(code, f"{label} disponível como apoio operacional (+{WEIGHTS[code]}).", name))
            score += WEIGHTS[code]

    if present("phone") or present("whatsapp"):
        limitations.append(note("contact_unverified", "Telefone ou valor de WhatsApp informado não confirma validade, titularidade ou disponibilidade de WhatsApp."))
    limitations.append(note("human_review_required", "Resultado para revisão humana; não autoriza contato."))

    sufficient = identity_ready and (website_missing or website_present or external_presence)
    opportunity = ("website" if website_missing or external_presence else "none") if sufficient else "needs_review"
    return QualificationResult(
        status=QualificationStatus.QUALIFIED if sufficient else QualificationStatus.INSUFFICIENT_DATA,
        score=max(0, min(100, score)), opportunity=opportunity,
        reasons=reasons, evidence=evidence, limitations=limitations,
        rules_version=RULES_VERSION,
    )
