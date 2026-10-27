"""Actual browser QA, restricted to synthetic loopback Auth/API/PostgreSQL."""
import json
from pathlib import Path
from urllib.request import urlopen
from urllib.parse import urlsplit
from uuid import uuid4
from playwright.sync_api import sync_playwright,expect

BASE='http://127.0.0.1:3100'

def main():
    with urlopen('http://127.0.0.1:8100/__test/config') as response:config=json.load(response)
    assert config['signature']=='phase31-synthetic-only'
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='msedge',headless=True)
        context=browser.new_context(viewport={'width':1440,'height':1000})
        errors=[]
        def local(route):
            assert urlsplit(route.request.url).hostname in ('127.0.0.1','localhost')
            route.continue_()
        context.route('**/*',local)
        page=context.new_page();page.on('pageerror',lambda error:errors.append(str(error)))
        page.goto(BASE+'/login')
        page.get_by_label('E-mail',exact=True).fill(config['email'])
        page.get_by_label('Senha',exact=True).fill(config['password'])
        page.get_by_role('button',name='Entrar',exact=True).click()
        page.wait_for_url(BASE+'/',timeout=30000)
        page.goto(BASE+'/configuracoes/equipe')
        expect(page.get_by_role('heading',name='Equipe',exact=True)).to_be_visible()
        expect(page.locator('tbody tr')).to_have_count(4,timeout=30000)
        page.on('dialog',lambda dialog:dialog.accept())
        row=page.locator('tr').filter(has_text='qa1@example.invalid')
        row.get_by_role('combobox').select_option('member')
        expect(row.get_by_role('combobox')).to_have_value('member')
        page.reload();expect(row.get_by_role('combobox')).to_have_value('member')
        for width in (1440,1024,390):
            page.set_viewport_size({'width':width,'height':900})
            assert page.locator('body').evaluate('(e)=>e.scrollWidth<=innerWidth')
        out=Path(__file__).resolve().parents[2]/'backend/.phase32-visual';out.mkdir(exist_ok=True)
        page.screenshot(path=str(out/'team-mobile.png'),full_page=True)
        page.set_viewport_size({'width':1440,'height':1000})
        page.goto(BASE+'/leads/novo')
        company='Synthetic manual QA '+uuid4().hex
        page.get_by_label('Empresa',exact=True).fill(company)
        page.get_by_label('Telefone',exact=True).fill('synthetic')
        page.get_by_role('button',name='Salvar lead',exact=True).click()
        page.wait_for_url(BASE+'/leads')
        page.get_by_role('link',name=company,exact=True).click()
        page.get_by_role('link',name='Editar dados e contato').click()
        phone=page.get_by_label('Telefone',exact=True)
        expect(phone).to_have_value('synthetic')
        phone.fill('synthetic-updated')
        page.get_by_role('button',name='Salvar lead',exact=True).click()
        page.wait_for_url(lambda url:not str(url).endswith('/editar'))
        page.get_by_role('link',name='Editar dados e contato').click()
        expect(page.get_by_label('Telefone',exact=True)).to_have_value('synthetic-updated')
        page.goto(BASE+'/configuracoes/atividades')
        expect(page.get_by_text('Lead atualizado',exact=True)).to_be_visible()
        expect(page.get_by_text('Papel de integrante alterado',exact=True).first).to_be_visible()
        page.screenshot(path=str(out/'activities-desktop.png'),full_page=True)
        assert not errors,errors
        browser.close()
    print('PASS synthetic browser: team, roles, responsive layout, lead create/edit, audit')

if __name__=='__main__':main()
