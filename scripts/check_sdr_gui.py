"""Offline Windows GUI regression. Temporary SQLite and fake AI; no real leads.

Run: python scripts/check_sdr_gui.py --rows 197
Use --show to see the test window. Exit 0 means all checks completed.
"""
import argparse
from contextlib import ExitStack
from pathlib import Path
import sys
import tempfile
import threading
import time
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--rows", type=int, default=197)
    parser.add_argument("--show", action="store_true")
    args = parser.parse_args()
    if not 20 <= args.rows <= 5000:
        parser.error("rows must be between 20 and 5000")
    from core.database.lead_repository import LeadRepository
    from core.database.outreach_repository import OutreachRepository
    from core.sales.models import SalesGeneration
    from ui.sales_workspace import SalesWorkspacePage
    import app

    with tempfile.TemporaryDirectory() as directory, ExitStack() as stack:
        from ui.settings import UserSettings
        stack.enter_context(patch("ui.sales_workspace.UserSettings", lambda: UserSettings(Path(directory) / "settings.json")))
        repository = LeadRepository(Path(directory) / "test.db")
        for index in range(args.rows):
            repository.create_lead(dict(empresa=f"Empresa sintética {index:05d} com nome extenso para testar o layout",
                segmento="dentista" if index % 2 == 0 else "advogado"))
        saved = OutreachRepository(repository.path)
        saved.create(1, SalesGeneration("Texto anterior preservado", "Teste", .8))
        before = [dict(row) for row in repository.list_leads()]
        fake = Mock()
        fake.generate.return_value = dict(mensagem="Rascunho sintético novo", angulo="Teste", confianca=.8)
        for target, replacement in (("app.load_environment", lambda: None),
                ("ui.dashboard.LeadRepository", lambda: repository),
                ("ui.sales_workspace.LeadRepository", lambda: repository),
                ("ui.sales_workspace.create_groq_provider", lambda: Mock()),
                ("ui.sales_panel.create_sales_provider", lambda: fake)):
            stack.enter_context(patch(target, replacement))
        stack.enter_context(patch("socket.create_connection", side_effect=AssertionError("Network forbidden")))
        stack.enter_context(patch("webbrowser.open", side_effect=AssertionError("Browser forbidden")))
        root = app.LoungLeadsApp()
        if not args.show:
            root.attributes("-alpha", 0)
        failures, times, gaps = [], [], []
        root.report_callback_exception = lambda typ, error, tb: failures.append(typ.__name__)
        state = {"cycle": 0, "stage": "open", "start": time.perf_counter(), "tick": time.perf_counter()}
        def watchdog():
            import os
            print("FAIL: GUI timeout", flush=True)
            os._exit(2)  # only this disposable diagnostic process
        timer = threading.Timer(60, watchdog)
        timer.daemon = True
        timer.start()
        def step():
            now = time.perf_counter()
            gaps.append(now - state["tick"])
            state["tick"] = now
            try:
                if failures:
                    raise AssertionError("Tk callback failed")
                stage = state["stage"]
                if stage == "open":
                    state["start"] = now
                    root.sidebar.buttons["sales"].invoke()
                    page = root.content.winfo_children()[0]
                    assert isinstance(page, SalesWorkspacePage)
                    root.sidebar.buttons["sales"].invoke()
                    assert root.content.winfo_children()[0] is page
                    state.update(page=page, stage="loaded")
                elif stage == "loaded":
                    page = state["page"]
                    if not page._load_busy and len(page.cards) == 12:
                        times.append(round(now - state["start"], 3))
                        assert len(page._data) == args.rows and len(page._row_pool) == 12
                        page.change_page(1)
                        state["stage"] = "paged"
                elif stage == "paged":
                    page = state["page"]
                    if page._render_job is None:
                        assert min(page.cards) == 13
                        page.filters["search"].insert(0, "00000")
                        page.apply_filters()
                        state["stage"] = "filtered"
                elif stage == "filtered":
                    page = state["page"]
                    if page._render_job is None:
                        assert list(page.cards) == [1]
                        page.select_lead(1)
                        sales = page.editors[1].sales
                        assert sales.message.get("1.0", "end-1c") == "Texto anterior preservado"
                        sales.message.delete("1.0", "end")
                        sales.message.insert("1.0", "Edição sintética")
                        page.select_lead(2)
                        page.select_lead(1)
                        assert sales.message.get("1.0", "end-1c") == "Edição sintética"
                        sales.save("EDITADA")
                        page.select_lead(2)
                        if state["cycle"] == 0:
                            page.editors[2].sales.generate()
                        state["stage"] = "generated"
                elif stage == "generated":
                    page = state["page"]
                    if not page.editors[2].sales.busy:
                        assert saved.history(2)[0]["mensagem"] == "Rascunho sintético novo"
                        root.sidebar.buttons["dashboard"].invoke()
                        state["cycle"] += 1
                        if state["cycle"] == 3:
                            assert before == [dict(row) for row in repository.list_leads()]
                            assert len(saved.history(1)) == 1
                            assert fake.generate.call_count == 1
                            root.quit()
                            return
                        # Reset only the synthetic edited draft for the next cycle.
                        saved.update(1, saved.history(1)[0]["id"], status="EDITADA", message="Texto anterior preservado")
                        state["stage"] = "open"
                if now - state["start"] > 20:
                    raise AssertionError("Stage timed out")
            except Exception as error:
                failures.append(type(error).__name__ + ":" + state["stage"])
                root.quit()
                return
            root.after(100, step)
        root.after(100, step)
        root.mainloop()
        timer.cancel()
        root.destroy()
        print("cycles", state["cycle"], "load_seconds", times, "max_callback_gap", round(max(gaps, default=0), 3), "errors", failures)
        return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
