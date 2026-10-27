"""Browser QA against the explicitly marked loopback-only Auth/API fixture."""
import json
from urllib.request import urlopen, Request
from urllib.parse import urlsplit
from playwright.sync_api import sync_playwright, expect

BASE = 'http://127.0.0.1:3198'
FIXTURE = 'http://127.0.0.1:8112'


def control(**state):
    with urlopen(Request(FIXTURE + '/__test/state', data=json.dumps(state).encode(),
                         headers={'Content-Type': 'application/json'})) as response:
        assert response.status == 200


def main():
    with urlopen(FIXTURE + '/__test/config') as response:
        config = json.load(response)
    assert config['signature'] == 'auth-session-no-database'
    with sync_playwright() as p:
        browser = p.chromium.launch(channel='msedge', headless=True)
        ctx = browser.new_context()
        ctx.set_default_navigation_timeout(90000)
        errors = []

        def local(route):
            assert urlsplit(route.request.url).hostname in ('localhost', '127.0.0.1')
            route.continue_()

        ctx.route('**/*', local)
        page = ctx.new_page()
        page.on('pageerror', lambda error: errors.append(type(error).__name__))
        page.goto(BASE + '/')
        expect(page).to_have_url(BASE + '/login?expired=1')
        assert ctx.request.get(BASE + '/api/session').status == 401
        page.get_by_label('E-mail', exact=True).fill('test@example.invalid')
        page.get_by_label('Senha', exact=True).fill('incorrect-password')
        page.get_by_role('button', name='Entrar', exact=True).click()
        expect(page.get_by_role('status')).to_contain_text('E-mail ou senha')
        assert not ctx.cookies()
        page.get_by_label('Senha', exact=True).fill(config['password'])
        page.get_by_role('button', name='Entrar', exact=True).click()
        expect(page.get_by_text('Synthetic Workspace', exact=True).first).to_be_visible(timeout=30000)
        assert page.url == BASE + '/'
        assert ctx.request.get(BASE + '/api/session').status == 200
        page.reload()
        expect(page.get_by_text('Synthetic Workspace', exact=True).first).to_be_visible(timeout=30000)
        # Host-only cookies intentionally do not authenticate a different hostname.
        assert ctx.request.get('http://localhost:3198/api/session').status == 401
        control(backend=False)
        assert ctx.request.get(BASE + '/api/session').status == 503
        control(backend=True, auth=False)
        failure = ctx.request.get(BASE + '/', max_redirects=0)
        assert failure.status == 503
        assert failure.headers.get('x-request-id')
        control(auth=True)
        page.goto(BASE + '/')
        expect(page.get_by_text('Synthetic Workspace', exact=True).first).to_be_visible(timeout=30000)
        page.get_by_role('button', name='Sair', exact=True).first.click()
        expect(page).to_have_url(BASE + '/login')
        assert ctx.request.get(BASE + '/api/session').status == 401
        assert not errors, errors
        with urlopen(FIXTURE + '/__test/config') as response:
            assert json.load(response)['verified'] > 0  # Real JWT verifier in fixture API.
        browser.close()
    print('PASS: invalid/valid login, Dashboard, reload, host-only cookies, logout, redirects, Auth/API outage; synthetic only, no database')


if __name__ == '__main__':
    main()
