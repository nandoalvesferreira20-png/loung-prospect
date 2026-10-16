"""Offline SDR layout, keyboard and WhatsApp regression with disposable SQLite."""
from contextlib import ExitStack
from pathlib import Path
import socket
import sys
import tempfile
import time
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main():
    import app
    from core.database import LeadRepository
    from core.database.connection import connect_database
    from core.database.outreach_repository import OutreachRepository
    from core.sales.models import SalesGeneration

    with tempfile.TemporaryDirectory() as directory, ExitStack() as stack:
        from ui.settings import UserSettings
        stack.enter_context(patch("ui.sales_workspace.UserSettings", lambda: UserSettings(Path(directory) / "settings.json")))
        repo = LeadRepository(Path(directory) / "sdr.db")
        names = ("Clínica São José — Unidade Centro", "Contato sem cadastro adicional", "Sem telefone", "Telefone inválido", "Sem rascunho")
        for i, name in enumerate(names, 1):
            segment = "Clínica odontológica" if i == 1 else "Corretor autônomo" if i == 2 else "Nicho desconhecido"
            repo.create_lead(dict(empresa=name, segmento=segment, telefone=None if i == 3 else "(11) 99999-1234"))
        saved = OutreachRepository(repo.path)
        for i in (1, 2, 3, 4):
            saved.create(i, SalesGeneration("Olá! Uma ideia para vocês?", "Presença digital", .8))
        from contextlib import closing
        with closing(connect_database(repo.path)) as connection, connection:
            connection.execute("UPDATE leads SET telefone='inválido' WHERE id=4")
        before = dict(repo.get_lead(1))
        for module in ("dashboard", "sales_workspace"):
            stack.enter_context(patch(f"ui.{module}.LeadRepository", lambda: repo))
        stack.enter_context(patch("app.load_environment", lambda: None))
        stack.enter_context(patch("ui.sales_workspace.create_groq_provider", lambda: Mock()))
        fake = Mock(generate=Mock(return_value=dict(mensagem="Novo rascunho sintético", angulo="Teste", confianca=.8)))
        stack.enter_context(patch("ui.sales_panel.create_sales_provider", lambda: fake))
        stack.enter_context(patch.object(socket.socket, "connect", side_effect=AssertionError("Network forbidden")))
        browser = stack.enter_context(patch("webbrowser.open", return_value=True))
        root = app.LoungLeadsApp()
        if "--show" not in sys.argv:
            root.attributes("-alpha", 0)
        errors, sizes = [], []
        root.report_callback_exception = lambda kind, error, tb: errors.append(f"{kind.__name__}: {error}")

        def pump(duration=.15):
            deadline = time.monotonic() + duration
            while time.monotonic() < deadline:
                root.update()
                time.sleep(.01)
            assert not errors, errors

        def wait_until(predicate):
            deadline = time.monotonic() + 12
            while not predicate() and time.monotonic() < deadline:
                pump(.05)
            assert predicate(), "UI operation timed out"

        def inside(widget, parent):
            assert widget.winfo_ismapped(), str(widget)
            assert widget.winfo_rooty() + widget.winfo_height() <= parent.winfo_rooty() + parent.winfo_height(), (str(widget), widget.winfo_height(), parent.winfo_height())
            assert widget.winfo_rootx() + widget.winfo_width() <= parent.winfo_rootx() + parent.winfo_width()

        try:
            root.show_sales()
            page = root.current_page
            wait_until(lambda: not page._load_busy and len(page.cards) == 5)
            assert page.browser_preference == "default"
            assert page.browser_selector.get() == "Navegador padrão do sistema"
            page.select_lead(1)
            pump()
            editor = page.editors[1]
            contact, sales = editor.contact, editor.sales
            assert sales.contact_type_selector.get() == "Recepção/equipe"
            for size in ("1280x760", "1050x650", "1440x900"):
                root.geometry(size)
                pump(.3)
                inside(contact.open_button, page)
                inside(page.browser_selector, page)
                inside(contact.notice, page)
                inside(sales.message, editor)
                inside(sales.contact_type_selector, editor)
                for control in sales.buttons:
                    if control.winfo_ismapped():
                        inside(control, sales)
                assert sales.message.winfo_height() >= 90, sales.message.winfo_height()
                sizes.append((size, sales.message.winfo_width(), sales.message.winfo_height()))
            sales.toggle_reason()
            pump()
            for control in sales.buttons:
                inside(control, sales)
            sales.toggle_reason()
            page.cards[1]._canvas.focus_force()
            pump()
            page.cards[1]._canvas.event_generate("<Down>")
            pump()
            assert root.focus_get() == page.cards[2]._canvas
            page.cards[2]._canvas.event_generate("<Return>")
            pump()
            assert page.selected_id == 2
            assert page.editors[2].sales.contact_type_selector.get() == "Contato direto"
            assert page.editors[2].contact.open_button.cget("state") == "normal"
            assert not {"consent", "source", "authorized_at"}.intersection(page.editors[2].contact.fields)
            for identity, hint in ((3, "Telefone não informado"), (4, "inválido"), (5, "Sem rascunho")):
                page.select_lead(identity)
                pump()
                assert page.editors[identity].contact.open_button.cget("state") == "disabled"
                assert hint in page.editors[identity].contact.notice.cget("text"), page.editors[identity].contact.notice.cget("text")
                assert page.editors[identity].sales.contact_type_selector.get() == "Indefinido"
            page.select_lead(1)
            pump()
            editor = page.editors[1]
            contact, sales = editor.contact, editor.sales
            message = "Olá, São José!\nPodemos conversar? Ideia & café + crescimento."
            sales.message.delete("1.0", "end")
            sales.message.insert("1.0", message)
            pump()
            assert contact.open_button.cget("state") == "normal"
            sales.copy_message()
            assert root.clipboard_get() == message
            contact.open_button.invoke()
            wait_until(lambda: not contact.browser_action.busy)
            url = browser.call_args.args[0]
            assert urlsplit(url).netloc == "wa.me" and urlsplit(url).path == "/5511999991234"
            assert parse_qs(urlsplit(url).query)["text"] == [message]
            assert browser.call_args.kwargs == dict(new=2)
            assert dict(repo.get_lead(1)) == before
            browser.return_value = False
            contact.open_button.invoke()
            wait_until(lambda: not contact.browser_action.busy)
            assert "Copiar link" in contact.notice.cget("text")
            contact.copy_link()
            assert root.clipboard_get() == url
            sales.message.delete("1.0", "end")
            pump()
            assert contact.open_button.cget("state") == "disabled"
            sales.message.insert("1.0", message)
            sales.save("EDITADA")
            pump()
            assert saved.history(1)[0]["mensagem"] == message
            page.select_lead(5)
            sales5 = page.editors[5].sales
            sales5.generate()
            wait_until(lambda: not sales5.busy)
            pump()
            assert page.editors[5].contact.open_button.cget("state") == "normal"
            assert fake.generate.call_count == 1
            page.select_lead(1)
            sales1 = page.editors[1].sales
            previous = sales1.message.get("1.0", "end-1c")
            sales1.contact_type_selector.set("Contato direto")
            sales1.change_contact_type("Contato direto")
            assert sales1.message.get("1.0", "end-1c") == previous
            sales1.generate(True)
            wait_until(lambda: not sales1.busy)
            pump()
            assert fake.generate.call_count == 2
            assert fake.generate.call_args.kwargs["evidence"]["tipo_contato"] == "contato_direto"
            assert fake.generate.call_args.kwargs["evidence"]["tipo_contato_origem"] == "ajuste_manual"
            assert saved.history(1)[1]["mensagem"] == previous
            page.filters["search"].insert(0, "nenhuma correspondência")
            page.apply_filters()
            pump()
            assert not page.cards and "filtros" in page.list_state.cget("text")
            page.clear_filters()
            pump()
            assert len(page.cards) == 5
            rows = page._data
            page._data = []
            page.apply_filters()
            pump()
            assert "carteira está vazia" in page.list_state.cget("text")
            page._data = rows
            page.apply_filters()
            pump()
            page.select_lead(2)
            editor2 = page.editors[2]
            editor2.tabs.set("Dados do lead")
            contact2 = editor2.contact
            contact2.fields["notes"].insert(0, "Observação sintética")
            contact2.update_availability()
            assert contact2.open_button.cget("state") == "normal"
            assert contact2.save()
            pump()
            assert contact2.open_button.cget("state") == "normal"
            assert repo.get_lead(2)["whatsapp_consent"] == "Desconhecido"
            assert repo.get_lead(2)["consent_source"] is None
            assert repo.get_lead(2)["consent_at"] is None
            page.select_lead(1)
            contact = page.editors[1].contact
            executable = Path(directory) / "Browser With Spaces" / "browser.exe"
            with patch("core.browser_launcher.find_browser", return_value=executable), patch("core.browser_launcher.subprocess.Popen") as process:
                for label, key in (("Microsoft Edge", "edge"), ("Google Chrome", "chrome")):
                    page.browser_selector.set(label)
                    page.choose_browser(label)
                    assert UserSettings(Path(directory) / "settings.json").browser() == key
                    contact.open_button.invoke()
                    wait_until(lambda: not contact.browser_action.busy)
                    args = process.call_args.args[0]
                    assert args[0] == str(executable)
                    assert parse_qs(urlsplit(args[1]).query)["text"] == [contact.sales.message.get("1.0", "end-1c")]
                    assert process.call_args.kwargs["shell"] is False
            root.show_dashboard()
            root.show_sales()
            page = root.current_page
            wait_until(lambda: not page._load_busy and len(page.cards) == 5)
            assert page.browser_preference == "chrome" and page.browser_selector.get() == "Google Chrome"
            page.select_lead(1)
            pump()
            assert page.editors[1].sales.contact_type_selector.get() == "Contato direto"
            contact = page.editors[1].contact
            browser.return_value = True
            count = browser.call_count
            with patch("core.browser_launcher.find_browser", return_value=None), patch("ui.sales_workspace.messagebox.askyesno", return_value=True) as offer:
                contact.open_button.invoke()
                wait_until(lambda: offer.called and not contact.browser_action.busy)
                assert browser.call_count == count + 1
                assert page.browser_preference == UserSettings(Path(directory) / "settings.json").browser() == "chrome"
            with patch("core.browser_launcher.find_browser", return_value=None), patch("ui.sales_workspace.messagebox.askyesno", return_value=False) as offer:
                contact.open_button.invoke()
                wait_until(lambda: offer.called and not contact.browser_action.busy)
                assert browser.call_count == count + 1
                assert "Escolha outro navegador" in contact.notice.cget("text")
            page.browser_selector.set("Navegador padrão do sistema")
            page.choose_browser("Navegador padrão do sistema")
            print("OK: layout", sizes, "keyboard, UTF-8 URL, browser preference persistence, Edge/Chrome arguments, accepted/declined fallback, copy/edit/generate; no external calls")
            if "--show" in sys.argv:
                page.select_lead(1)
                root.after(20000, root.quit)
                root.mainloop()
        finally:
            root.destroy()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
