"""Versioned local phrasing; no assertion of research or commercial diagnosis."""
import unicodedata

VERSION = "v1"
SEGMENTS = {
    "dentista": "o consultório",
    "estetica": "o espaço de estética",
    "veterinario": "a clínica veterinária",
    "advogado": "o escritório",
    "restaurante": "o restaurante",
    "generic": "a empresa",
}
ALIASES = {"odontologia": "dentista", "clinica odontologica": "dentista",
           "veterinaria": "veterinario", "advocacia": "advogado"}
GREETINGS = {"professional": "Olá, tudo bem?", "friendly": "Oi, tudo bem?", "direct": "Oi!"}
# Context selects a subject; it is not a sentence made from every lead field.
SUBJECTS = {
    "dentista": "a apresentação do consultório na internet",
    "estetica": "a presença digital do espaço",
    "veterinario": "a apresentação da clínica na internet",
    "advogado": "a apresentação profissional do escritório na internet",
    "restaurante": "a presença digital e a experiência online",
    "generic": "a presença digital do negócio",
}
FIRST_CONTACT = {
    "professional": (
        "Gostaria de compartilhar uma ideia sobre {subject}.",
        "Meu contato é para propor uma conversa breve sobre {subject}.",
        "Gostaria de apresentar uma possibilidade relacionada à presença digital de vocês.",
    ),
    "friendly": (
        "Queria trocar uma ideia com vocês sobre {subject}.",
        "Queria compartilhar uma ideia para valorizar a presença digital de vocês.",
        "Pensei em entrar em contato para conversar sobre {subject}.",
    ),
    "direct": (
        "Tenho uma sugestão sobre {subject} para compartilhar com vocês.",
        "Gostaria de propor uma ideia para a presença digital de vocês.",
        "Meu contato é sobre {subject}. Gostaria de compartilhar uma sugestão.",
    ),
}
CONTINUATIONS = {
    "follow_up": (
        "Passando só para retomar minha mensagem anterior.",
        "Retomo o convite da minha última mensagem, sem pressa.",
        "Volto à ideia que mencionei na mensagem anterior.",
    ),
    "reactivation": (
        "Resolvi retomar o contato para conversar sobre a presença digital de vocês.",
        "Faz um tempo desde meu último contato. Gostaria de retomar a ideia sobre presença digital.",
        "Volto a entrar em contato para compartilhar uma ideia sobre a presença digital de vocês.",
    ),
}
CLOSINGS = {
    "professional": "Posso explicar por aqui?",
    "friendly": "Posso te contar rapidinho por aqui?",
    "direct": "Posso te contar?",
}


def normalize_segment(value):
    value = unicodedata.normalize("NFKD", value or "")
    value = "".join(char for char in value if not unicodedata.combining(char)).strip().lower()
    value = ALIASES.get(value, value)
    return value if value in SEGMENTS else "generic"


def segment_display(value):
    return SEGMENTS[normalize_segment(value)]


def template_id(request):
    return f"{request.channel}_{request.objective}_{normalize_segment(request.context.segment)}_{request.tone}_{VERSION}_{request.variation}"
