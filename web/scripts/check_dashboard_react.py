"""Dashboard regression against the loopback-only, no-database Auth/API fixture."""
import json
import sys
from urllib.request import urlopen
from urllib.parse import urlsplit
from playwright.sync_api import sync_playwright, expect

BASE = 'http://127.0.0.1:3198'
FIXTURE = 'http://127.0.0.1:8112'


def main():
    expect.set_options(timeout=90000)
    with urlopen(FIXTURE + '/__test/config') as response:
        config = json.load(response)
    assert config['signature'] == 'auth-session-no-database'
    errors = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel='msedge', headless=True)
        context = browser.new_context()
        def local_only(route):
            assert urlsplit(route.request.url).hostname in ('localhost', '127.0.0.1')
            route.continue_()
        context.route('**/*', local_only)
        page = context.new_page()
        page.set_default_timeout(90000)
        page.on('pageerror', lambda error: errors.append(error.stack))
        page.on('console', lambda message: errors.append(message.text)
                if message.type == 'error' and ('use()' in message.text or 'hydration' in message.text.lower()) else None)
        page.goto(BASE + '/')
        page.get_by_label('E-mail', exact=True).fill('test@example.invalid')
        page.get_by_label('Senha', exact=True).fill(config['password'])
        navigations=[]
        page.on('request', lambda request: navigations.append(1)
                if urlsplit(request.url).path == '/' and '_rsc=' in request.url else None)
        page.get_by_role('button', name='Entrar', exact=True).click()
        expect(page.get_by_text('Synthetic Workspace', exact=True).first).to_be_visible(timeout=90000)
        if '--development' not in sys.argv:
            assert len(navigations)==1, 'Login must initiate one RSC navigation without concurrent refresh'
        for path in ['/leads', '/', '/pipeline', '/']:
            page.locator('nav').first.locator('a[href="' + path + '"]').click()
            expect(page).to_have_url(BASE + path)
            page.wait_for_timeout(1500)
        page.reload()
        expect(page.get_by_text('Synthetic Workspace', exact=True).first).to_be_visible(timeout=90000)
        expect(page.get_by_role('list', name='Leads por etapa')).to_be_attached()
        page.set_viewport_size({'width': 800, 'height': 900})
        page.get_by_role('button', name='Abrir navegação').click()
        expect(page.get_by_role('dialog')).to_be_visible()
        page.get_by_role('button', name='Fechar navegação').click()
        expect(page.get_by_role('dialog')).not_to_be_visible()
        for path in ('/api/session', '/api/overview', '/api/followups', '/api/dashboard/commercial'):
            response = context.request.get(BASE + path)
            assert response.status == 200
            timing = response.headers.get('server-timing', '')
            assert 'bff_auth;dur=' in timing and 'bff_upstream;dur=' in timing
            print(json.dumps({'route': path, 'server_timing': timing,
                              'proxy_auth_ms': response.headers.get('x-loung-proxy-auth-ms')}))
        # An API outage must remain distinct from expiration.
        page.route('**/api/session', lambda route: route.fulfill(status=503, json={'detail': 'Synthetic outage'}))
        page.reload()
        expect(page.get_by_role('alert').filter(has_text='Synthetic outage')).to_have_text('Synthetic outage')
        assert page.url == BASE + '/'
        page.unroute('**/api/session')
        page.route('**/api/session', lambda route: route.fulfill(status=401, json={'detail': 'Synthetic expiration'}))
        page.reload()
        expect(page).to_have_url(BASE + '/login?expired=1')
        browser.close()
    assert not errors, json.dumps(errors, ensure_ascii=True, indent=2)
    print('PASS: login, Dashboard, Leads/Pipeline navigation, reload, timing headers, outage versus expiration; no React suspension/hydration errors; synthetic only')


if __name__ == '__main__':
    main()

