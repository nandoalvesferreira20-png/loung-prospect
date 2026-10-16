"""Local lead workspace with explicit imports, edits and link opening."""
import queue
import threading
import webbrowser
from tkinter import filedialog, messagebox, ttk

import customtkinter as ctk

from core.database import LeadRepository
from ui.lead_workspace_logic import LeadWorkspace, STATUSES, counts, list_values, valid_url
from ui.theme import COLORS, TYPOGRAPHY, SPACING
from ui.components import panel, heading, button, field, table, badge
from ui.presentation import portfolio_values, priority_tone, status_tone, empty_copy
from ui.commercial_logic import priority_label
from ui.copy_field import add_copy_field
from ui.commercial_panel import CommercialPanel
from core.commercial.values import commercial_status
from core.database.template_draft_repository import TemplateDraftRepository

DETAILS = {"empresa": "Empresa", "cidade": "Cidade", "segmento": "Segmento", "telefone": "Telefone",
           "whatsapp": "WhatsApp", "email": "Email", "site": "Site", "endereco": "Endereço",
           "avaliacao": "Avaliação", "quantidade_avaliacoes": "Quantidade de avaliações", "google_maps": "Google Maps", "qualification_score": "Score",
           "qualification_status": "Qualificação", "opportunity": "Oportunidade",
           "qualification_reasons": "Motivos", "qualification_evidence": "Evidências",
           "qualification_limitations": "Limitações", "rules_version": "Versão das regras"}


class LeadWorkspacePage(ctk.CTkFrame):
    def __init__(self, master, repository=None):
        super().__init__(master, fg_color=COLORS["bg"])
        self.logic = LeadWorkspace(repository if repository is not None else LeadRepository())
        self.pending = queue.Queue()
        self.importing = False
        self.poll_job = None
        self.detail_dialog = None
        heading(self, "Carteira de Leads", "Gerencie e acompanhe sua operação comercial.")
        self.summary = ctk.CTkLabel(self, text="", font=TYPOGRAPHY["secondary"], text_color=COLORS["text_secondary"])
        self.summary.pack(anchor="w", padx=28, pady=(0, 12))
        actions = ctk.CTkFrame(self, fg_color="transparent")
        actions.pack(fill="x", padx=28, pady=(0, 12))
        self.import_button = button(actions, "Importar planilha", self.import_file, kind="primary")
        self.import_button.pack(side="left", padx=(0, 8))
        button(actions, "Atualizar lista", self.refresh).pack(side="left")
        button(actions, "Abrir abordagem com IA", self.generate_sales).pack(side="left", padx=8)
        button(actions, "Abrir lead", self.detail, kind="primary", width=100).pack(side="left")
        form = panel(self)
        form.pack(fill="x", padx=28, pady=(0, 4))
        self.filters = {}
        search_cell = ctk.CTkFrame(form, fg_color="transparent")
        search_cell.grid(row=0, column=0, columnspan=3, sticky="ew", padx=12, pady=12)
        self.filters["search"] = field(search_cell, "Buscar empresa ou cidade", placeholder_text="Digite para filtrar")
        button(form, "Aplicar filtros", self.refresh, width=120).grid(row=0, column=3, sticky="sew", pady=(0, 12), padx=(0, 8))
        button(form, "Limpar", self.clear_filters, kind="ghost", width=80).grid(row=0, column=4, sticky="sew", pady=(0, 12))
        for col, (key, label) in enumerate((("status", "Status · todos se vazio"), ("segmento", "Segmento"), ("responsavel", "Responsável"), ("score", "Score mínimo"))):
            form.grid_columnconfigure(col, weight=1)
            cell = ctk.CTkFrame(form, fg_color="transparent")
            cell.grid(row=1, column=col, columnspan=2 if col == 3 else 1, sticky="ew", padx=(0, 12 if col < 3 else 0), pady=(0, 8))
            self.filters[key] = field(cell, label, options=["", *STATUSES] if key == "status" else None, width=110)
        self.filters["search"].bind("<Return>", lambda event: self.refresh())
        self.notice = ctk.CTkLabel(self, text="Selecione um lead e use Abrir lead, duplo clique ou Enter. Arraste a barra horizontal para outras colunas.", text_color=COLORS["muted"], font=TYPOGRAPHY["caption"])
        self.notice.pack(anchor="w", padx=28, pady=(0, 8))
        table_frame = ctk.CTkFrame(self, fg_color="transparent")
        table_frame.pack(fill="both", expand=True, padx=28, pady=(0, 24))
        columns = ("Empresa", "Etapa", "Próximo contato", "Prioridade", "Score", "Cidade", "Segmento", "Responsável")
        self.table = table(table_frame, columns, {"Empresa": 220, "Etapa": 150, "Próximo contato": 155, "Prioridade": 85, "Score": 65})
        self.table.bind("<Double-1>", self.detail)
        self.table.bind("<Return>", self.detail)
        self.refresh()

    def refresh(self):
        try:
            rows = self.logic.list(**{key: entry.get() for key, entry in self.filters.items()})
            stats = counts(self.logic.repository.list_leads())
            self.summary.configure(text=f"Total: {stats['total']} · Novos: {stats['novos']} · Contatados: {stats['contatados']} · Responderam: {stats['responderam']} · Reunião: {stats['reuniao']}")
            self.table.delete(*self.table.get_children())
            self.notice.configure(text=empty_copy("portfolio", bool(rows)) or f"{len(rows)} leads · selecione e use Abrir lead, duplo clique ou Enter · outras colunas na barra horizontal")
            for index, row in enumerate(rows):
                self.table.insert("", "end", iid=str(row["id"]), values=portfolio_values(row), tags=("alternate",) if index % 2 else ())
        except Exception as error:
            messagebox.showerror("Carteira de Leads", str(error), parent=self)

    def clear_filters(self):
        for key, widget in self.filters.items():
            if key == "status":
                widget.set("")
            else:
                widget.delete(0, "end")
        self.refresh()

    def import_file(self):
        if self.importing:
            return
        path = filedialog.askopenfilename(parent=self, filetypes=[("Planilhas Excel", "*.xlsx")])
        if not path:
            return
        self.importing = True
        self.import_button.configure(state="disabled")
        self.notice.configure(text="Importando planilha…")
        def worker():
            try:
                self.pending.put((self.logic.import_file(path), None))
            except Exception as error:
                self.pending.put((None, str(error)))
        threading.Thread(target=worker, daemon=True).start()
        self.poll_job = self.after(100, self.poll_import)

    def poll_import(self):
        self.poll_job = None
        try:
            summary, error = self.pending.get_nowait()
        except queue.Empty:
            self.poll_job = self.after(100, self.poll_import)
            return
        self.importing = False
        self.import_button.configure(state="normal")
        self.notice.configure(text="Importação encerrada.")
        if error:
            messagebox.showerror("Importação", error, parent=self)
        else:
            text = f"Linhas: {summary.total_rows}\nImportados: {summary.imported}\nDuplicados: {summary.skipped_duplicates}\nInválidos: {summary.skipped_invalid}"
            if summary.errors:
                text += "\n\n" + "\n".join(f"Linha {issue.row}: {issue.message}" for issue in summary.errors[:8])
                if len(summary.errors) > 8:
                    text += f"\nMais {len(summary.errors) - 8} erros."
            self.notice.configure(text=text.replace("\n", " · "))
        self.refresh()
        if not error:
            self.notice.configure(text=f"Importação concluída · {summary.imported} inseridos · {summary.skipped_duplicates} duplicados")

    def destroy(self):
        if self.poll_job is not None:
            self.after_cancel(self.poll_job)
        super().destroy()

    def detail(self, event=None):
        selection = self.table.selection()
        if not selection:
            return
        self.open_detail(int(selection[0]))

    def can_leave(self):
        dialog = self.detail_dialog
        if dialog is not None and dialog.winfo_exists():
            return dialog.close_detail()
        return True

    def generate_sales(self):
        selection = self.table.selection()
        if not selection:
            self.notice.configure(text="Selecione um lead para abrir a abordagem com IA.")
            return
        self.open_detail(int(selection[0]), generate_ai=True)

    def open_detail(self, lead_id, generate_ai=False):
        if self.detail_dialog is not None and self.detail_dialog.winfo_exists():
            if not self.detail_dialog.close_detail():
                return
        try:
            row = self.logic.repository.get_lead(lead_id)
            if row is None:
                raise ValueError("Lead não encontrado. Atualize a lista.")
        except Exception as error:
            messagebox.showerror("Lead", str(error), parent=self)
            return
        dialog = ctk.CTkToplevel(self)
        self.detail_dialog = dialog
        dialog.title("Detalhes do lead")
        dialog.geometry(f"780x{min(730, dialog.winfo_screenheight() - 120)}")
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()
        header = ctk.CTkFrame(dialog, fg_color="transparent")
        header.pack(fill="x", padx=24, pady=(20, 0))
        ctk.CTkLabel(header, text=row["empresa"], font=TYPOGRAPHY["section"], wraplength=700, justify="left").pack(anchor="w")
        ctk.CTkLabel(header, text=" · ".join(value for value in (row["segmento"], row["cidade"]) if value), text_color=COLORS["muted"]).pack(anchor="w")
        chips = ctk.CTkFrame(header, fg_color="transparent")
        chips.pack(fill="x", pady=(8, 0))
        badge(chips, f"Score {row['qualification_score'] if row['qualification_score'] is not None else '—'}").pack(side="left", padx=(0, 8))
        badge(chips, priority_label(row["qualification_score"]), priority_tone(row["qualification_score"])).pack(side="left", padx=(0, 8))
        badge(chips, commercial_status(row["status"]), status_tone(row["status"])).pack(side="left")
        tabs = ctk.CTkTabview(dialog)
        tabs.pack(fill="both", expand=True, padx=16, pady=16)
        for name in ("Dados", "Comercial", "Histórico", "Por modelo", "Com IA"):
            tabs.add(name)
        body = ctk.CTkScrollableFrame(tabs.tab("Dados"))
        body.pack(fill="both", expand=True)
        for field, label in DETAILS.items():
            if field in ("telefone", "whatsapp", "email", "site", "endereco", "google_maps"):
                add_copy_field(body, label, row[field])
            else:
                ctk.CTkLabel(body, text=f"{label}: {row[field] if row[field] is not None else '—'}", wraplength=590, justify="left").pack(anchor="w", pady=4)
        for field, label in (("site", "Abrir Site"), ("google_maps", "Abrir Google Maps")):
            if valid_url(row[field]):
                button(body, label, lambda url=row[field]: self.open_url(url), kind="secondary").pack(anchor="w", pady=6)
        commercial = ctk.CTkScrollableFrame(tabs.tab("Comercial"))
        commercial.pack(fill="both", expand=True)
        dialog.commercial_panel = CommercialPanel(commercial, tabs.tab("Histórico"),
            self.logic.repository, row["id"], self.refresh)
        from ui.outreach_panel import OutreachPanel
        dialog.outreach_panel = OutreachPanel(tabs.tab("Por modelo"),
            lambda: self.logic.repository.get_lead(lead_id),
            TemplateDraftRepository(self.logic.repository.path), lead_id)
        tabs.set("Comercial")
        from ui.sales_panel import SalesPanel
        dialog.sales_panel = SalesPanel(tabs.tab("Com IA"), self.logic.repository, lead_id)
        def close_detail():
            for tab, confirm in (("Comercial", dialog.commercial_panel.confirm_pending),
                                  ("Por modelo", dialog.outreach_panel.confirm_pending),
                                  ("Com IA", dialog.sales_panel.confirm_discard)):
                tabs.set(tab)
                if not confirm():
                    return False
            dialog.destroy()
            self.detail_dialog = None
            return True
        dialog.close_detail = close_detail
        dialog.protocol("WM_DELETE_WINDOW", close_detail)
        if generate_ai:
            tabs.set("Com IA")
            # Opening an editor is separate from explicitly requesting generation.

    def open_url(self, url):
        if not valid_url(url):
            return
        try:
            if not webbrowser.open(url, new=2):
                raise RuntimeError("O navegador não aceitou a solicitação.")
        except Exception as error:
            messagebox.showerror("Abrir link", str(error), parent=self)
