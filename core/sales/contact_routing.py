"""Maintainable niche defaults and generation policy; contact roles are hypotheses."""
import re
import unicodedata

CONTACT_TYPES = {"Recepção/equipe": "recepcao_equipe", "Contato direto": "contato_direto", "Indefinido": "indefinido"}

# Match normalized niche text, never infer size/ownership from company names.
NICHE_RULES = {
    "recepcao_equipe": (
        r"\bclinic\w*\b.*\b(?:odont\w*|dent\w*|medic\w*|estetic\w*|veterin\w*|vet)\b",
        r"\b(?:hospital|hospitais)\b.*\b(?:veterin\w*|vet)\b",
        r"\b(?:policlinic\w*|centro medico|centros medicos)\b",
        r"\b(?:restaurante\w*|cafeteria\w*|coffee shop|casa de cafe)\b",
        r"\b(?:academia\w*|cross\s*fit)\b",
        r"\bsal(?:ao|oes)\b.*\b(?:medi\w*|grande\w*)\b",
        r"\b(?:medi\w*|grande\w*)\b.*\bsal(?:ao|oes)\b",
    ),
    "contato_direto": (
        r"\b(?:corretor\w*|advogad\w*)\b.*\b(?:autonom\w*|independente\w*)\b",
        r"\b(?:autonom\w*|independente\w*)\b.*\b(?:corretor\w*|advogad\w*)\b",
        r"\bbarbeir[oa]s?\b",
        r"\bbarbearia\w*\b.*\b(?:pequen\w*|individual)\b",
        r"\b(?:pequen\w*|individual)\b.*\bbarbearia\w*\b",
        r"\b(?:estetic\w*|profissiona\w*)\b.*\b(?:autonom\w*|independente\w*)\b",
        r"\b(?:autonom\w*|independente\w*)\b.*\bestetic\w*\b",
        r"\bpersonal\s*trainers?\b",
    ),
}


def normalize_niche(value):
    text = unicodedata.normalize("NFKD", value if isinstance(value, str) else "")
    text = "".join(char for char in text if not unicodedata.combining(char)).casefold()
    return " ".join(re.sub(r"[^a-z0-9]+", " ", text).split())


def classify_contact(segment):
    text = normalize_niche(segment)
    if re.search(r"\bimobiliari\w*\b", text):
        return "indefinido"  # A general agency number is not an autonomous broker.
    if re.search(r"\bsal(?:ao|oes)\b", text) and re.search(r"\bpequen\w*\b", text):
        return "indefinido"
    if re.search(r"\bbarbearia\w*\b", text) and re.search(r"\b(?:medi\w*|grande\w*)\b", text):
        return "indefinido"
    matches = {kind for kind, patterns in NICHE_RULES.items() if any(re.search(pattern, text) for pattern in patterns)}
    return next(iter(matches)) if len(matches) == 1 else "indefinido"


def contact_context(segment, override=None):
    if override is not None and override not in CONTACT_TYPES.values():
        raise ValueError("Tipo de contato inválido.")
    return {"tipo_contato": override or classify_contact(segment),
            "tipo_contato_origem": "ajuste_manual" if override is not None else "sugestao_nicho"}


CONTACT_GUIDANCE = """
Adapte a abertura ao campo tipo_contato. Ele indica contato PROVÁVEL, nunca uma
certeza sobre quem respondeu; isso também vale para ajuste_manual. Não chame
a pessoa de proprietária, gerente ou recepcionista e não afirme estrutura ou porte.
- recepcao_equipe: mensagem curta e educada, perguntando quem cuida da área
  relacionada à única solução sugerida e pedindo encaminhamento. Evite proposta
  longa para quem talvez não decida. Ex.: 'Quem cuida da apresentação digital?
  Poderiam me encaminhar à pessoa responsável?'. Não afirme que existe recepção.
- contato_direto: fale com o profissional de forma objetiva e respeitosa,
  relacionando a ideia ao nicho informado e à oportunidade recebida, se houver.
  Oportunidade interna continua sendo hipótese, não carência comprovada. Sem
  oportunidade concreta, faça um convite breve e exploratório, sem inventar uma.
- indefinido: abertura neutra, perguntando quem é a pessoa responsável pelo
  assunto. Não presuma cargo, tamanho da equipe nem que o interlocutor decide.
Só mencione observações específicas presentes nos dados recebidos. Não invente
problemas, serviços, características, tamanho do negócio ou ausência de site.
Dados incompletos exigem texto neutro e sem detalhes presumidos. Use português
natural, tom respeitoso e uma chamada para conversa sem pressão.
"""
