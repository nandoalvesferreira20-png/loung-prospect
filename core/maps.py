# core/maps.py

from urllib.parse import quote_plus
from playwright.sync_api import Page


def iter_links(page, query, log=print, should_stop=lambda: False, max_scroll_attempts=12):
    """Incremental discovery on a dedicated search page.

    Stop on three rounds without new links or the existing scroll safety bound.
    The caller stops consuming as soon as its accepted-lead target is reached.
    """
    if should_stop():
        return
    page.goto(f"https://www.google.com/maps/search/{quote_plus(query)}",
              wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(5000)
    seen = set()
    stale = 0
    for attempt in range(max_scroll_attempts + 1):
        if should_stop():
            return
        anchors = page.locator("a[href*='/maps/place/']")
        before = len(seen)
        for i in range(anchors.count()):
            if should_stop():
                return
            href = anchors.nth(i).get_attribute("href")
            if href and href not in seen:
                seen.add(href)
                yield href
        stale = stale + 1 if len(seen) == before else 0
        if stale >= 3:
            log("Não apareceram novos links após três tentativas de rolagem.")
            return
        if attempt == max_scroll_attempts:
            log("Limite de segurança de rolagem atingido nesta busca.")
            return
        scroll_results(page)
        page.wait_for_timeout(1800)


def collect_links(
    page: Page,
    query: str,
    max_results: int,
    log=print
) -> list[str]:
    """
    Abre o Google Maps, pesquisa a query e coleta links de empresas.
    """

    url = f"https://www.google.com/maps/search/{quote_plus(query)}"

    log(f"🌐 Abrindo Google Maps...")

    page.goto(
        url,
        wait_until="domcontentloaded",
        timeout=60000
    )

    page.wait_for_timeout(5000)

    links = []
    seen = set()

    scroll_attempts = 0
    max_scroll_attempts = 12

    while len(links) < max_results and scroll_attempts < max_scroll_attempts:

        anchors = page.locator("a[href*='/maps/place/']")

        try:
            total = anchors.count()

            for i in range(total):
                href = anchors.nth(i).get_attribute("href")

                if not href:
                    continue

                if href in seen:
                    continue

                seen.add(href)
                links.append(href)

                log(f"🔗 Link coletado: {len(links)}/{max_results}")

                if len(links) >= max_results:
                    break

        except Exception as e:
            log(f"Erro ao coletar links: {e}")

        if len(links) >= max_results:
            break

        scroll_results(page)

        scroll_attempts += 1

        page.wait_for_timeout(1800)

    return links[:max_results]


def scroll_results(page: Page):
    """
    Rola a lista lateral de resultados do Google Maps.
    """

    try:
        feed = page.locator("div[role='feed']")

        if feed.count() > 0:
            feed.first.evaluate(
                "(el) => el.scrollBy(0, 1200)"
            )
            return

    except Exception:
        pass

    try:
        page.mouse.wheel(0, 1200)

    except Exception:
        pass
