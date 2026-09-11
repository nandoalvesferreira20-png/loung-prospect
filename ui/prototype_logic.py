"""Presentation logic without widgets; no automatic generation or selection."""
from core.prototype.models import PrototypeLead, PrototypeRequest
from core.prototype.registry import TemplateRegistry
from core.prototype.generator import generate_prototype


def parse_score(value):
    if not value.strip():
        return None
    try:
        score = int(value)
    except ValueError:
        raise ValueError("Score deve ser inteiro entre 0 e 100.") from None
    if not 0 <= score <= 100:
        raise ValueError("Score deve ser inteiro entre 0 e 100.")
    return score


def build_request(fields, template_id, registry):
    for key, label in (("company_name", "Nome da empresa"), ("segment", "Segmento"), ("output_directory", "Pasta de saída")):
        if not fields.get(key, "").strip():
            raise ValueError(f"Informe {label}.")
    if not template_id:
        raise ValueError("Selecione um template.")
    template = registry.get_template(template_id)
    if template.segment.strip().lower() != fields["segment"].strip().lower():
        raise ValueError("Template incompatível com o segmento. Carregue os templates novamente.")
    lead = PrototypeLead(
        company_name=fields["company_name"].strip(), segment=fields["segment"].strip(),
        qualification_score=parse_score(fields.get("qualification_score", "")),
        **{name: fields.get(name) or None for name in
           ("city", "phone", "whatsapp", "address", "current_website")},
    )
    return PrototypeRequest(lead, template, fields["output_directory"].strip())


class PrototypeSession:
    def __init__(self, registry=None):
        self.registry = registry if registry is not None else TemplateRegistry()
        self.last_result = None

    def templates(self, segment):
        return self.registry.find_templates_for_segment(segment)

    @property
    def can_open(self):
        return self.last_result is not None and self.last_result.status == "created"

    def generate(self, fields, template_id):
        self.last_result = None
        request = build_request(fields, template_id, self.registry)
        self.last_result = generate_prototype(request)
        return self.last_result
