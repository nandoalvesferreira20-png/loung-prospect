"""Manual, isolated Prototype Studio page."""
import os
from tkinter import filedialog, messagebox

import customtkinter as ctk

from core.prototype.preview import get_preview_path, open_preview
from ui.prototype_logic import PrototypeSession
from ui.theme import COLORS, FONT, TYPOGRAPHY
from ui.components import heading, field, button, section_label


class PrototypeStudioPage(ctk.CTkScrollableFrame):
    def __init__(self, master, session=None):
        super().__init__(master, fg_color=COLORS["bg"])
        self.session = session if session is not None else PrototypeSession()
        self.template_ids = {}
        self.entries = {}
        heading(self, "Prototype Studio", "Crie uma apresentação local a partir dos dados do lead.")
        form = ctk.CTkFrame(self, fg_color="transparent")
        form.pack(fill="x", padx=28)
        for column in (0, 1):
            form.grid_columnconfigure(column, weight=1, uniform="prototype")
        for index, (key, label) in enumerate((("company_name", "Nome da empresa *"), ("segment", "Segmento *"),
                ("city", "Cidade"), ("phone", "Telefone"), ("whatsapp", "WhatsApp · com DDI informado"),
                ("address", "Endereço"), ("current_website", "Site atual"),
                ("qualification_score", "Score · opcional, 0–100"))):
            cell = ctk.CTkFrame(form, fg_color="transparent")
            cell.grid(row=index // 2, column=index % 2, sticky="ew", padx=(0, 12), pady=(0, 12))
            self.entries[key] = field(cell, label)
        output = ctk.CTkFrame(self, fg_color="transparent")
        output.pack(fill="x", padx=28, pady=(8, 16))
        self.entries["output_directory"] = field(output, "Pasta de saída *", value="prototypes")
        button(output, "Escolher pasta", self.choose_directory, kind="ghost").pack(anchor="w", pady=(8, 0))
        templates = ctk.CTkFrame(self, fg_color="transparent")
        templates.pack(fill="x", padx=28, pady=(0, 16))
        section_label(templates, "Template")
        button(templates, "Carregar templates", self.load_templates).pack(anchor="w", pady=(0, 8))
        self.templates = ctk.CTkComboBox(templates, values=["Carregue os templates"], state="disabled", height=36)
        self.templates.set("Carregue os templates")
        self.templates.pack(fill="x")
        actions = ctk.CTkFrame(self, fg_color="transparent")
        actions.pack(fill="x", padx=28, pady=(0, 12))
        self.generate_button = button(actions, "Gerar protótipo", self.generate, kind="primary")
        self.generate_button.pack(side="left", padx=(0, 8))
        self.preview_button = button(actions, "Abrir protótipo", self.preview)
        self.preview_button.pack(side="left", padx=(0, 8))
        self.folder_button = button(actions, "Abrir pasta", self.open_directory)
        self.folder_button.pack(side="left")
        self.result_label = ctk.CTkLabel(self, text="Nenhuma geração solicitada.", wraplength=750, justify="left", text_color=COLORS["muted"])
        self.result_label.pack(anchor="w", padx=28, pady=(0, 24))
        self.refresh_result()

    def choose_directory(self):
        selected = filedialog.askdirectory(parent=self, title="Pasta de saída dos protótipos")
        if selected:
            self.entries["output_directory"].delete(0, "end")
            self.entries["output_directory"].insert(0, selected)

    def load_templates(self):
        self.template_ids = {}
        self.templates.configure(state="disabled")
        self.templates.set("Nenhum template compatível")
        try:
            available = self.session.templates(self.entries["segment"].get())
            self.template_ids = {f"{t.name} · {t.version} ({t.template_id})": t.template_id for t in available}
            if not available:
                self.result_label.configure(text="Nenhum template compatível com o segmento informado.")
                return
            labels = list(self.template_ids)
            self.templates.configure(values=labels, state="readonly")
            self.templates.set(labels[0])
        except Exception as error:
            messagebox.showerror("Templates", str(error), parent=self)

    def refresh_result(self):
        state = "normal" if self.session.can_open else "disabled"
        self.preview_button.configure(state=state)
        self.folder_button.configure(state=state)
        result = self.session.last_result
        if result is not None:
            text = f"Protótipo criado em:\n{result.output_path}" if self.session.can_open else "Falha na geração:\n" + "\n".join(result.errors)
            if result.warnings:
                text += "\nAvisos:\n" + "\n".join(result.warnings)
            self.result_label.configure(text=text)

    def generate(self):
        self.generate_button.configure(state="disabled")
        try:
            self.session.generate({key: entry.get() for key, entry in self.entries.items()},
                                  self.template_ids.get(self.templates.get()))
        except Exception as error:
            self.result_label.configure(text=f"Não foi possível gerar: {error}")
            messagebox.showerror("Prototype Studio", str(error), parent=self)
        finally:
            self.generate_button.configure(state="normal")
            self.refresh_result()

    def preview(self):
        if self.session.can_open:
            try:
                open_preview(self.session.last_result)
            except Exception as error:
                messagebox.showerror("Preview", str(error), parent=self)

    def open_directory(self):
        if self.session.can_open:
            try:
                os.startfile(get_preview_path(self.session.last_result).parent)
            except Exception as error:
                messagebox.showerror("Abrir pasta", str(error), parent=self)
