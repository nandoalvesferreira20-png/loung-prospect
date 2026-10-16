"""CRM browser validation against an explicitly synthetic temporary DB only."""
from pathlib import Path
from urllib.parse import urlsplit
import json
import re
import urllib.request
from playwright.sync_api import sync_playwright, expect

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/"backend/.phase24-visual"
BASE="http://127.0.0.1:3100"
API="http://127.0.0.1:8100"


def main():
    with urllib.request.urlopen(API+"/__test/metrics") as response:
        assert json.load(response)["signature"] == "phase24-synthetic-only"
    OUT.mkdir(exist_ok=True)
    errors=[]
    with sync_playwright() as p:
        browser=p.chromium.launch(channel="msedge",headless=True)
        context=browser.new_context(viewport={"width":1440,"height":1000})
        assert context.request.post(API+"/__test/reset").ok
        def local(route):
            assert urlsplit(route.request.url).hostname in {"127.0.0.1","localhost"}, "External browser request forbidden"
            route.continue_()
        context.route("**/*",local)
        page=context.new_page()
        page.on("pageerror",lambda error:errors.append(str(error)))
        page.goto(BASE+"/pipeline")
        expect(page.get_by_role("link",name="TESTE Novo 01",exact=True)).to_be_visible()
        expect(page.get_by_role("link",name="TESTE Novo 09",exact=True)).to_have_count(0)
        page.get_by_role("button",name="Carregar mais").click()
        expect(page.get_by_role("link",name="TESTE Novo 09",exact=True)).to_have_count(1)
        expect(page.get_by_role("heading",name="Etapa especial",exact=True)).to_have_count(1)
        page.get_by_role("combobox",name="Mover TESTE Novo 01",exact=True).select_option("Em conversa")
        expect(page.get_by_role("status")).to_contain_text("etapa alterada")
        expect(page.get_by_role("region",name="Etapas do pipeline").get_by_role("combobox",name="Mover TESTE Novo 01",exact=True)).to_have_value("Em conversa")
        # A concurrent desktop edit causes a safe rollback of the optimistic card.
        assert context.request.post(API+"/__test/conflict/2").ok
        page.get_by_role("combobox",name="Mover TESTE Novo 02",exact=True).select_option("Em conversa")
        expect(page.get_by_role("alert").filter(has_text="movimentação visual")).to_be_visible()
        expect(page.get_by_role("combobox",name="Mover TESTE Novo 02",exact=True)).to_have_value("Novo")
        page.get_by_role("button",name="Atualizar quadro").click()
        expect(page.get_by_role("status")).not_to_contain_text("Carregando")
        # Native mouse drag has the same mutation contract as the keyboard select.
        card=page.locator("li[draggable=true]").filter(has=page.get_by_role("link",name="TESTE Novo 03",exact=True))
        target=page.get_by_role("region",name="Etapas do pipeline").locator("section").filter(has=page.get_by_role("heading",name="Contato realizado",exact=True))
        page.get_by_role("region",name="Etapas do pipeline").evaluate("element => element.scrollLeft=0")
        expect(page.get_by_role("combobox",name="Mover TESTE Novo 03",exact=True)).to_be_enabled()
        page.once("dialog",lambda dialog:dialog.accept())
        card.drag_to(target)
        expect(page.get_by_role("combobox",name="Mover TESTE Novo 03",exact=True)).to_have_value("Contato realizado")
        expect(page.get_by_role("combobox",name="Mover TESTE Novo 03",exact=True)).to_be_enabled()
        for width in (1440,1024,390):
            page.set_viewport_size({"width":width,"height":1000})
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), f"Pipeline overflow {width}"
            page.screenshot(path=str(OUT/f"pipeline-{width}.png"),full_page=True)
        page.set_viewport_size({"width":1440,"height":1000})
        page.get_by_label("Buscar empresa").fill("TESTE Personalizado")
        expect(page.get_by_role("status")).to_contain_text("1 leads")
        page.get_by_label("Buscar empresa").fill("sem resultado")
        expect(page.get_by_role("status")).to_contain_text("0 leads")
        page.goto(BASE+"/leads/13")
        expect(page.get_by_role("heading",name="TESTE Legado",exact=True)).to_be_visible()
        expect(page.get_by_role("navigation",name="Navegação principal").get_by_role("link",name="Leads",exact=True)).to_have_attribute("aria-current","location")
        expect(page.get_by_text("Observação anterior preservada",exact=True).first).to_be_visible()
        page.get_by_label("Descrição",exact=True).fill("Observação adicionada no teste offline")
        page.get_by_label("Etapa atual",exact=True).select_option("Proposta enviada")
        page.get_by_role("button",name="Salvar etapa",exact=True).click()
        expect(page.get_by_role("status").filter(has_text="Etapa alterada")).to_be_visible()
        expect(page.get_by_label("Descrição",exact=True)).to_have_value("Observação adicionada no teste offline")
        page.get_by_role("button",name="Registrar atividade",exact=True).click()
        expect(page.get_by_role("status").filter(has_text="Atividade registrada")).to_be_visible()
        expect(page.get_by_text("Observação adicionada no teste offline",exact=True)).to_be_visible()
        page.get_by_label("Tipo de atividade").select_option("Contato realizado")
        page.get_by_label("Descrição",exact=True).fill("Contato confirmado manualmente")
        expect(page.get_by_role("button",name="Registrar atividade",exact=True)).to_be_disabled()
        page.get_by_role("checkbox",name="Confirmo que esta atividade realmente ocorreu").check()
        page.get_by_role("button",name="Registrar atividade",exact=True).click()
        expect(page.get_by_text("Contato confirmado manualmente",exact=True)).to_be_visible()
        page.get_by_label("Data e horário locais").fill("2026-12-20T10:30")
        page.get_by_label("Próxima ação / observação").fill("Revisar proposta na próxima conversa")
        page.get_by_role("button",name="Salvar retorno",exact=True).click()
        expect(page.get_by_role("status").filter(has_text="Retorno salvo")).to_be_visible()
        page.get_by_label("Data e horário locais").fill("2026-12-21T11:30")
        page.get_by_role("button",name="Salvar retorno",exact=True).click()
        expect(page.get_by_text(re.compile("Follow-up reagendado"),exact=False).first).to_be_visible()
        page.screenshot(path=str(OUT/"profile-1440.png"),full_page=True)
        page.set_viewport_size({"width":390,"height":900})
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), "Profile overflow"
        page.screenshot(path=str(OUT/"profile-390.png"),full_page=True)
        page.get_by_role("button",name="Concluir follow-up",exact=True).click()
        expect(page.get_by_role("status").filter(has_text="Follow-up concluído")).to_be_visible()
        expect(page.get_by_role("button",name="Concluir follow-up",exact=True)).to_be_disabled()
        page.goto(BASE+"/sdr?leadId=1")
        expect(page.get_by_role("heading",name="TESTE Novo 01",exact=True)).to_be_visible()
        page.goto(BASE+"/meu-dia")
        expect(page.get_by_role("heading",name="Meu Dia",exact=True).first).to_be_visible()
        expect(page.get_by_role("link",name="TESTE Novo 02",exact=True)).to_be_visible()
        page.screenshot(path=str(OUT/"my-day-390.png"),full_page=True)
        page.goto(BASE+"/")
        expect(page.get_by_role("region",name="Indicadores comerciais")).to_be_visible()
        expect(page.get_by_text("Contato registrado",exact=True)).to_be_visible()
        assert context.request.get(BASE+"/api/dashboard/commercial").json()["contacted"] == 2
        assert context.request.patch(BASE+"/api/leads/1/stage",data={"stage":"Novo"}).status == 422
        assert context.request.get(BASE+"/api/pipeline",headers={"Origin":"https://external.example"}).status == 403
        assert context.request.get(API+"/__test/metrics").json()["backups"] == 1
        assert not errors,errors
        browser.close()
    print("CRM offline aprovado: paginação, filtros, teclado, drag-and-drop, rollback concorrente, atividades, confirmação, retorno/reagendamento/conclusão, perfil, SDR, Meu Dia e indicadores.")
    print(f"Capturas: {OUT}")


if __name__ == "__main__": main()
