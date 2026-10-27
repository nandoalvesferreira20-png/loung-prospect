"""End-to-end Auth/BFF/FastAPI/PostgreSQL with generated synthetic credentials."""
import json
import re
from urllib.request import urlopen
from urllib.parse import urlsplit
from pathlib import Path
from uuid import uuid4
from playwright.sync_api import sync_playwright,expect
BASE='http://127.0.0.1:3100'

def main():
    with urlopen('http://127.0.0.1:8100/__test/config') as response:config=json.load(response)
    assert config['signature']=='phase31-synthetic-only'
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='msedge',headless=True)
        ctx=browser.new_context(viewport={'width':1440,'height':1000})
        errors=[]
        def local(route):
            assert urlsplit(route.request.url).hostname in ('127.0.0.1','localhost')
            route.continue_()
        ctx.route('**/*',local)
        page=ctx.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
        print("protected redirect",flush=True);page.goto(BASE+'/pipeline');expect(page).to_have_url(BASE+'/login?expired=1')
        assert ctx.request.get(BASE+'/api/leads').status==401
        page.get_by_label('E-mail',exact=True).fill(config['email']);page.get_by_label('Senha',exact=True).fill('incorrect')
        page.get_by_role('button',name='Entrar',exact=True).click();expect(page.get_by_role('status')).to_contain_text('E-mail ou senha inválidos')
        page.get_by_label('Senha',exact=True).fill(config['password']);page.get_by_role('button',name='Entrar',exact=True).click()
        print('signed in',flush=True);expect(page.get_by_text(re.compile('Browser QA.*Synthetic browser workspace'))).to_be_visible(timeout=30000)
        print('pipeline',flush=True);page.goto(BASE+'/pipeline');expect(page.get_by_role('link',name='SYNTHETIC browser lead',exact=True)).to_be_visible(timeout=30000)
        page.reload();expect(page.get_by_role('link',name='SYNTHETIC browser lead',exact=True)).to_be_visible()
        for width in (1440,1024,390):
            page.set_viewport_size({'width':width,'height':900});assert page.locator('body').evaluate('(e)=>e.scrollWidth<=innerWidth')
        page.set_viewport_size({'width':1440,'height':1000})
        page.get_by_role('link',name='SYNTHETIC browser lead',exact=True).click()
        note='Observação sintética '+uuid4().hex
        page.get_by_label('Descrição',exact=True).fill(note)
        page.get_by_role('button',name='Registrar atividade',exact=True).click()
        expect(page.get_by_text(note,exact=True)).to_be_visible()
        expect(page.locator('li').filter(has_text=note).get_by_text(re.compile('Browser QA'))).to_be_visible()
        out=Path(__file__).resolve().parents[2]/'backend/.phase31-visual'
        out.mkdir(exist_ok=True)
        page.screenshot(path=str(out/'authenticated-profile.png'),full_page=True)
        print('logout',flush=True);page.get_by_role('button',name='Sair',exact=True).click();expect(page).to_have_url(BASE+'/login')
        assert ctx.request.get(BASE+'/api/leads').status==401
        page.goto(BASE+'/recuperar-senha');page.wait_for_load_state('networkidle');page.get_by_label('E-mail',exact=True).fill(config['email']);page.get_by_role('button',name='Enviar instruções').click()
        expect(page.get_by_role('status')).to_contain_text('receberá instruções')
        page.goto(BASE+'/login');page.get_by_label('E-mail',exact=True).fill(config['outsider']);page.get_by_label('Senha',exact=True).fill(config['password']);page.get_by_role('button',name='Entrar',exact=True).click()
        expect(page.get_by_role('heading',name='Acesso indisponível')).to_be_visible(timeout=30000)
        expect(page.get_by_role('alert').filter(has_text='membership')).to_be_visible()
        assert not errors,errors
        browser.close()
    print('Auth browser: login/logout, persistence, route/BFF protection, recovery, nonmember, CRM and responsive layouts passed')
if __name__=='__main__':main()
