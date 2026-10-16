"""Offline real-Tk navigation/WhatsApp check using only a disposable database.

Use --show to display the synthetic UI during the checks.
No API or real browser is called; no existing database is opened.
"""
import argparse
from contextlib import ExitStack
from pathlib import Path
import sys
import tempfile
import time
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--show", action="store_true")
    args = parser.parse_args()
    from core.database import LeadRepository
    from core.database.outreach_repository import OutreachRepository
    from core.sales.models import SalesGeneration
    from ui.sales_workspace import ContactPanel
    import app

    with tempfile.TemporaryDirectory() as directory, ExitStack() as stack:
        from ui.settings import UserSettings
        stack.enter_context(patch("ui.sales_workspace.UserSettings", lambda: UserSettings(Path(directory) / "settings.json")))
        repo = LeadRepository(Path(directory) / "test.db")
        for index in range(30):
            repo.create_lead(dict(empresa=f"Clínica Sintética {index + 1}", segmento="dentista",
                cidade="Cidade de Teste", telefone="(12) 99184-4481", qualification_score=70,
                opportunity="website"))
        OutreachRepository(repo.path).create(1, SalesGeneration("Mensagem sintética original", "Teste", .8))
        before = [dict(row) for row in repo.list_leads()]
        for module in ("dashboard", "lead_workspace", "my_day", "sales_workspace"):
            stack.enter_context(patch(f"ui.{module}.LeadRepository", lambda: repo))
        stack.enter_context(patch("app.load_environment", lambda: None))
        stack.enter_context(patch("ui.sales_workspace.create_groq_provider", lambda: Mock()))
        stack.enter_context(patch("socket.socket.connect", side_effect=AssertionError("Network forbidden")))
        browser = stack.enter_context(patch("webbrowser.open", return_value=False))
        root = app.LoungLeadsApp()
        if not args.show:
            root.attributes("-alpha", 0)
        errors, checks = [], []
        root.report_callback_exception = lambda typ, exc, tb: errors.append(typ.__name__)
        pages = ("dashboard", "places", "workspace", "search", "day", "sales", "prototype")
        tasks = [(size, page) for size in ("1280x760", "1050x650") for page in pages]
        state = {"index": 0, "start": time.monotonic()}

        def children(widget):
            for child in widget.winfo_children():
                yield child
                yield from children(child)

        def navigate():
            try:
                size, name = tasks[state["index"]]
                root.geometry(size + "+0+0")
                root.sidebar.buttons[name].invoke()
                root.after(1800, inspect)
            except Exception as exc:
                errors.append(type(exc).__name__)
                root.quit()

        def inspect():
            try:
                size, name = tasks[state["index"]]
                page = root.current_page
                root.sidebar.buttons[name].invoke()
                assert root.current_page is page
                if name == "workspace":
                    page.table.selection_set("1")
                    root.update_idletasks()
                    assert page.detail_dialog is None  # selecting is not opening
                    page.open_detail(1)
                    import customtkinter as ctk
                    dialog = next(widget for widget in children(page) if isinstance(widget, ctk.CTkToplevel))
                    tabs = next(widget for widget in children(dialog) if isinstance(widget, ctk.CTkTabview))
                    for tab in ("Dados", "Comercial", "Histórico", "Por modelo", "Com IA"):
                        tabs.set(tab)
                    assert dialog.sales_panel.loaded_text == "Mensagem sintética original"
                    dialog.destroy()
                if name == "sales":
                    assert len(page._data) == 30
                    page.select_lead(1)
                    sales = page.editors[1].sales
                    sales.message.delete("1.0", "end")
                    text = "Olá! Texto editado & não salvo.\nPodemos conversar?"
                    sales.message.insert("1.0", text)
                    contact = next(widget for widget in children(page) if isinstance(widget, ContactPanel))
                    contact.open_whatsapp()
                    state["contact"] = contact
                    state["sales"] = sales
                    root.after(300, check_whatsapp)
                    return
                finish()
            except Exception as exc:
                errors.append(type(exc).__name__ + ":" + tasks[state["index"]][1])
                root.quit()

        def check_whatsapp():
            try:
                from urllib.parse import parse_qs, urlsplit
                contact, sales = state["contact"], state["sales"]
                url = browser.call_args.args[0]
                assert urlsplit(url).path == "/5512991844481"
                assert parse_qs(urlsplit(url).query)["text"] == [sales.message.get("1.0", "end-1c")]
                assert browser.call_args.kwargs == dict(new=2)
                assert "Copiar link" in contact.notice.cget("text")
                contact.copy_link()
                assert root.clipboard_get() == url
                # Restore editor only; do not save or mark contact.
                sales.message.delete("1.0", "end")
                sales.message.insert("1.0", sales.loaded_text)
                finish()
            except Exception as exc:
                errors.append(type(exc).__name__ + ":whatsapp")
                root.quit()

        def finish():
            size, name = tasks[state["index"]]
            checks.append(f"{size}:{name}")
            state["index"] += 1
            if state["index"] == len(tasks):
                assert before == [dict(row) for row in repo.list_leads()]
                root.quit()
            else:
                root.after(50, navigate)

        root.after(100, navigate)
        root.after(180000, lambda: (errors.append("timeout"), root.quit()))
        root.mainloop()
        root.destroy()
        print("screens", len(checks), "seconds", round(time.monotonic() - state["start"], 2), "errors", errors)
        return int(bool(errors) or len(checks) != len(tasks))


if __name__ == "__main__":
    raise SystemExit(main())
