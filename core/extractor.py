# core/extractor.py

from playwright.sync_api import Page
from core.website_inspection import enrich_website_verification, inspect_explicit_website


def extract_company_data(page: Page, cidade: str, segmento: str, *, verify_website: bool = False) -> dict:
    """
    Extrai as informações da empresa na página atual do Google Maps.
    """

    data = {
        "Empresa": "",
        "Cidade": cidade,
        "Segmento": segmento,
        "Telefone": "",
        "WhatsApp": "",
        "Site": "",
        "Endereço": "",
        "Avaliação": "",
        "Google Maps": page.url,
        "Status Comercial": "Novo Lead",
        "Próxima Ação": "Qualificar lead",
        "Potencial (1-5)": "",
        "Observações": ""
    }

    # ==========================
    # Nome da empresa
    # ==========================

    try:
        for selector in [
            "h1.DUwDvf",
            "h1"
        ]:
            element = page.locator(selector)

            if element.count() > 0:
                data["Empresa"] = element.first.inner_text(timeout=2000).strip()

                if data["Empresa"]:
                    break

    except Exception:
        pass

    # ==========================
    # Botões do Google Maps
    # ==========================

    try:

        buttons = page.locator("button[aria-label], a[aria-label]")

        total = min(buttons.count(), 100)

        for i in range(total):

            btn = buttons.nth(i)

            label = btn.get_attribute("aria-label") or ""

            lower = label.lower()

            # --------------------------
            # Telefone
            # --------------------------

            if (
                not data["Telefone"]
                and ("telefone:" in lower or "phone:" in lower)
            ):
                telefone = label.split(":", 1)[-1].strip()

                data["Telefone"] = telefone
                data["WhatsApp"] = telefone

            # --------------------------
            # Endereço
            # --------------------------

            if (
                not data["Endereço"]
                and ("endereço:" in lower or "address:" in lower)
            ):
                data["Endereço"] = label.split(":", 1)[-1].strip()

            # --------------------------
            # Site
            # --------------------------

            if (
                not data["Site"]
                and ("website:" in lower or "site:" in lower)
            ):
                href = btn.get_attribute("href")

                if href:
                    data["Site"] = href

    except Exception:
        pass

    # ==========================
    # Caso o site não tenha sido encontrado
    # ==========================

    if not data["Site"]:

        try:

            links = page.locator("a[href^='http']")

            total = min(links.count(), 60)

            for i in range(total):

                href = links.nth(i).get_attribute("href")

                if not href:
                    continue

                if "google.com" in href:
                    continue

                if "gstatic.com" in href:
                    continue

                data["Site"] = href
                break

        except Exception:
            pass

    # ==========================
    # Avaliação
    # ==========================

    try:

        rating = page.locator(
            "[aria-label*='estrelas'], [aria-label*='stars']"
        )

        if rating.count() > 0:
            data["Avaliação"] = (
                rating.first.get_attribute("aria-label") or ""
            )

    except Exception:
        pass

    if verify_website:
        explicit = inspect_explicit_website(page, data)
        if explicit is not None:
            return explicit
        return enrich_website_verification(page, data)
    return data
