"""Run against local_fixture_server on 8138 and a local Next build on 3138."""
from playwright.sync_api import sync_playwright
from urllib.parse import urlparse
import json,time
base="http://127.0.0.1:3138"
with sync_playwright() as p:
    browser=p.chromium.launch(channel="msedge",headless=True)
    page=browser.new_page(viewport={"width":1440,"height":1000})
    errors=[]
    page.on("pageerror",lambda e:errors.append(str(e)))
    def route(r):
        assert urlparse(r.request.url).hostname in ("127.0.0.1","localhost"),r.request.url
        r.continue_()
    page.route("**/*",route)
    page.goto(base+"/",wait_until="networkidle")
    assert page.url==base+"/"
    assert page.request.get(base+"/api/session").json()["role"]=="local"
    initial=page.request.get(base+"/api/leads").json()["total"]
    assert initial==0, "Restart synthetic fixture before this test"
    page.goto(base+"/leads/novo",wait_until="networkidle")
    page.get_by_label("Empresa",exact=True).fill("Synthetic browser company")
    page.get_by_label("Telefone",exact=True).fill("11999990000")
    page.get_by_role("button",name="Salvar lead",exact=True).click()
    page.wait_for_url(base+"/leads")
    page.get_by_text("Synthetic browser company",exact=True).wait_for()
    assert page.request.get(base+"/api/leads").json()["total"]==1
    for path in ["/pipeline","/meu-dia","/sdr","/configuracoes"]:
        page.goto(base+path,wait_until="networkidle")
        assert page.url==base+path
    prefs={"values":{"displayName":"Synthetic browser user","startPage":"/pipeline"}}
    assert page.request.put(base+"/api/local/preferences",data=prefs).status==200
    assert page.request.get(base+"/api/local/preferences").json()==prefs
    page.goto(base+"/login",wait_until="networkidle")
    assert page.url==base+"/"
    result=page.request.post(base+"/api/prospecting/search",data={"niche":"Synthetic clinics","location":"Synthetic City","quantity":1})
    assert result.status==202,result.text()
    job=result.json()["id"]
    for _ in range(50):
        status=page.request.get(base+"/api/prospecting/search/"+job).json()
        if status["status"] in ("completed","failed"):break
        time.sleep(.1)
    assert status["status"]=="completed",status
    for fmt in ("csv","xlsx"):
        result=page.request.get(base+"/api/prospecting/search/"+job+"/export?format="+fmt)
        assert result.status==200,result.text()
    page.screenshot(path="temp/local-dashboard-browser.png",full_page=True)
    assert not errors,errors
    print(json.dumps({"dashboard":"direct without login","CRUD":"browser create persisted","navigation":"pipeline/day/sdr/settings","preferences":"SQLite via BFF","places":"mocked search and CSV/XLSX","browserErrors":errors}))
    browser.close()
