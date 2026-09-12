"""Daily manual work queue; no dependency on prospecting."""
from datetime import datetime
from tkinter import ttk, messagebox

import customtkinter as ctk

from core.database import LeadRepository
from core.commercial.day import get_my_day
from ui.commercial_logic import parse_reference_date, day_values
from ui.theme import COLORS, TYPOGRAPHY
from ui.components import heading, field, button, MetricStrip, table
from ui.presentation import empty_copy


class MyDayPage(ctk.CTkFrame):
    def __init__(self, master, on_open, repository=None):
        super().__init__(master, fg_color=COLORS["bg"])
        self.repository = repository if repository is not None else LeadRepository()
        self.on_open = on_open
        heading(self, "Meu Dia", "Organize seus contatos e mantenha o pipeline em movimento.")
        self.metrics = MetricStrip(self, (("atrasados", "ATRASADOS", "warning"), ("hoje", "HOJE", "accent"),
            ("novos", "NOVOS", "text"), ("reunioes", "REUNIÕES", "text"), ("propostas", "PROPOSTAS", "text")))
        self.metrics.pack(fill="x", padx=28, pady=(0, 20))
        form = ctk.CTkFrame(self, fg_color="transparent")
        form.pack(fill="x", padx=28, pady=(0, 8))
        for col in (0, 1):
            form.grid_columnconfigure(col, weight=1)
        owner = ctk.CTkFrame(form, fg_color="transparent")
        owner.grid(row=0, column=0, sticky="ew", padx=(0, 12))
        self.responsible = field(owner, "Responsável · vazio para todos")
        reference = ctk.CTkFrame(form, fg_color="transparent")
        reference.grid(row=0, column=1, sticky="ew", padx=(0, 12))
        self.reference = field(reference, "Data de referência · dd/mm/aaaa", value=datetime.now().strftime("%d/%m/%Y"))
        button(form, "Atualizar", self.refresh).grid(row=0, column=2, sticky="s")
        self.summary = ctk.CTkLabel(self, text="", text_color=COLORS["muted"], font=TYPOGRAPHY["caption"], wraplength=850, justify="left")
        self.summary.pack(anchor="w", padx=28, pady=(4, 8))
        actions = ctk.CTkFrame(self, fg_color="transparent")
        actions.pack(fill="x", padx=28, pady=(0, 12))
        button(actions, "Abrir lead", self.open_selected, kind="primary").pack(side="left")
        ctk.CTkLabel(actions, text="ou dê um duplo clique na linha", text_color=COLORS["muted"], font=TYPOGRAPHY["caption"]).pack(side="left", padx=12)
        frame = ctk.CTkFrame(self, fg_color="transparent")
        frame.pack(fill="both", expand=True, padx=28, pady=(0, 24))
        columns = ("Empresa", "Responsável", "Status", "Score", "Prioridade", "Próxima ação", "Próximo contato")
        self.table = table(frame, columns, {"Empresa": 230, "Score": 65, "Prioridade": 85, "Próxima ação": 230, "Próximo contato": 160})
        self.table.bind("<Double-1>", self.open_selected)
        self.table.bind("<Return>", self.open_selected)
        self.refresh()

    def refresh(self):
        try:
            result = get_my_day(self.repository, parse_reference_date(self.reference.get()),
                                responsavel=self.responsible.get())
            counts = result.counts
            text = (f"Atrasados: {counts['atrasados']} · Hoje: {counts['hoje']} · Novos: {counts['novos']} · "
                    f"Reuniões: {counts['reunioes']} · Propostas: {counts['propostas']}")
            if result.invalid_dates:
                text += f"\n{result.invalid_dates} data(s) inválida(s) não consideradas no agendamento."
            self.metrics.set(counts)
            self.summary.configure(text=text if result.rows else empty_copy("day", False) + ("\n" + text if result.invalid_dates else ""))
            self.table.delete(*self.table.get_children())
            for index, row in enumerate(result.rows):
                self.table.insert("", "end", iid=str(row["id"]), values=day_values(row), tags=("alternate",) if index % 2 else ())
        except Exception as error:
            messagebox.showerror("Meu Dia", str(error), parent=self)

    def open_selected(self, event=None):
        selected = self.table.selection()
        if selected:
            self.on_open(int(selected[0]))
