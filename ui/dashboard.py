"""Operational overview built exclusively from existing lead/day APIs."""
from tkinter import messagebox
import customtkinter as ctk
from core.database import LeadRepository
from ui.theme import COLORS, TYPOGRAPHY, SPACING
from ui.components import heading, button, MetricStrip, section_label, badge
from ui.presentation import overview_data, empty_copy, priority_tone, status_tone
from ui.commercial_logic import priority_label, format_date


class DashboardPage(ctk.CTkScrollableFrame):
    def __init__(self, master, repository=None, on_search=None, on_workspace=None, on_day=None):
        super().__init__(master, fg_color=COLORS["bg"])
        self.repository = repository if repository is not None else LeadRepository()
        heading(self, "Visão Geral", "Sua operação comercial, em um só lugar.")
        actions = ctk.CTkFrame(self, fg_color="transparent")
        actions.pack(fill="x", padx=28, pady=(0, 20))
        for label, command, kind in (("Prospectar", on_search, "primary"), ("Abrir Carteira", on_workspace, "secondary"), ("Meu Dia", on_day, "secondary")):
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
        for key, title, tone in (("high", "Alta", "accent"), ("good", "Boa", "success"), ("medium", "Média", "warning"), ("low", "Baixa", "neutral"), ("unknown", "Sem score", "neutral")):
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
        self.refresh()

    def refresh(self):
        try:
            data = overview_data(self.repository.list_leads())
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
