"""Manual, isolated Prototype Studio page."""
import os
from tkinter import filedialog, messagebox

import customtkinter as ctk

from core.prototype.preview import get_preview_path, open_preview
from ui.prototype_logic import PrototypeSession
from ui.theme import COLORS, FONT


class PrototypeStudioPage(ctk.CTkScrollableFrame):
    def __init__(self, master, session=None):
        super().__init__(master, fg_color=COLORS["bg"])
        self.session = session if session is not None else PrototypeSession()
        self.template_ids = {}
        self.entries = {}
        ctk.CTkLabel(self, text="Prototype Studio", font=(FONT, 30, "bold")).pack(anchor="w", padx=28, pady=(25, 8))
        ctk.CTkLabel(self, text="Preencha um lead e escolha um template para gerar um protótipo local.", wraplength=680).pack(anchor="w", padx=28, pady=(0, 20))
        for key, label in (("company_name", "Nome da empresa *"), ("segment", "Segmento *"),
                           ("city", "Cidade"), ("phone", "Telefone"), ("whatsapp", "WhatsApp (com DDI informado)"),
                           ("address", "Endereço"), ("current_website", "Website atual"),
                           ("qualification_score", "Score de qualificação (opcional, 0–100)"),
                           ("output_directory", "Pasta de saída *")):
            ctk.CTkLabel(self, text=label).pack(anchor="w", padx=28)
            entry = ctk.CTkEntry(self, height=36)
            entry.pack(fill="x", padx=28, pady=(0, 10))
            self.entries[key] = entry
        self.entries["output_directory"].insert(0, "prototypes")
        ctk.CTkButton(self, text="Escolher pasta", command=self.choose_directory).pack(anchor="w", padx=28, pady=6)
        ctk.CTkButton(self, text="Carregar templates", command=self.load_templates).pack(anchor="w", padx=28, pady=6)
        self.templates = ctk.CTkComboBox(self, values=["Carregue os templates"], state="disabled", width=400)
        self.templates.set("Carregue os templates")
        self.templates.pack(fill="x", padx=28, pady=10)
        self.generate_button = ctk.CTkButton(self, text="Gerar protótipo", command=self.generate)
        self.generate_button.pack(anchor="w", padx=28, pady=8)
        self.preview_button = ctk.CTkButton(self, text="Abrir protótipo", command=self.preview)
        self.preview_button.pack(anchor="w", padx=28, pady=6)
        self.folder_button = ctk.CTkButton(self, text="Abrir pasta", command=self.open_directory)
        self.folder_button.pack(anchor="w", padx=28, pady=6)
        self.result_label = ctk.CTkLabel(self, text="Nenhuma geração solicitada.", wraplength=650, justify="left")
        self.result_label.pack(anchor="w", padx=28, pady=20)
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
                messagebox.showinfo("Templates", "Nenhum template compatível com o segmento informado.", parent=self)
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
