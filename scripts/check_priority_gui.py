"""Real Tk loss-prevention and compact-table checks. Disposable data, no network."""
from contextlib import ExitStack
from pathlib import Path
import socket
import sys
import tempfile
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main():
    import customtkinter as ctk
    import app
    from core.database import LeadRepository
    from core.database.outreach_repository import OutreachRepository
    from core.database.template_draft_repository import TemplateDraftRepository
    from core.sales.models import SalesGeneration
    from ui.pending_edits import ask_pending_action

    def children(widget):
        for child in widget.winfo_children():
            yield child
            yield from children(child)

    with tempfile.TemporaryDirectory() as directory, ExitStack() as stack:
        from ui.settings import UserSettings
        stack.enter_context(patch("ui.sales_workspace.UserSettings", lambda: UserSettings(Path(directory) / "settings.json")))
        repo = LeadRepository(Path(directory) / "priority.db")
        identity = repo.create_lead(dict(empresa="Empresa sintética de nome longo", status="Reunião marcada"))
        outreach = OutreachRepository(repo.path)
        outreach.create(identity, SalesGeneration("Original IA", "Teste", .8))
        for module in ("dashboard", "lead_workspace", "my_day", "sales_workspace"):
            stack.enter_context(patch(f"ui.{module}.LeadRepository", lambda: repo))
        stack.enter_context(patch("app.load_environment", lambda: None))
        stack.enter_context(patch.object(socket.socket, "connect", side_effect=AssertionError("Network forbidden")))
        stack.enter_context(patch("webbrowser.open", side_effect=AssertionError("Browser forbidden")))
        provider = stack.enter_context(patch("ui.sales_panel.create_sales_provider", Mock(side_effect=AssertionError("AI forbidden"))))
        root = app.LoungLeadsApp()
        root.attributes("-alpha", 0)
        errors = []
        root.report_callback_exception = lambda kind, error, tb: errors.append(str(error))

        def pump():
            root.update_idletasks()
            root.update()

        try:
            root.show_workspace()
            pump()
            page = root.current_page
            for size in ("1280x760", "1050x650"):
                root.geometry(size)
                pump()
                # Debounced table fit is exercised deterministically in the event loop.
                root.after(150, root.quit)
                root.mainloop()
                visible = page.table.cget("displaycolumns")
                assert tuple(visible)[:4] == ("Empresa", "Etapa", "Próximo contato", "Prioridade")
                assert len(visible) == len(page.table.cget("columns"))
                assert sum(page.table.column(key, "width") for key in visible[:4]) < page.table.winfo_width()
                page.table.selection_set(str(identity))
                pump()
                assert page.detail_dialog is None
                page.table.focus(str(identity))
                page.table.focus_force()
                pump()
                page.table.event_generate("<Return>")
                pump()
                assert page.detail_dialog is not None
                assert page.detail_dialog.close_detail()

            page.open_detail(identity, generate_ai=True)
            pump()
            provider.assert_not_called()  # opening the IA tab never generates
            dialog = page.detail_dialog
            commercial = dialog.commercial_panel
            commercial.notes.insert("end", "Observação pendente")
            commercial.entries["proxima_acao"].insert(0, "Ligar amanhã")
            commercial.entries["proximo_contato"].insert(0, "16/10/2026 10:30")
            template = dialog.outreach_panel
            template.message.insert("1.0", "Mensagem por modelo editada")
            sales = dialog.sales_panel
            sales.message.delete("1.0", "end")
            sales.message.insert("1.0", "Mensagem IA editada")
            with patch("ui.pending_edits.ask_pending_action", return_value="continue"):
                assert not dialog.close_detail()
            assert dialog.winfo_exists() and commercial.has_pending_edits()
            commercial.entries["proximo_contato"].delete(0, "end")
            commercial.entries["proximo_contato"].insert(0, "31/02/2026 10:30")
            with patch("ui.pending_edits.ask_pending_action", return_value="save"), patch("ui.commercial_panel.messagebox.showerror"):
                assert not dialog.close_detail()
            assert dialog.winfo_exists() and repo.get_lead(identity)["observacoes"] is None
            commercial.entries["proximo_contato"].delete(0, "end")
            commercial.entries["proximo_contato"].insert(0, "16/10/2026 10:30")
            with patch("ui.pending_edits.ask_pending_action", return_value="save"):
                assert dialog.close_detail()
            assert repo.get_lead(identity)["observacoes"] == "Observação pendente"
            assert repo.get_lead(identity)["proxima_acao"] == "Ligar amanhã"
            assert repo.get_lead(identity)["proximo_contato"]
            assert repo.get_lead(identity)["status"] == "Reunião agendada"
            assert TemplateDraftRepository(repo.path).load(identity)["message"] == "Mensagem por modelo editada"
            assert outreach.history(identity)[0]["mensagem"] == "Mensagem IA editada"

            page.open_detail(identity)
            pump()
            dialog = page.detail_dialog
            assert dialog.outreach_panel.message.get("1.0", "end-1c") == "Mensagem por modelo editada"
            dialog.outreach_panel.message.insert("end", " ALTERAÇÃO")
            with patch("ui.pending_edits.ask_pending_action", return_value="continue"):
                dialog.outreach_panel.generate(another=True)
            assert dialog.outreach_panel.message.get("1.0", "end-1c").endswith(" ALTERAÇÃO")
            with patch("ui.pending_edits.ask_pending_action", return_value="discard"):
                dialog.outreach_panel.generate()
            assert not dialog.outreach_panel.message.get("1.0", "end-1c").endswith(" ALTERAÇÃO")
            with patch("ui.pending_edits.ask_pending_action", return_value="discard"):
                assert dialog.close_detail()
            assert TemplateDraftRepository(repo.path).load(identity)["message"] == "Mensagem por modelo editada"

            # Exercise the actual three-button modal and its default close semantics.
            for label, expected in (("Salvar", "save"), ("Descartar alterações", "discard"),
                                    ("Continuar editando", "continue")):
                def choose(text=label):
                    control = next(w for w in children(root) if isinstance(w, ctk.CTkButton) and w.cget("text") == text)
                    control.invoke()
                root.after(100, choose)
                assert ask_pending_action(page, "Teste") == expected
            root.show_day()
            pump()
            root.current_page.table.selection_set(str(identity))
            root.current_page.open_selected()
            pump()
            assert root.current_page.detail_dialog is not None
            assert root.current_page.detail_dialog.close_detail()
            assert not errors, errors
            print("OK: two sizes, selection/Enter, My Day, save/discard/continue, template/AI persistence; no APIs")
        finally:
            root.destroy()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
