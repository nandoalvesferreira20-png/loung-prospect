"""Commercial form and append-only history inside the existing lead dialog."""
from tkinter import messagebox
import customtkinter as ctk

from core.commercial.values import STATUSES, CHANNELS, INTERACTION_TYPES
from ui.commercial_logic import CommercialLead, format_date, history_text
from ui.theme import COLORS, TYPOGRAPHY
from ui.components import field, button, section_label


class CommercialPanel:
    def __init__(self, commercial_parent, history_parent, repository, lead_id, on_change):
        self.logic = CommercialLead(repository, lead_id)
        self.parent = commercial_parent
        self.on_change = on_change
        self.entries = {}
        self.last_contact = ctk.CTkLabel(commercial_parent, text="", text_color=COLORS["muted"], font=TYPOGRAPHY["caption"])
        self.last_contact.pack(anchor="w", pady=(8, 16))
        form = ctk.CTkFrame(commercial_parent, fg_color="transparent")
        form.pack(fill="x")
        for column in (0, 1):
            form.grid_columnconfigure(column, weight=1, uniform="commercial")
        for index, (key, label, options) in enumerate((("status", "Status", STATUSES), ("responsavel", "Responsável", None),
                ("canal_preferencial", "Canal preferencial", ("", *CHANNELS)),
                ("proximo_contato", "Próximo contato · dd/mm/aaaa HH:MM", None))):
            cell = ctk.CTkFrame(form, fg_color="transparent")
            cell.grid(row=index // 2, column=index % 2, sticky="ew", padx=(0, 12), pady=(0, 16))
            self.entries[key] = field(cell, label, options=options)
        action = ctk.CTkFrame(commercial_parent, fg_color="transparent")
        action.pack(fill="x", pady=(0, 16))
        self.entries["proxima_acao"] = field(action, "Próxima ação · até 240 caracteres")
        ctk.CTkLabel(commercial_parent, text="Observações", font=TYPOGRAPHY["secondary"], text_color=COLORS["text_secondary"]).pack(anchor="w", pady=(0, 5))
        self.notes = ctk.CTkTextbox(commercial_parent, height=110, font=TYPOGRAPHY["body"])
        self.notes.pack(fill="x")
        actions = ctk.CTkFrame(commercial_parent, fg_color="transparent")
        actions.pack(fill="x", pady=16)
        button(actions, "Salvar alterações", self.save, kind="primary").pack(side="left")
        self.feedback = ctk.CTkLabel(actions, text="", text_color=COLORS["success"], font=TYPOGRAPHY["caption"])
        self.feedback.pack(side="left", padx=12)
        button(history_parent, "+ Registrar interação", self.new_interaction, kind="primary").pack(anchor="w", pady=16)
        self.history = ctk.CTkTextbox(history_parent, wrap="word", height=300, font=TYPOGRAPHY["body"], fg_color=COLORS["surface"])
        self.history.pack(fill="both", expand=True)
        self.reload()

    def reload(self):
        row = self.logic.load()
        for key, widget in self.entries.items():
            text = format_date(row[key]) if key == "proximo_contato" else row[key] or ""
            if isinstance(widget, ctk.CTkComboBox):
                widget.set(text)
            else:
                widget.delete(0, "end")
                widget.insert(0, text)
        self.notes.delete("1.0", "end")
        self.notes.insert("1.0", row["observacoes"] or "")
        self.refresh_history()

    def refresh_history(self):
        row = self.logic.load()
        self.last_contact.configure(text=f"Último contato: {format_date(row['ultimo_contato']) or 'Não registrado'}")
        self.history.configure(state="normal")
        self.history.delete("1.0", "end")
        self.history.insert("1.0", history_text(self.logic.history()))
        self.history.configure(state="disabled")

    def save(self):
        try:
            self.logic.save(**{key: widget.get() for key, widget in self.entries.items()},
                            observacoes=self.notes.get("1.0", "end-1c"))
            self.feedback.configure(text="Alterações salvas.")
            self.on_change()
        except Exception as error:
            messagebox.showerror("Salvar lead", str(error), parent=self.parent)

    def new_interaction(self):
        row = self.logic.load()
        dialog = ctk.CTkToplevel(self.parent)
        dialog.title("Registrar interação")
        dialog.geometry(f"620x{min(700, dialog.winfo_screenheight() - 120)}")
        dialog.transient(self.parent.winfo_toplevel())
        dialog.grab_set()
        body = ctk.CTkScrollableFrame(dialog)
        body.pack(fill="both", expand=True, padx=16, pady=16)
        section_label(body, "Interação")
        fields = {}
        for key, label, options in (("tipo", "Tipo", INTERACTION_TYPES), ("canal", "Canal", ("", *CHANNELS))):
            ctk.CTkLabel(body, text=label).pack(anchor="w")
            fields[key] = ctk.CTkComboBox(body, values=list(options), height=36)
            fields[key].set(options[0])
            fields[key].pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(body, text="Descrição").pack(anchor="w")
        description = ctk.CTkTextbox(body, height=120)
        description.pack(fill="x")
        section_label(body, "Próximos passos")
        update = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(body, text="Atualizar também os próximos passos", variable=update,
                       command=lambda: toggle()).pack(anchor="w", pady=12)
        for key, label in (("status", "Novo status"), ("proxima_acao", "Próxima ação"),
                           ("proximo_contato", "Próximo contato · dd/mm/aaaa HH:MM")):
            ctk.CTkLabel(body, text=label).pack(anchor="w")
            widget = ctk.CTkComboBox(body, values=list(STATUSES), height=36) if key == "status" else ctk.CTkEntry(body, height=36)
            text = format_date(row[key]) if key == "proximo_contato" else row[key] or ""
            if key == "status":
                widget.set(text)
            else:
                widget.insert(0, text)
            widget.pack(fill="x", pady=(0, 8))
            fields[key] = widget
        def toggle():
            for key in ("status", "proxima_acao", "proximo_contato"):
                fields[key].configure(state="normal" if update.get() else "disabled")
        toggle()
        def close():
            dialog.destroy()
            self.parent.winfo_toplevel().grab_set()
        dialog.protocol("WM_DELETE_WINDOW", close)
        def save():
            try:
                self.logic.register(**{key: widget.get() for key, widget in fields.items()},
                    descricao=description.get("1.0", "end-1c"), update_followup=update.get())
                close()
                self.refresh_history()
                if update.get():
                    saved = self.logic.load()
                    for key in ("status", "proxima_acao", "proximo_contato"):
                        widget = self.entries[key]
                        text = format_date(saved[key]) if key == "proximo_contato" else saved[key] or ""
                        if key == "status":
                            widget.set(text)
                        else:
                            widget.delete(0, "end")
                            widget.insert(0, text)
                self.feedback.configure(text="Interação registrada.")
                self.on_change()
            except Exception as error:
                messagebox.showerror("Registrar interação", str(error), parent=dialog)
        button(body, "Salvar interação", save, kind="primary").pack(anchor="w", pady=16)
