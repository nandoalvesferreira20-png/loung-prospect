"""Safe browser diagnostics: synthetic credentials and intercepted Auth traffic only.
Run against a dev server with public env vars overridden; never submits to real Supabase.
"""
import sys
from playwright.sync_api import sync_playwright,expect
mode=sys.argv[1]
with sync_playwright() as p:
    browser=p.chromium.launch(channel='msedge',headless=True)
    page=browser.new_page();calls=[]
    def route(request):
        url=request.request.url
        if '/auth/v1/token' in url:
            calls.append(True)
            request.fulfill(status=400,content_type='application/json',body='{"code":"invalid_credentials","msg":"Invalid login credentials"}')
        elif url.startswith('http://127.0.0.1:3199') or url.startswith('http://localhost:3199'):
            request.continue_()
        else:request.abort()
    page.route('**/*',route)
    response=page.goto('http://127.0.0.1:3199/login?expired=1')
    assert response.status==200
    page.get_by_label('E-mail',exact=True).fill('synthetic@example.invalid')
    page.get_by_label('Senha',exact=True).fill('synthetic-test-input')
    page.get_by_role('button',name='Entrar',exact=True).click()
    if mode=='missing':
        expect(page.get_by_role('status')).to_contain_text('web/.env.local')
        assert not calls
    else:
        expect(page.get_by_role('status')).to_contain_text('E-mail ou senha inválidos')
        assert len(calls)==1
        assert not page.context.cookies() # Invalid login must not create a session.
    browser.close()
print('Browser diagnosis passed: '+mode+'; Auth requests='+str(len(calls)))
