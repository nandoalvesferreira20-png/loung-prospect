"""Offline end-to-end checks. Requires the explicit phase23 fixture on port 8100.

Run the web production server with LOUNG_API_URL=http://127.0.0.1:8100, port 3100.
All external browser requests, including WhatsApp, are intercepted, never sent.
"""
from pathlib import Path
from urllib.parse import urlsplit, parse_qs
import json
import urllib.request
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "backend/.phase23-visual"


def metrics():
    with urllib.request.urlopen("http://127.0.0.1:8100/__test/metrics", timeout=3) as response:
        result = json.load(response)
    assert result["signature"] == "phase23-synthetic-only", "Refusing to test a real backend"
    return result


def main():
    initial = metrics()["calls"]
    OUT.mkdir(exist_ok=True)
    errors, whatsapp = [], []
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=True)
        context = browser.new_context(viewport={"width":1440,"height":1050}, permissions=["clipboard-read", "clipboard-write"])
        def intercept(route):
            parsed = urlsplit(route.request.url)
            if parsed.hostname in {"localhost", "127.0.0.1"}:
                route.continue_()
            elif parsed.hostname == "wa.me":
                whatsapp.append(route.request.url)
                route.fulfill(status=200, content_type="text/html", body="<title>WhatsApp intercepted offline</title>")
            else:
                errors.append("Unexpected external request: " + parsed.hostname)
                route.abort()
        context.route("**/*", intercept)
        page = context.new_page()
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto("http://127.0.0.1:3100/sdr")
        expect(page.get_by_text("Escolha com quem conversar")).to_be_visible()
        page.get_by_role("button", name="TESTE Clínica Árvore").click()
        expect(page.locator("#recipient")).to_have_value("auto")
        expect(page.locator("#recipient option:checked")).to_have_text("Automático · Recepção/equipe")
        expect(page.get_by_role("button", name="Abrir WhatsApp")).to_be_disabled()
        page.get_by_role("button", name="Gerar abordagem com IA").dblclick()
        expect(page.locator("#message")).to_have_value(__import__("re").compile("encaminhar"))
        assert metrics()["calls"] == initial + 1
        text = "Olá, equipe! Uma opção para vocês.\nPodemos conversar sobre integração & gestão?"
        page.locator("#message").fill(text)
        page.get_by_role("button", name="Copiar mensagem", exact=True).click()
        expect(page.get_by_text("Mensagem copiada.", exact=True)).to_be_visible()
        assert page.evaluate("navigator.clipboard.readText()").replace("\r\n", "\n") == text
        with page.expect_popup() as popup:
            page.get_by_role("link", name="Abrir WhatsApp").click()
        popup.value.wait_for_load_state()
        assert len(whatsapp) == 1
        url = urlsplit(whatsapp[0])
        assert url.path == "/5511999991234"
        assert parse_qs(url.query)["text"][0] == text
        assert "%0A" in whatsapp[0] and "%C3" in whatsapp[0]
        popup.value.close()
        page.get_by_role("button", name="TESTE Fotógrafo").click()
        expect(page.get_by_role("dialog")).to_be_visible()
        page.get_by_role("button", name="Continuar editando", exact=True).click()
        expect(page.locator("#message")).to_have_value(text)
        page.get_by_role("button", name="TESTE Fotógrafo").click()
        page.get_by_role("button", name="Salvar e continuar", exact=True).click()
        expect(page.get_by_role("heading", name="TESTE Fotógrafo", exact=True)).to_be_visible()
        page.locator("#recipient").select_option("unknown")
        page.locator("#service").select_option("automation")
        page.get_by_role("button", name="Gerar abordagem com IA").click()
        expect(page.locator("#message")).to_have_value(__import__("re").compile("responsável"))
        assert "/351912345678?text=" in page.get_by_role("link", name="Abrir WhatsApp").get_attribute("href")
        page.get_by_role("button", name="Salvar texto revisado").click()
        expect(page.get_by_text("Texto revisado salvo no histórico.")).to_be_visible()
        page.locator("#recipient").select_option("reception")
        page.get_by_role("button", name="Regenerar com IA").click()
        expect(page.locator("#message")).to_have_value(__import__("re").compile("encaminhar"))
        page.get_by_role("button", name="Aprovar e salvar versão").click()
        expect(page.locator("#message")).to_have_attribute("readonly", "")
        page.screenshot(path=str(OUT / "sdr-desktop.png"), full_page=True)
        page.get_by_role("button", name="TESTE Sem telefone").click()
        expect(page.locator("#whatsapp-help")).to_contain_text("Telefone não informado")
        expect(page.get_by_role("button", name="Abrir WhatsApp")).to_be_disabled()
        page.get_by_role("button", name="TESTE Telefone inválido").click()
        expect(page.locator("#whatsapp-help")).to_contain_text("inválido")
        page.get_by_role("button", name="TESTE Recusa").click()
        expect(page.get_by_role("button", name="Gerar abordagem com IA")).to_be_disabled()
        expect(page.locator("#whatsapp-help")).to_contain_text("Contato bloqueado")
        page.get_by_role("button", name="TESTE Clínica Árvore").click()
        expect(page.get_by_text(text, exact=True).first).to_be_visible()  # saved by dirty guard
        page.locator("#instruction").fill("falha simulada")
        page.get_by_role("button", name="Gerar abordagem com IA").click()
        expect(page.locator("p[role=alert]")).to_contain_text("Não foi possível gerar")
        assert "synthetic-sensitive-value" not in page.content()
        page.locator("#instruction").fill("")
        page.get_by_role("button", name="Gerar abordagem com IA").click()
        expect(page.locator("#message")).not_to_have_value("")
        page.get_by_role("button", name="Salvar texto revisado").click()
        expect(page.get_by_text("Texto revisado salvo no histórico.")).to_be_visible()
        # Search has real pagination semantics and the selection stays attached to its lead.
        page.locator("#lead-search").fill("nenhum resultado")
        expect(page.get_by_text("Nenhum lead encontrado")).to_be_visible()
        page.locator("#lead-search").fill("Clínica")
        expect(page.get_by_text("1 leads encontrados")).to_be_visible()
        for width in (1024, 768, 390):
            page.set_viewport_size({"width":width,"height":900})
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), f"Horizontal overflow at {width}"
            page.screenshot(path=str(OUT / f"sdr-{width}.png"), full_page=True)
        page.locator("#recipient").focus()
        assert page.locator("#recipient").evaluate("el => getComputedStyle(el).outlineStyle") != "none"
        saved_text = page.locator("#message").input_value()
        page.locator("#message").fill(saved_text + " Edição pendente.")
        page.get_by_role("button", name="Regenerar com IA").click()
        dialog = page.get_by_role("dialog")
        expect(dialog).to_be_visible()
        bounds = dialog.bounding_box()
        assert bounds["x"] >= 0 and bounds["x"] + bounds["width"] <= 390
        page.keyboard.press("Escape")
        expect(dialog).not_to_be_visible()
        expect(page.locator("#message")).to_have_value(saved_text + " Edição pendente.")
        page.evaluate("Object.defineProperty(navigator.clipboard, 'writeText', {value: async () => {throw new Error('offline clipboard failure')}})")
        page.get_by_role("button", name="Copiar mensagem", exact=True).click()
        expect(page.locator("p[role=alert]")).to_contain_text("Não foi possível copiar")
        page.locator("#message").fill(saved_text)
        # BFF rejects untrusted origins and malformed body; no generation triggered.
        response = context.request.post("http://127.0.0.1:3100/api/sdr/generate", data={"leadId":1})
        assert response.status == 422
        response = context.request.post("http://127.0.0.1:3100/api/sdr/generate", data={"leadId":1}, headers={"Origin":"https://external.example"})
        assert response.status == 403
        assert not errors, errors
        assert metrics()["backups"] == 1
        browser.close()
    print("SDR offline: seleção, classificação, geração, revisão, proteção, histórico, cópia, URL WhatsApp e 4 resoluções aprovados.")
    print(f"Capturas: {OUT}")


if __name__ == "__main__":
    main()
