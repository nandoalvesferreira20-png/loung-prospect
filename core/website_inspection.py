"""Inspect only the already-open Maps panel; never navigate to company sites."""

from urllib.parse import urlsplit
from core.diagnostics import trace, enabled

from core.validator import WebsiteVerification, with_website_verification


# Positive evidence requires a scoped, visible control, not a fully settled panel.
EXPLICIT_WEBSITE = r"""() => {
    const visible = el => el.getClientRects().length > 0;
    const panels = [...document.querySelectorAll('[role="main"]')]
        .filter(el => visible(el) && el.querySelector('h1'));
    if (panels.length !== 1) return null;
    const panel = panels[0];
    const controls = [...panel.querySelectorAll('a, button')].filter(el =>
        visible(el) && (el.getAttribute('data-item-id') === 'authority' ||
        /^(website|site)\s*:/i.test(el.getAttribute('aria-label') || '')));
    const links = [...new Set(controls.map(el => el.getAttribute('href')).filter(Boolean))];
    if (links.length !== 1) return null;
    return {name: panel.querySelector('h1').textContent.trim(), url: location.href,
            explicit_href: links[0]};
}"""


def inspect_explicit_website(page, record):
    """Copy a URL only when the current company panel identifies its provenance.

    No provider or hostname allowlist is used. This positive observation does not
    certify panel completeness, website ownership or the availability of the URL.
    """
    source = record["Google Maps"]
    try:
        if enabled():
            try:
                inventory = page.evaluate(r"""() => ({url: location.href,
                    panels: [...document.querySelectorAll('[role="main"]')].map(p => ({
                        visible: p.getClientRects().length > 0,
                        name: p.querySelector('h1')?.textContent,
                        address: !!p.querySelector('[data-item-id="address"]'),
                        controls: [...p.querySelectorAll('a, button')].map(e => ({
                            label: e.getAttribute('aria-label'), item: e.getAttribute('data-item-id'),
                            href: e.getAttribute('href'), visible: e.getClientRects().length > 0
                        }))
                    }))})""")
                trace("DOM_INVENTORY", company=record["Empresa"], inventory=inventory)
            except Exception as diagnostic_error:
                trace("DOM_DIAGNOSTIC_ERROR", message=str(diagnostic_error))
        snapshot = page.evaluate(EXPLICIT_WEBSITE)
        trace("EXPLICIT_SNAPSHOT", company=record["Empresa"], input_site=record.get("Site"), snapshot=snapshot,
              criterion="visible main with h1; visible authority or anchored Site:/Website:; exactly one distinct href")
        if snapshot and snapshot.get("explicit_href"):
            href = snapshot["explicit_href"]
            parsed = urlsplit(href)
            if (snapshot["name"] == record["Empresa"] and snapshot["url"] == source
                    and parsed.scheme in ("http", "https") and parsed.hostname):
                trace("VERIFICATION", company=record["Empresa"], reason="explicit control accepted",
                      verification=WebsiteVerification(source, True, True, website_source="explicit_website_control"))
                return with_website_verification(
                    {**record, "Site": href},
                    WebsiteVerification(source, True, True, website_source="explicit_website_control"),
                )
            trace("EXPLICIT_REJECTED", name_matches=snapshot["name"] == record["Empresa"],
                  url_matches=snapshot["url"] == source, scheme=parsed.scheme, hostname=parsed.hostname)
    except Exception as error:
        trace("VERIFICATION", reason="explicit inspection exception", message=str(error),
              verification=WebsiteVerification(source, error=True))
        return with_website_verification(record, WebsiteVerification(source, error=True))
    return None


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
        trace("PANEL_FIRST", company=record["Empresa"], available=first is not None,
              site_used=record.get("Site"), reason="null means panel count/name/address/loading gate failed")
        if first is not None:
            page.wait_for_timeout(500)
            second = page.evaluate(PANEL_SNAPSHOT)
            trace("PANEL_COMPARISON", stable=first == second, name_matches=first["name"] == record["Empresa"],
                  url_matches=first["url"] == source, website_controls=first["websites"], site_used=record.get("Site"))
            if (first == second and first["url"] == source
                    and first["name"] == record["Empresa"]):
                links = first["websites"]
                site = record.get("Site", "")
                if site and site in links:
                    parsed = urlsplit(site)
                    if parsed.scheme in ("http", "https") and parsed.hostname:
                        check = WebsiteVerification(source, True, True, website_source="explicit_website_control")
                elif not site and not links:
                    check = WebsiteVerification(source, True, False)
    except Exception as error:
        trace("PANEL_ERROR", message=str(error))
        check = WebsiteVerification(source, error=True)
    trace("VERIFICATION", company=record["Empresa"], verification=check,
          reason="completed: matching explicit URL or empty Site with no website controls; incomplete: readiness/stability/identity/URL match failed; see preceding diagnostics")
    return with_website_verification(record, check)
