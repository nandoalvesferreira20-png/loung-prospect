"""End-to-end checks against backend.tests.fixture_server, never real records."""
from pathlib import Path
import json
import sys
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright

base = sys.argv[1] if len(sys.argv)>1 else "http://127.0.0.1:3100"
assert urlparse(base).hostname in {"localhost","127.0.0.1"}
out = Path(__file__).resolve().parents[1] / "test-results"
out.mkdir(exist_ok=True)
with sync_playwright() as p:
    browser=p.chromium.launch(channel="msedge",headless=True)
    page=browser.new_page()
    errors=[]
    page.on("pageerror",lambda error:errors.append(str(error)))
    context=page.context
    def local_only(route):
        assert urlparse(route.request.url).hostname in {"localhost","127.0.0.1"}, "External request blocked"
        route.continue_()
    context.route("**/*",local_only)
    # The fixture signature prevents accidental testing against the real DB.
    sample=page.request.get(base+"/api/leads").json()
    assert sample["total"]==24 and sample["items"][0]["company"]=="Teste empresa 01", "Start the synthetic fixture API first"
    for width,height in [(1440,1000),(1024,768),(390,844)]:
        page.set_viewport_size({"width":width,"height":height})
        for path in ["/","/leads"]:
            page.goto(base+path,wait_until="networkidle")
            page.get_by_text("Base local · somente leitura",exact=True).wait_for()
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), (path,width)
            if path=="/leads":
                page.get_by_text("Teste empresa 01",exact=True).wait_for()
            else:
                page.get_by_label("24",exact=True).wait_for()
            page.screenshot(path=str(out/f"phase21-{path.strip('/') or 'dashboard'}-{width}.png"),full_page=True)
    page.set_viewport_size({"width":1440,"height":1000})
    page.goto(base+"/leads",wait_until="networkidle")
    page.get_by_text("Teste empresa 01",exact=True).wait_for()
    page.get_by_role("button",name="Próxima página").click()
    page.get_by_text("Teste empresa 21",exact=True).wait_for()
    page.get_by_role("button",name="Página anterior").click()
    page.get_by_text("Teste empresa 01",exact=True).wait_for()
    page.get_by_label("Etapa",exact=True).select_option("Reunião agendada")
    page.get_by_text("1 lead(s) encontrado(s)",exact=False).wait_for()
    assert page.get_by_text("Teste empresa 02",exact=True).count()==0
    page.get_by_role("checkbox",name="Selecionar Teste empresa 01",exact=True).check()
    page.get_by_text("1 selecionado(s)",exact=False).wait_for()
    page.get_by_label("Etapa",exact=True).select_option("")
    page.get_by_label("Buscar lead",exact=True).fill("empresa 02")
    page.get_by_text("Teste empresa 02",exact=True).wait_for()
    page.get_by_text("Não informado",exact=True).first.wait_for()
    page.get_by_label("Buscar lead",exact=True).fill("sem correspondencia")
    page.get_by_text("Nenhum lead corresponde aos filtros",exact=True).wait_for()
    page.get_by_label("Buscar lead",exact=True).fill("")
    page.get_by_text("Teste empresa 01",exact=True).wait_for()
    # Exercise HTTP/BFF validation and same-origin restriction as well.
    assert page.request.get(base+"/api/leads?page=0").status==422
    assert page.request.get(base+"/api/leads",headers={"Origin":"https://external.example"}).status==403
    # Simulate network-level backend unavailability at the browser boundary.
    context.route("**/api/leads?*",lambda route:route.fulfill(status=503,json={"code":"API_UNAVAILABLE","detail":"API local indisponível — teste controlado."}))
    page.get_by_role("button",name="Atualizar",exact=True).click()
    page.get_by_role("alert").get_by_text("API local indisponível",exact=False).wait_for()
    context.unroute("**/api/leads?*")
    page.get_by_role("button",name="Tentar novamente",exact=True).click()
    page.get_by_text("Teste empresa 01",exact=True).wait_for()
    assert not errors,errors
    report={"status":"passed","viewports":["1440x1000","1024x768","390x844"],"checks":["real HTTP through Next BFF to fixture FastAPI","dashboard counts and chart","pagination","canonical stage filtering","selection","search","null fields","empty filters","HTTP 422","origin restriction","error and retry"],"javascript_errors":errors}
    (out/"phase21-report.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(json.dumps(report,indent=2))
    browser.close()
