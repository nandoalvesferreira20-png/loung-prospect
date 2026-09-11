import argparse
import sys
import time
from urllib.parse import quote_plus
import pandas as pd
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError


def safe_text(locator, default=""):
    try:
        if locator.count() > 0:
            return locator.first.inner_text(timeout=1500).strip()
    except Exception:
        pass
    return default


def safe_attr(locator, attr, default=""):
    try:
        if locator.count() > 0:
            value = locator.first.get_attribute(attr, timeout=1500)
            return value or default
    except Exception:
        pass
    return default


def extract_place_data(page, cidade, segmento):
    name = ""

    # Tenta pegar o nome pela estrutura atual do Google Maps
    for selector in [
        "h1.DUwDvf",
        "h1",
    ]:
        try:
            loc = page.locator(selector)
            if loc.count() > 0:
                name = loc.first.inner_text(timeout=2000).strip()
                if name:
                    break
        except Exception:
            pass

    address = ""
    phone = ""
    website = ""
    rating = ""

    # Botões/infos do painel lateral costumam ter aria-label com os dados
    buttons = page.locator("button[aria-label], a[aria-label]")
    try:
        total = min(buttons.count(), 80)
        for i in range(total):
            label = buttons.nth(i).get_attribute("aria-label") or ""

            label_lower = label.lower()

            if not address and ("endereço:" in label_lower or "address:" in label_lower):
                address = label.split(":", 1)[-1].strip()

            if not phone and ("telefone:" in label_lower or "phone:" in label_lower):
                phone = label.split(":", 1)[-1].strip()

            if not website and ("website:" in label_lower or "site:" in label_lower):
                website = buttons.nth(i).get_attribute("href") or ""
    except Exception:
        pass

    # Site também pode aparecer em link direto
    if not website:
        try:
            links = page.locator("a[href^='http']")
            for i in range(min(links.count(), 50)):
                href = links.nth(i).get_attribute("href") or ""
                if "google.com" not in href and "gstatic.com" not in href:
                    website = href
                    break
        except Exception:
            pass

    # Avaliação
    try:
        rating_candidates = page.locator("[aria-label*='estrelas'], [aria-label*='stars']")
        if rating_candidates.count() > 0:
            rating = rating_candidates.first.get_attribute("aria-label") or ""
    except Exception:
        pass

    return {
        "Empresa": name,
        "Segmento pesquisado": segmento,
        "Cidade": cidade,
        "Telefone": phone,
        "WhatsApp": phone,
        "E-mail": "",
        "Instagram": "",
        "Site": website,
        "Endereço": address,
        "Avaliação": rating,
        "Google Maps": page.url,
        "Qualidade do Site (1-5)": "",
        "Presença Digital (1-5)": "",
        "Potencial (1-5)": "",
        "Problemas Encontrados": "",
        "Status Comercial": "Novo Lead",
        "Próxima Ação": "Qualificar lead",
        "Observações": ""
    }


def collect_links_from_maps(page, query, max_results):
    url = f"https://www.google.com/maps/search/{quote_plus(query)}"
    page.goto(url, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(5000)

    links_found = []
    seen = set()

    # Rola a lista para carregar resultados
    for _ in range(12):
        anchors = page.locator("a[href*='/maps/place/']")
        try:
            count = anchors.count()
            for i in range(count):
                href = anchors.nth(i).get_attribute("href")
                if href and href not in seen:
                    seen.add(href)
                    links_found.append(href)
                    if len(links_found) >= max_results:
                        return links_found
        except Exception:
            pass

        try:
            feed = page.locator("div[role='feed']")
            if feed.count() > 0:
                feed.first.evaluate("(el) => el.scrollBy(0, 1200)")
            else:
                page.mouse.wheel(0, 1200)
        except Exception:
            page.mouse.wheel(0, 1200)

        page.wait_for_timeout(2000)

    return links_found[:max_results]


def run(cidades, segmentos, max_results, output, headless=False):
    rows = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context(locale="pt-BR")
        page = context.new_page()

        for cidade in cidades:
            for segmento in segmentos:
                query = f"{segmento} em {cidade}"
                print(f"Buscando links: {query}")

                links = collect_links_from_maps(page, query, max_results)
                print(f"Encontrados {len(links)} links para: {query}")

                for index, link in enumerate(links, start=1):
                    print(f"Coletando {index}/{len(links)}: {link}")

                    try:
                        page.goto(link, wait_until="domcontentloaded", timeout=60000)
                        page.wait_for_timeout(3500)
                        data = extract_place_data(page, cidade, segmento)

                        if data["Empresa"]:
                            rows.append(data)

                    except PlaywrightTimeoutError:
                        print("Tempo esgotado ao abrir empresa.")
                    except Exception as e:
                        print(f"Erro ao coletar empresa: {e}")

                    time.sleep(1.5)

        browser.close()

    df = pd.DataFrame(rows)

    if df.empty:
        print("Nenhum lead coletado.")
        return

    df = df.drop_duplicates(subset=["Empresa", "Endereço"], keep="first")

    if output.endswith(".csv"):
        df.to_csv(output, index=False, encoding="utf-8-sig")
    else:
        df.to_excel(output, index=False)

    print(f"Arquivo gerado: {output}")
    print(f"Total de leads únicos: {len(df)}")


def cli_main(argv=None):
    """Executa a CLI legada sem abrir a interface gráfica."""
    parser = argparse.ArgumentParser(description="Loung Leads - coletor inicial sem API")
    parser.add_argument("--cidades", nargs="+", required=True, help="Ex: Santos Praia_Grande")
    parser.add_argument("--segmentos", nargs="+", required=True, help="Ex: clinica_odontologica clinica_medica")
    parser.add_argument("--max", type=int, default=10, help="Máximo por busca")
    parser.add_argument("--output", default="leads_loungtech.xlsx", help="Arquivo .xlsx ou .csv")
    parser.add_argument("--headless", action="store_true", help="Rodar sem abrir navegador")

    args = parser.parse_args(argv)

    cidades = [c.replace("_", " ") for c in args.cidades]
    segmentos = [s.replace("_", " ") for s in args.segmentos]

    run(cidades, segmentos, args.max, args.output, headless=args.headless)


def gui_main():
    """Executa somente a interface gráfica."""
    from app import LoungLeadsApp

    app = LoungLeadsApp()
    app.mainloop()


def main(argv=None):
    """Sem argumentos abre a GUI; com argumentos mantém a CLI legada."""
    argv = sys.argv[1:] if argv is None else argv
    if argv:
        cli_main(argv)
    else:
        gui_main()


if __name__ == "__main__":
    main()
