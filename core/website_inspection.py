"""Inspect only the already-open Maps panel; never navigate to company sites."""

from urllib.parse import urlsplit

from core.validator import WebsiteVerification, with_website_verification


PANEL_SNAPSHOT = r"""() => {
    const visible = el => el.getClientRects().length > 0;
    const panels = [...document.querySelectorAll('[role="main"]')]
        .filter(el => visible(el) && el.querySelector('h1'));
    if (panels.length !== 1) return null;
    const panel = panels[0];
    const name = panel.querySelector('h1').textContent.trim();
    const address = panel.querySelector('[data-item-id="address"]');
    const busy = document.querySelector('[aria-busy="true"], [role="progressbar"]');
    if (!name || !address || !visible(address) || (busy && visible(busy))) return null;
    const controls = [...panel.querySelectorAll('a, button')];
    const websites = controls.filter(el =>
        el.getAttribute('data-item-id') === 'authority' ||
        /^(website|site)\s*:/i.test(el.getAttribute('aria-label') || '')
    ).map(el => el.getAttribute('href') || '');
    return {name, websites, signature: panel.innerHTML, url: location.href};
}"""


def enrich_website_verification(page, record):
    """Attach a conservative report without changing collected values.

    Absence is scoped to two identical snapshots of a recognizable, non-loading
    panel, 500 ms apart. Missing readiness markers, changing DOM, generic fallback
    links or unrecognized website controls remain inconclusive. DOM readiness is
    a heuristic, not a guarantee against future Google Maps markup changes.
    """
    source = record["Google Maps"]
    check = WebsiteVerification(source)
    try:
        first = page.evaluate(PANEL_SNAPSHOT)
        if first is not None:
            page.wait_for_timeout(500)
            second = page.evaluate(PANEL_SNAPSHOT)
            if (first == second and first["url"] == source
                    and first["name"] == record["Empresa"]):
                links = first["websites"]
                site = record.get("Site", "")
                if site and site in links:
                    parsed = urlsplit(site)
                    if parsed.scheme in ("http", "https") and parsed.hostname:
                        check = WebsiteVerification(source, True, True)
                elif not site and not links:
                    check = WebsiteVerification(source, True, False)
    except Exception:
        check = WebsiteVerification(source, error=True)
    return with_website_verification(record, check)
