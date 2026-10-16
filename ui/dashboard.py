"""Operational overview built exclusively from existing lead/day APIs."""
from tkinter import messagebox
import queue
import threading
import customtkinter as ctk
from core.database import LeadRepository
from ui.theme import COLORS, TYPOGRAPHY, SPACING
from ui.components import heading, button, MetricStrip, section_label, badge, panel
from ui.presentation import overview_data, overview_details, empty_copy, priority_tone, status_tone
from ui.commercial_logic import priority_label, format_date


class DashboardPage(ctk.CTkScrollableFrame):
    def __init__(self, master, repository=None, on_search=None, on_workspace=None, on_day=None, on_sales=None):
        super().__init__(master, fg_color=COLORS["bg"])
        self.repository = repository
        self.pending = queue.Queue()
        self.job = None
        self.loading = False
        self.closed = False
        heading(self, "Visão Geral", "Sua operação comercial, em um só lugar.")
        actions = ctk.CTkFrame(self, fg_color="transparent")
        actions.pack(fill="x", padx=28, pady=(0, 20))
        for label, command, kind in (("Prospectar", on_search, "primary"), ("Abrir Carteira", on_workspace, "secondary"), ("SDR Inteligente", on_sales, "secondary"), ("Meu Dia", on_day, "ghost")):
            button(actions, label, command, kind=kind).pack(side="left", padx=(0, 8))
        button(actions, "Atualizar", self.refresh, kind="ghost", width=90).pack(side="right")
        self.metrics = MetricStrip(self, (("total", "TOTAL DE LEADS", "text"), ("today", "PARA HOJE", "accent"),
                                        ("overdue", "ATRASADOS", "warning"), ("meetings", "REUNIÕES", "text")))
        self.metrics.pack(fill="x", padx=28, pady=(0, 24))
        content = ctk.CTkFrame(self, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=28, pady=(0, 28))
        content.grid_columnconfigure(0, weight=1)
        content.grid_columnconfigure(1, weight=3)
        self.priorities = ctk.CTkFrame(content, fg_color="transparent")
        self.priorities.grid(row=0, column=0, sticky="new", padx=(0, 24))
        section_label(self.priorities, "Prioridades")
        self.priority_labels = {}
        for key, title, tone in (("high", "Alta", "accent"), ("good", "Boa", "accent"), ("medium", "Média", "warning"), ("low", "Baixa", "neutral"), ("unknown", "Sem score", "neutral")):
            row = ctk.CTkFrame(self.priorities, fg_color="transparent")
            row.pack(fill="x", pady=8)
            badge(row, title, tone).pack(side="left")
            value = ctk.CTkLabel(row, text="—", font=TYPOGRAPHY["section"])
            value.pack(side="right", padx=8)
            self.priority_labels[key] = value
        self.activity = ctk.CTkFrame(content, fg_color="transparent")
        self.activity.grid(row=0, column=1, sticky="new")
        section_label(self.activity, "Próximas ações")
        self.activity_rows = ctk.CTkFrame(self.activity, fg_color="transparent")
        self.activity_rows.pack(fill="both", expand=True)
        self.details = panel(self)
        self.details.pack(fill="x", padx=28, pady=(0, 28))
        for column in range(3):
            self.details.grid_columnconfigure(column, weight=1, uniform="details")
        self.detail_labels = {}
        for column, (key, title) in enumerate((("recent", "Leads recentes"), ("segments", "Por segmento"), ("opportunities", "Oportunidades"))):
            cell = ctk.CTkFrame(self.details, fg_color="transparent")
            cell.grid(row=0, column=column, sticky="nsew", padx=16, pady=16)
            section_label(cell, title)
            label = ctk.CTkLabel(cell, text="Carregando…", justify="left", anchor="nw", text_color=COLORS["text_secondary"])
            label.pack(fill="both", expand=True)
            from ui.responsive_text import WrappedLabels
            cell._wrap = WrappedLabels(cell, (label,), padding=0)
            self.detail_labels[key] = label
        self.refresh()

    def refresh(self):
        if self.loading or self.closed:
            return
        self.loading = True
        repository, pending = self.repository, self.pending
        def worker():
            try:
                repo = repository if repository is not None else LeadRepository()
                rows = repo.list_leads()
                pending.put((repo, overview_data(rows), overview_details(rows), None))
            except Exception:
                from ui.sdr_diagnostics import log_current_error
                log_current_error()
                pending.put((None, None, None, "Não foi possível carregar os indicadores. Tente atualizar."))
        threading.Thread(target=worker, daemon=True).start()
        self.job = self.after(50, self.poll)

    def poll(self):
        self.job = None
        if self.closed:
            return
        try:
            repository, data, details, error = self.pending.get_nowait()
        except queue.Empty:
            self.job = self.after(50, self.poll)
            return
        self.loading = False
        if error:
            self.detail_labels["recent"].configure(text=error)
            return
        self.repository = repository
        self.render(data, details)

    def destroy(self):
        self.closed = True
        if self.job is not None:
            self.after_cancel(self.job)
        super().destroy()

    def render(self, data, details):
        try:
            for key in ("segments", "opportunities"):
                self.detail_labels[key].configure(text="\n\n".join(f"{name} · {count}" for name, count in details[key]) or "Nenhum lead cadastrado.")
            self.detail_labels["recent"].configure(text="\n\n".join(row["empresa"] for row in details["recent"]) or "Sua carteira começa com a primeira busca.")
            self.metrics.set(data)
            for key, label in self.priority_labels.items():
                label.configure(text=str(data["priorities"][key]))
            for widget in self.activity_rows.winfo_children():
                widget.destroy()
            if not data["actions"]:
                ctk.CTkLabel(self.activity_rows, text=empty_copy("actions", False), text_color=COLORS["muted"],
                            wraplength=450, justify="left").pack(anchor="w", pady=20)
            for row in data["actions"]:
                line = ctk.CTkFrame(self.activity_rows, fg_color=COLORS["surface"], corner_radius=6)
                line.pack(fill="x", pady=(0, 8))
                line.grid_columnconfigure(0, weight=1)
                ctk.CTkLabel(line, text=row["empresa"], font=TYPOGRAPHY["body"], anchor="w").grid(row=0, column=0, sticky="ew", padx=14, pady=(10, 0))
                badge(line, row["status"], status_tone(row["status"])).grid(row=0, column=1, padx=12)
                ctk.CTkLabel(line, text=row["proxima_acao"] or "Próxima ação não definida", text_color=COLORS["muted"], anchor="w").grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 10))
                ctk.CTkLabel(line, text=format_date(row["proximo_contato"]) or "Sem agendamento", text_color=COLORS["muted"], font=TYPOGRAPHY["caption"]).grid(row=1, column=1, padx=12)
        except Exception as error:
            messagebox.showerror("Visão Geral", str(error), parent=self)
