"""Browser regression using only sdr_fixture_server and simulated Groq.

Start the synthetic backend on 8100 and the web app on 3100 pointing to it.
Run with a Python environment containing Playwright and Edge installed.
"""
import json
import urllib.request
from urllib.parse import parse_qs, urlsplit

from playwright.sync_api import sync_playwright, expect


def main():
    with urllib.request.urlopen('http://127.0.0.1:8100/__test/metrics') as response:
        assert json.load(response)['signature'] == 'phase23-synthetic-only'
    with sync_playwright() as p:
        browser = p.chromium.launch(channel='msedge', headless=True)
        context = browser.new_context(viewport={'width': 1440, 'height': 1000})
        whatsapp = []

        def intercept(route):
            url = urlsplit(route.request.url)
            if url.hostname in {'127.0.0.1', 'localhost'}:
                route.continue_()
            elif url.hostname == 'wa.me':
                whatsapp.append(route.request.url)
                route.fulfill(body='Synthetic WhatsApp interception')
            else:
                route.abort()

        context.route('**/*', intercept)
        page = context.new_page()
        requests = []
        page.on('request', lambda request: requests.append(request.url))
        page.goto('http://127.0.0.1:3100/sdr')
        expect(page.get_by_text('5 leads encontrados', exact=True)).to_be_visible()
        expect(page.locator('#lead-niche')).to_have_value('')
        page.locator('#lead-niche').select_option(label='Clínica odontológica')
        expect(page.get_by_text('1 leads encontrados', exact=True)).to_be_visible()
        page.locator('#lead-search').fill('inexistente')
        expect(page.get_by_text('Nenhum lead encontrado', exact=True)).to_be_visible()
        expect(page.get_by_text('Nenhum lead deste nicho corresponde aos filtros.', exact=False)).to_be_visible()
        page.locator('#lead-search').fill('Árvore')
        expect(page.get_by_text('1 leads encontrados', exact=True)).to_be_visible()
        page.locator('#lead-stage').select_option(label='Fechado')
        expect(page.get_by_text('0 leads encontrados', exact=True)).to_be_visible()
        page.locator('#lead-stage').select_option(label='Novo')
        expect(page.get_by_text('1 leads encontrados', exact=True)).to_be_visible()
        page.get_by_role('button', name='TESTE Clínica Árvore').click()
        expect(page.locator('#recipient')).to_be_visible()
        initial = [url for url in requests if '/api/leads?' in url or '/api/lead-niches' in url]
        page.get_by_role('button', name='Gerar abordagem com IA').click()
        expect(page.locator('#message')).not_to_have_value('')
        expect(page.locator('#lead-niche')).to_have_value('Clínica odontológica')
        text = page.locator('#message').input_value() + ' Revisão sintética.'
        page.locator('#message').fill(text)
        page.get_by_role('button', name='Salvar texto revisado').click()
        expect(page.get_by_text('Texto revisado salvo no histórico.', exact=True)).to_be_visible()
        expect(page.locator('#lead-search')).to_have_value('Árvore')
        expect(page.locator('#lead-stage')).to_have_value('Novo')
        assert initial == [url for url in requests if '/api/leads?' in url or '/api/lead-niches' in url]
        with page.expect_popup() as popup:
            page.get_by_role('link', name='Abrir WhatsApp').click()
        popup.value.wait_for_load_state()
        assert parse_qs(urlsplit(whatsapp[0]).query)['text'] == [text]
        popup.value.close()
        page.locator('#message').fill(text + ' Pendente.')
        page.locator('#lead-niche').select_option(label='Fotógrafos')
        expect(page.get_by_role('dialog')).to_be_visible()
        page.get_by_role('button', name='Continuar editando', exact=True).click()
        expect(page.locator('#lead-niche')).to_have_value('Clínica odontológica')
        page.locator('#message').fill(text)
        page.locator('#lead-niche').select_option(label='Todos os nichos')
        expect(page.get_by_text('Escolha com quem conversar', exact=True)).to_be_visible()
        expect(page.get_by_text('1 leads encontrados', exact=True)).to_be_visible()
        for width in (1024, 768, 390):
            page.set_viewport_size({'width': width, 'height': 900})
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        browser.close()
    print('SDR niche browser regression passed (synthetic data, simulated Groq, intercepted WhatsApp).')


if __name__ == '__main__':
    main()
