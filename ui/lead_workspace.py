"""Local lead workspace with explicit imports, edits and link opening."""
import queue
import threading
import webbrowser
from tkinter import filedialog, messagebox, ttk

import customtkinter as ctk

from core.database import LeadRepository
from ui.lead_workspace_logic import LeadWorkspace, STATUSES, counts, list_values, valid_url
from ui.theme import COLORS
from ui.copy_field import add_copy_field

DETAILS = {"empresa": "Empresa", "cidade": "Cidade", "segmento": "Segmento", "telefone": "Telefone",
           "whatsapp": "WhatsApp", "email": "Email", "site": "Site", "endereco": "Endereço",
           "avaliacao": "Avaliação", "google_maps": "Google Maps", "qualification_score": "Score",
           "qualification_status": "Qualification Status", "opportunity": "Opportunity",
           "qualification_reasons": "Reasons", "qualification_evidence": "Evidence",
           "qualification_limitations": "Limitations", "rules_version": "Rules Version"}


class LeadWorkspacePage(ctk.CTkFrame):
    def __init__(self, master, repository=None):
        super().__init__(master, fg_color=COLORS["bg"])
        self.logic = LeadWorkspace(repository if repository is not None else LeadRepository())
        self.pending = queue.Queue()
        self.importing = False
        self.poll_job = None
        ctk.CTkLabel(self, text="Carteira de Leads", font=("Arial", 28, "bold")).pack(anchor="w", padx=24, pady=(24, 8))
        self.summary = ctk.CTkLabel(self, text="")
        self.summary.pack(anchor="w", padx=24)
        actions = ctk.CTkFrame(self, fg_color="transparent")
        actions.pack(fill="x", padx=24, pady=12)
        self.import_button = ctk.CTkButton(actions, text="Importar planilha", command=self.import_file)
        self.import_button.pack(side="left", padx=(0, 12))
        ctk.CTkButton(actions, text="Atualizar lista", command=self.refresh).pack(side="left")
        self.notice = ctk.CTkLabel(self, text="Selecione um lead para abrir os detalhes.")
        self.notice.pack(anchor="w", padx=24)
        form = ctk.CTkFrame(self)
        form.pack(fill="x", padx=24, pady=12)
        self.filters = {}
        for index, (key, label) in enumerate((("status", "Status (vazio = todos)"), ("segmento", "Segmento"),
                                            ("responsavel", "Responsável"), ("score", "Score mínimo"), ("search", "Empresa ou cidade"))):
            row, column = divmod(index, 3)
            cell = ctk.CTkFrame(form, fg_color="transparent")
            cell.grid(row=row, column=column, padx=8, pady=6, sticky="ew")
            form.grid_columnconfigure(column, weight=1)
            ctk.CTkLabel(cell, text=label).pack(anchor="w")
            widget = ctk.CTkComboBox(cell, values=["", *STATUSES]) if key == "status" else ctk.CTkEntry(cell)
            if key == "status":
                widget.set("")
            widget.pack(fill="x")
            self.filters[key] = widget
        ctk.CTkButton(form, text="Aplicar filtros", command=self.refresh).grid(row=1, column=2, padx=8, pady=12)
        table_frame = ctk.CTkFrame(self)
        table_frame.pack(fill="both", expand=True, padx=24, pady=(0, 24))
        columns = ("Score", "Empresa", "Cidade", "Segmento", "Opportunity", "Responsável", "Status")
        self.table = ttk.Treeview(table_frame, columns=columns, show="headings", selectmode="browse")
        for name in columns:
            self.table.heading(name, text=name)
            self.table.column(name, width=65 if name == "Score" else 150, minwidth=60)
        vertical = ttk.Scrollbar(table_frame, orient="vertical", command=self.table.yview)
        horizontal = ttk.Scrollbar(table_frame, orient="horizontal", command=self.table.xview)
        self.table.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        vertical.pack(side="right", fill="y")
        horizontal.pack(side="bottom", fill="x")
        self.table.pack(fill="both", expand=True)
        self.table.bind("<<TreeviewSelect>>", self.detail)
        self.refresh()

    def refresh(self):
        try:
            rows = self.logic.list(**{key: entry.get() for key, entry in self.filters.items()})
            stats = counts(self.logic.repository.list_leads())
            self.summary.configure(text=f"Total: {stats['total']} · Novos: {stats['novos']} · Contatados: {stats['contatados']} · Responderam: {stats['responderam']} · Reunião: {stats['reuniao']}")
            self.table.delete(*self.table.get_children())
            for row in rows:
                self.table.insert("", "end", iid=str(row["id"]), values=list_values(row))
        except Exception as error:
            messagebox.showerror("Carteira de Leads", str(error), parent=self)

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
            messagebox.showinfo("Importação", text, parent=self)
        self.refresh()

    def destroy(self):
        if self.poll_job is not None:
            self.after_cancel(self.poll_job)
        super().destroy()

    def detail(self, event=None):
        selection = self.table.selection()
        if not selection:
            return
        try:
            row = self.logic.repository.get_lead(int(selection[0]))
            if row is None:
                raise ValueError("Lead não encontrado. Atualize a lista.")
        except Exception as error:
            messagebox.showerror("Lead", str(error), parent=self)
            return
        dialog = ctk.CTkToplevel(self)
        dialog.title("Detalhes do lead")
        dialog.geometry("700x700")
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()
        body = ctk.CTkScrollableFrame(dialog)
        body.pack(fill="both", expand=True, padx=16, pady=16)
        for field, label in DETAILS.items():
            if field in ("telefone", "whatsapp", "email", "site", "endereco", "google_maps"):
                add_copy_field(body, label, row[field])
            else:
                ctk.CTkLabel(body, text=f"{label}: {row[field] if row[field] is not None else '—'}", wraplength=590, justify="left").pack(anchor="w", pady=4)
        for field, label in (("site", "Abrir Site"), ("google_maps", "Abrir Google Maps")):
            if valid_url(row[field]):
                ctk.CTkButton(body, text=label, command=lambda url=row[field]: self.open_url(url)).pack(anchor="w", pady=6)
        ctk.CTkLabel(body, text="Status").pack(anchor="w")
        status = ctk.CTkComboBox(body, values=list(STATUSES))
        status.set(row["status"])
        status.pack(fill="x")
        ctk.CTkLabel(body, text="Responsável").pack(anchor="w")
        responsible = ctk.CTkEntry(body)
        responsible.insert(0, row["responsavel"] or "")
        responsible.pack(fill="x")
        ctk.CTkLabel(body, text="Observações").pack(anchor="w")
        notes = ctk.CTkTextbox(body, height=130)
        notes.insert("1.0", row["observacoes"] or "")
        notes.pack(fill="x")
        def save():
            try:
                self.logic.save(row["id"], status.get(), responsible.get(), notes.get("1.0", "end-1c"))
                dialog.destroy()
                self.refresh()
            except Exception as error:
                messagebox.showerror("Salvar lead", str(error), parent=dialog)
        ctk.CTkButton(body, text="Salvar alterações", command=save).pack(pady=16)

    def open_url(self, url):
        if not valid_url(url):
            return
        try:
            if not webbrowser.open(url, new=2):
                raise RuntimeError("O navegador não aceitou a solicitação.")
        except Exception as error:
            messagebox.showerror("Abrir link", str(error), parent=self)
