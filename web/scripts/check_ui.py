"""Local-only phase-1 checks. Never starts the desktop or calls providers."""
from pathlib import Path
import json
import sys
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright

base = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:3000"
assert urlparse(base).hostname in {"localhost", "127.0.0.1"}, "Use a local server."
out = Path(__file__).resolve().parents[1] / "test-results"
out.mkdir(exist_ok=True)
routes = {"/": "Uma visão clara da sua operação", "/prospeccao": "Encontre seu próximo cliente", "/leads": "Sua carteira de leads", "/sdr": "Do contexto à conversa", "/pipeline": "Cada oportunidade no seu momento", "/meu-dia": "Meu Dia", "/configuracoes": "Configurações"}
errors, external, checked = [], [], []
with sync_playwright() as p:
    browser = None
    for channel in ["msedge", "chrome"]:
        try:
            browser = p.chromium.launch(channel=channel, headless=True)
            break
        except Exception:
            pass
    if browser is None:
        raise RuntimeError("Edge ou Chrome não disponível para validar localmente.")
    context = browser.new_context(permissions=["clipboard-read", "clipboard-write"])
    page = context.new_page()
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.on("console", lambda message: errors.append(message.text) if message.type == "error" and "Failed to load resource" not in message.text else None)
    def check_request(route):
        url = route.request.url
        if urlparse(url).scheme in {"http", "https"} and urlparse(url).hostname not in {"localhost", "127.0.0.1"}:
            external.append(url)
            route.abort()
        else:
            route.continue_()
    context.route("**/*", check_request)
    for width, height in [(1440, 1000), (1024, 768), (390, 844)]:
        page.set_viewport_size({"width": width, "height": height})
        for path, title in routes.items():
            response = page.goto(base + path, wait_until="networkidle")
            assert response and response.status == 200, path
            page.get_by_role("heading", name=title, exact=True, level=1).wait_for()
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), f"Overflow: {path} {width}"
            page.screenshot(path=str(out / f"{path.strip('/') or 'dashboard'}-{width}.png"), full_page=True)
            checked.append(f"{path} @ {width}x{height}")
    page.set_viewport_size({"width": 390, "height": 844})
    page.get_by_role("button", name="Abrir navegação").click()
    dialog = page.get_by_role("dialog")
    dialog.wait_for()
    dialog.get_by_role("link", name="Prospecção", exact=True).click()
    page.get_by_role("heading", name=routes["/prospeccao"]).wait_for()
    assert page.get_by_role("dialog").count() == 0
    page.get_by_role("button", name="Abrir navegação").click()
    page.keyboard.press("Escape")
    assert page.get_by_role("dialog").count() == 0
    assert page.get_by_role("button", name="Abrir navegação").evaluate("element => element === document.activeElement")
    page.get_by_role("button", name="Iniciar pesquisa").click()
    page.get_by_text("Informe um nicho com pelo menos 2 caracteres.").wait_for()
    page.get_by_label("Nicho ou segmento").fill("Clínicas odontológicas")
    page.get_by_label("Localização", exact=True).fill("São Paulo, SP")
    page.get_by_label("Quantidade máxima", exact=True).fill("101")
    page.get_by_role("button", name="Iniciar pesquisa").click()
    page.get_by_text("Máximo de 100 empresas.", exact=True).wait_for()
    page.goto(base + "/configuracoes")
    page.get_by_label("Seu nome de exibição").fill("Validação local")
    page.get_by_label("Atalho de trabalho preferido").select_option("/sdr")
    page.get_by_role("button", name="Salvar preferências").click()
    page.get_by_role("status").get_by_text("Preferências salvas neste navegador.").wait_for()
    page.reload(wait_until="networkidle")
    assert page.get_by_label("Seu nome de exibição").input_value() == "Validação local"
    assert page.get_by_label("Atalho de trabalho preferido").input_value() == "/sdr"
    page.get_by_role("link", name="Abrir atalho escolhido").click()
    page.get_by_role("heading", name=routes["/sdr"]).wait_for()
    # The functional editor now requires a real selected lead. Full offline SDR
    # coverage (including clipboard) is in check_sdr.py with a synthetic backend.
    page.get_by_role("heading", name="Escolha com quem conversar").wait_for()
    page.goto(base + "/pagina-inexistente")
    page.get_by_role("heading", name="Página não encontrada").wait_for()
    assert not errors, errors
    assert not external, external
    report = {"routes_and_viewports": checked, "functional_checks": ["mobile navigation", "Escape and focus", "invalid prospecting input without starting a search", "local preferences persistence", "SDR requires lead selection", "404"], "javascript_errors": errors, "external_requests": external}
    (out / "ui-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    context.close()
    browser.close()
