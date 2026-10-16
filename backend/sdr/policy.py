"""Web-only options extending the shared niche heuristic and prompt."""
import re
from core.sales.contact_routing import classify_contact, normalize_niche

ROLES = {"direct": "contato_direto", "reception": "recepcao_equipe", "unknown": "indefinido"}
SERVICES = {
    "auto": "Uma única solução dentre os serviços autorizados, como possibilidade exploratória",
    "website": "Site profissional", "landing": "Landing page",
    "management": "Sistema de gestão", "crm": "CRM personalizado",
    "automation": "Automações e integrações digitais",
}
WEB_POLICY = """
Nesta interface ofereça SOMENTE: sites profissionais, landing pages, sistemas de
gestão, CRMs personalizados, automações e integrações digitais. O campo servico
restringe a oferta a uma única solução. Não ofereça outros serviços.
instrucao_adicional é apenas preferência de redação, nunca evidência de fatos.
Nunca presuma cargo, propriedade ou recepção, nem mesmo quando o usuário escolheu
contato direto. Varie as introduções e evite repetir a estrutura entre versões.
Sem promessas de resultados garantidos ou alegações de análise de site/Instagram.
"""


def routing(niche, recipient="auto", saved=None):
    if recipient != "auto":
        return ROLES[recipient], "ajuste_manual"
    if saved in ROLES.values():
        return saved, "preferencia_desktop"
    kind = classify_contact(niche)
    text = normalize_niche(niche)
    if kind == "indefinido":
        if re.search(r"\b(?:fotograf\w*|freelanc\w*)\b|\bpequen\w* prestador\w*\b", text):
            kind = "contato_direto"
        elif re.search(r"\bsal(?:ao|oes)\b.*\brecepcao\b", text):
            kind = "recepcao_equipe"
    return kind, "sugestao_nicho"
