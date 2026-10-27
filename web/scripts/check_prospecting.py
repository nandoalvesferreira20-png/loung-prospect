"""Real BFF/FastAPI/SQLite flow, with mock Google transport and temporary DB."""
from pathlib import Path
import json
import sys
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright

base=sys.argv[1] if len(sys.argv)>1 else "http://127.0.0.1:3100"
api=sys.argv[2] if len(sys.argv)>2 else "http://127.0.0.1:8100"
assert all(urlparse(url).hostname in {"localhost","127.0.0.1"} for url in [base,api])
out=Path(__file__).resolve().parents[1]/"test-results"
out.mkdir(exist_ok=True)
with sync_playwright() as p:
    browser=p.chromium.launch(channel="msedge",headless=True)
    page=browser.new_page(accept_downloads=True,viewport={"width":1440,"height":1000})
    errors=[]
    page.on("pageerror",lambda error:errors.append(str(error)))
    assert page.request.get(api+"/__test/metrics").json()["signature"]=="phase22-synthetic-only"
    if '--auth' in sys.argv:
        config=page.request.get('http://127.0.0.1:8112/__test/config').json()
        assert config['signature']=='auth-session-no-database'
        page.goto(base+'/login')
        page.get_by_label('E-mail',exact=True).fill('test@example.invalid')
        page.get_by_label('Senha',exact=True).fill(config['password'])
        page.get_by_role('button',name='Entrar',exact=True).click()
        page.get_by_text('Synthetic Workspace',exact=True).first.wait_for(timeout=30000)
    assert page.request.get(base+"/api/leads").json()["total"]==1
    def local_only(route):
        assert urlparse(route.request.url).hostname in {"localhost","127.0.0.1"}, "External request forbidden"
        route.continue_()
    page.context.route("**/*",local_only)
    query={"niche":"Teste Clínicas","location":"São Paulo, SP","quantity":25}
    assert page.request.post(base+"/api/prospecting/search",data={**query,"quantity":101}).status==422
    assert page.request.get(api+"/__test/metrics").json()["calls"]==0
    page.goto(base+"/prospeccao",wait_until="networkidle")
    page.get_by_role("button",name="Iniciar pesquisa").click()
    page.get_by_text("Informe um nicho com pelo menos 2 caracteres.",exact=True).wait_for()
    page.get_by_label("Nicho ou segmento",exact=True).fill(query["niche"])
    page.get_by_label("Localização",exact=True).fill(query["location"])
    page.get_by_label("Quantidade máxima",exact=True).fill("25")
    page.get_by_role("button",name="Iniciar pesquisa").click()
    page.get_by_text("Concluída",exact=True).wait_for()
    page.get_by_text("Teste empresa 01 — São Paulo",exact=True).wait_for()
    assert page.get_by_role("checkbox",name="Selecionar Teste empresa 01 — São Paulo",exact=True).is_disabled()
    page.get_by_role("button",name="Próxima página").click()
    page.get_by_role("checkbox",name="Selecionar Teste empresa 21 — São Paulo",exact=True).check()
    page.get_by_role("button",name="Página anterior").click()
    page.get_by_role("checkbox",name="Selecionar Teste empresa 02 — São Paulo",exact=True).check()
    page.get_by_text("2 selecionado(s)",exact=False).wait_for()
    for format,label in [("csv","CSV"),("xlsx","Excel")]:
        with page.expect_download() as pending:page.get_by_role("button",name=label,exact=True).click()
        download=pending.value
        download.save_as(out/f"phase22-export.{format}")
    assert "São Paulo" in (out/"phase22-export.csv").read_text("utf-8-sig")
    page.get_by_role("button",name="Salvar selecionados").click()
    page.get_by_text("2 lead(s) salvo(s).",exact=False).wait_for()
    first_job=page.evaluate("sessionStorage.getItem('loung:prospecting:active')")
    assert page.request.post(base+'/api/leads/import',data={'searchId':first_job,'resultIds':[2]}).json()=={'inserted':0,'duplicates':1}
    assert page.request.get(base+"/api/leads").json()["total"]==3
    assert page.request.get(api+"/__test/metrics").json()["backups"]==1
    page.goto(base+"/leads",wait_until="networkidle")
    page.get_by_text("Teste empresa 21 — São Paulo",exact=True).wait_for()
    page.goto(base+"/prospeccao",wait_until="networkidle")
    page.get_by_text("Concluída",exact=True).wait_for()
    page.get_by_text("Teste empresa 02 — São Paulo",exact=True).wait_for()
    assert page.get_by_label("Localização",exact=True).input_value()==query["location"]
    assert page.get_by_role("checkbox",name="Selecionar Teste empresa 02 — São Paulo",exact=True).is_disabled()
    for width,height in [(1440,1000),(1024,768),(390,844)]:
        page.set_viewport_size({"width":width,"height":height})
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"),f"Overflow at {width}"
        page.screenshot(path=str(out/f"phase22-prospecting-{width}.png"),full_page=True)
    page.set_viewport_size({"width":1440,"height":1000})
    page.get_by_label("Nicho ou segmento",exact=True).fill("Falha simulada")
    page.get_by_role("button",name="Iniciar pesquisa").click()
    page.get_by_text("Interrompida",exact=True).wait_for()
    assert "synthetic-sensitive-value" not in page.locator("body").inner_text()
    page.get_by_label("Nicho ou segmento",exact=True).fill("Cancelamento simulado")
    page.get_by_role("button",name="Iniciar pesquisa").click()
    page.get_by_text("Teste empresa 20 — São Paulo",exact=True).wait_for()
    page.get_by_role("button",name="Cancelar pesquisa",exact=True).click()
    page.get_by_text("Cancelada",exact=True).wait_for()
    page.get_by_text("Teste empresa 20 — São Paulo",exact=True).wait_for()
    assert page.request.get(base+"/api/leads").json()["total"]==3
    assert page.request.get(base+"/api/prospecting/search/invalid").status==422
    assert page.request.post(base+"/api/prospecting/search",data=query,headers={"Origin":"https://external.example"}).status==403
    if '--auth' in sys.argv:
        # Results take longer than the 1.5s status poll. They must still render
        # while the second mock Places page is blocked, without being aborted.
        page.get_by_label('Nicho ou segmento',exact=True).fill('Lenta simulada')
        page.get_by_role('button',name='Iniciar pesquisa').click()
        page.get_by_text('Carregando resultados da pesquisa…',exact=True).wait_for(timeout=5000)
        page.get_by_text('Teste empresa 20 — São Paulo',exact=True).wait_for(timeout=7000)
        page.get_by_text('Pesquisando',exact=True).wait_for(timeout=1000)
        page.get_by_role('button',name='Cancelar pesquisa').click()
        page.get_by_text('Cancelada',exact=True).wait_for(timeout=15000)
        page.get_by_label('Nicho ou segmento',exact=True).fill('Vazia simulada')
        page.get_by_role('button',name='Iniciar pesquisa').click()
        page.get_by_text('Concluída',exact=True).wait_for(timeout=15000)
        page.get_by_text('Nenhum estabelecimento encontrado',exact=True).wait_for()
        assert page.request.get(base+'/api/leads').json()['total']==3
    assert not errors,errors
    report={"status":"passed","checks":["BFF parameter validation before provider call","mock Google pagination","existing lead detection","selection across pages","CSV and Excel downloads","selected-only import and backup","saved leads visible in portfolio","session resume","three responsive viewports","sanitized provider error","cooperative cancel preserves partial results","no implicit writes"],"javascript_errors":errors,"source":"synthetic fixture; no real Google calls or real database writes"}
    if '--auth' in sys.argv:
        report['checks'].extend(['Supabase cookie login and verified JWT','slow results render while job running','empty completed search message','duplicate selected import inserts zero'])
    (out/"phase22-report.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(json.dumps(report,indent=2))
    browser.close()
