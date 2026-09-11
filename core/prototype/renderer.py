"""Small renderer for trusted HTML templates; lead values are always escaped.

Placeholders belong only in HTML text or quoted attributes, never script/style
contexts. Conditional blocks cannot nest. Lead values are inserted in one pass
and are never interpreted as template syntax.
"""
import html
import re

from .models import PrototypeLead


def _number(value):
    if not value or not re.fullmatch(r"[+0-9() .-]+", value.strip()):
        return None
    digits = re.sub(r"[^0-9]", "", value)
    return digits if 8 <= len(digits) <= 15 else None


def render_index(template: str, lead: PrototypeLead) -> str:
    """Render approved tokens. No country code, contact identity or facts inferred.

    WhatsApp numbers are assumed supplied in international form; no country code
    is added. Missing/unusable WhatsApp falls back to a telephone URI.
    """
    values = {name: getattr(lead, name) or "" for name in
              ("company_name", "segment", "city", "phone", "whatsapp", "address")}
    whatsapp = _number(lead.whatsapp)
    phone = _number(lead.phone)
    values["contact_url"] = (f"https://wa.me/{whatsapp}" if whatsapp else
                             "tel:" + ("+" if (lead.phone or "").strip().startswith("+") else "") + phone if phone else "")
    values["contact_label"] = "Conversar pelo WhatsApp" if whatsapp else "Entrar em contato"
    token = re.compile(r"{{\s*(.*?)\s*}}", re.DOTALL)
    output = []
    cursor = 0
    active = None
    for match in token.finditer(template):
        if active is None or values[active].strip():
            output.append(template[cursor:match.start()])
        key = match.group(1)
        if key.startswith("#if "):
            field = key[4:].strip()
            if active is not None or field not in values:
                raise ValueError(f"Invalid conditional: {key}")
            active = field
        elif key == "/if":
            if active is None:
                raise ValueError("Unexpected /if")
            active = None
        elif key not in values:
            raise ValueError(f"Unknown placeholder: {key}")
        elif active is None or values[active].strip():
            output.append(html.escape(values[key], quote=True))
        cursor = match.end()
    if active is not None:
        raise ValueError("Unclosed conditional")
    output.append(template[cursor:])
    # Reject malformed syntax in the source, never scan inserted lead data.
    remainder = token.sub("", template)
    if "{{" in remainder or "}}" in remainder:
        raise ValueError("Malformed placeholder")
    return "".join(output)
