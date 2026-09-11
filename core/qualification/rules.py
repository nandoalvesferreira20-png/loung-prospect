"""Conservative, offline rules. Scores express priority, never sale probability.

Version 1 requires observed name, segment and a resolved website observation to
qualify. Operational signals alone cannot establish a website opportunity.
Insufficient records retain their supported signal score, but need review.
The maximum supported score is 80: these limited inputs do not justify 100.
No timestamp is generated, keeping evaluation deterministic.
"""

from types import MappingProxyType

from .models import (
    ObservationStatus, QualificationInput, QualificationNote,
    QualificationResult, QualificationStatus,
)

RULES_VERSION = "1.0.0"
WEIGHTS = MappingProxyType({"website_not_found": 60, "phone_observed": 10, "address_observed": 10})


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
    website_missing = website_state == ObservationStatus.NOT_FOUND and not present("website")
    website_present = observed("website")
    if website_missing:
        evidence.append(note("website_not_found", "Site explicitamente não encontrado na fonte consultada.", "website"))
        reasons.append(note("website_not_found", f"Sinal para revisar uma possível oportunidade de website (+{WEIGHTS['website_not_found']}).", "website"))
        score += WEIGHTS["website_not_found"]
        limitations.append(note("website_absence_unconfirmed", "Não encontrar site na fonte não comprova que a empresa não possui site.", "website"))
    elif website_present:
        evidence.append(note("website_observed", f"Site informado na fonte: {lead.website}", "website"))
        limitations.append(note("website_not_inspected", "Conteúdo, funcionamento e qualidade do site não foram avaliados.", "website"))
    else:
        if website_state == ObservationStatus.ERROR:
            code, text = "website_error", "Observação do site contém erro; é necessária revisão."
        elif website_state in (ObservationStatus.NOT_FOUND, ObservationStatus.OBSERVED):
            code, text = "website_inconsistent", "Valor e estado de observação do site são inconsistentes; é necessária revisão."
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

    sufficient = identity_ready and (website_missing or website_present)
    opportunity = ("website" if website_missing else "none") if sufficient else "needs_review"
    return QualificationResult(
        status=QualificationStatus.QUALIFIED if sufficient else QualificationStatus.INSUFFICIENT_DATA,
        score=max(0, min(100, score)), opportunity=opportunity,
        reasons=reasons, evidence=evidence, limitations=limitations,
        rules_version=RULES_VERSION,
    )
