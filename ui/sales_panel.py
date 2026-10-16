"""Human review panel; worker communicates through a queue, never Tk calls."""
import queue
import threading
from tkinter import messagebox
import customtkinter as ctk

from core.sales.agent import SalesAgent, SalesGenerationError
from core.sales.errors import SalesConfigurationError
from core.sales.provider import create_sales_provider
from core.database.outreach_repository import OutreachRepository
from ui.components import button, badge
from ui.sdr_components import StatusBar
from ui.sdr_formatting import draft_label, confidence_badge, STATUS_LABELS
from ui.theme import COLORS, TYPOGRAPHY
from ui.copy_field import copy_to_clipboard
from ui.responsive_text import WrappedLabels
from ui.sdr_diagnostics import log_current_error
from ui.pending_edits import resolve_pending
from core.sales.contact_routing import CONTACT_TYPES, classify_contact
from core.database.contact_preference_repository import ContactPreferenceRepository


def notify_state(panel):
    callback = getattr(panel, "on_state_changed", None)
    if callback is not None:
        callback()


class SalesPanel(ctk.CTkFrame):
    def __init__(self, master, repository, lead_id, *, inline=False, on_completed=None):
        super().__init__(master, fg_color="transparent")
        self.pack(fill="both", expand=True)
        self.repository, self.lead_id = repository, lead_id
        self.on_completed = on_completed
        self.active_provider = None
        self.outreach = OutreachRepository(repository.path, initialize=not inline)
        self.contact_preferences = ContactPreferenceRepository(repository.path)
        lead = repository.get_lead(lead_id)
        override = self.contact_preferences.get(lead_id)
        self.contact_type = override or classify_contact(lead["segmento"] if lead else None)
        self.pending = queue.Queue()
        self.busy, self.job, self.current_id, self.snapshot = False, None, None, None
        self.rows = {}
        self.loaded_text = ""
        if not inline:
            ctk.CTkLabel(self, text="Rascunhos de IA · aprovação salva a versão, sem enviar contato.",
                         text_color=COLORS["muted"], wraplength=650).pack(pady=8)
        routing_row = ctk.CTkFrame(self, fg_color="transparent")
        routing_row.pack(fill="x", padx=12, pady=(0, 4))
        self.contact_type_label = ctk.CTkLabel(routing_row,
            text="Contato provável · manual" if override else "Contato provável · pelo nicho",
            font=TYPOGRAPHY["caption"], text_color=COLORS["muted"])
        self.contact_type_label.pack(side="left")
        self.contact_type_selector = ctk.CTkComboBox(routing_row, values=list(CONTACT_TYPES), state="readonly",
            width=165, height=28, font=TYPOGRAPHY["caption"], command=self.change_contact_type)
        self.contact_type_selector.set(next(label for label, value in CONTACT_TYPES.items() if value == self.contact_type))
        self.contact_type_selector.pack(side="right")
        version_row = ctk.CTkFrame(self, fg_color="transparent")
        version_row.pack(fill="x", padx=12)
        self.history = ctk.CTkComboBox(version_row, values=["Nenhuma abordagem"], state="readonly", command=self.select)
        self.history.pack(side="left", fill="x", expand=True)
        if inline:
            button(version_row, "⋯ Mais ações", self.toggle_reason, kind="ghost", width=90, height=28).pack(side="right", padx=(4, 0))
        self.info = ctk.CTkLabel(self, text="", wraplength=300 if inline else 650, font=TYPOGRAPHY["caption"], text_color=COLORS["muted"], anchor="w", justify="left")
        self.info.pack(fill="x", padx=12, pady=2 if inline else 8)
        self.message = ctk.CTkTextbox(self, wrap="word", height=130 if inline else 280, font=TYPOGRAPHY["message"], border_width=1)
        self.message.pack(fill="both", expand=True, padx=12)
        self.message._textbox.configure(padx=12, pady=10)
        self.message._textbox.bind("<<Modified>>", self.message_modified, add="+")
        self.options = ctk.CTkFrame(self, fg_color="transparent") if inline else None
        self.reason = ctk.CTkEntry(self.options if inline else self, placeholder_text="Motivo para outra versão (opcional, até 500 caracteres)")
        if not inline:
            self.reason.pack(fill="x", padx=12, pady=6)
        else:
            self.reason.grid(row=2, column=0, columnspan=2, sticky="ew", padx=4, pady=4)
        actions = ctk.CTkFrame(self, fg_color="transparent")
        actions.pack(fill="x", padx=12, pady=8)
        self.buttons = []
        for index, (label, command) in enumerate((("Gerar com IA", self.generate),
                ("Nova versão com IA", lambda: self.generate(True)), ("Salvar edição", lambda: self.save("EDITADA")),
                ("Aprovar versão", lambda: self.save("APROVADA")), ("Descartar versão", self.discard_version))):
            host = self.options if inline and index in (0, 1, 3, 4) else actions
            row, column = (({0: (0, 0), 1: (0, 1), 2: (0, 0), 3: (1, 0), 4: (1, 1)}[index]) if inline else divmod(index, 3))
            host.grid_columnconfigure(column, weight=1, uniform="actions")
            control = button(host, label, command, kind="primary" if index == 0 else "secondary", width=90, height=32 if inline else 40)
            control.grid(row=row, column=column, padx=4, pady=4, sticky="ew")
            self.buttons.append(control)
        self.feedback = StatusBar(self, text="Revise a mensagem antes de abrir a conversa." if inline else "Revisão humana obrigatória. Confiança não é probabilidade de venda.", wraplength=300 if inline else 650, font=TYPOGRAPHY["caption"], text_color=COLORS["muted"], justify="left", anchor="w")
        self.feedback.pack(fill="x", padx=12, pady=2 if inline else 8)
        copy = button(actions if inline else self, "Copiar mensagem", self.copy_message, kind="ghost", width=90, height=32 if inline else 40)
        if inline:
            actions.grid_columnconfigure(1, weight=1, uniform="actions")
            copy.grid(row=0, column=1, sticky="ew", padx=4, pady=4)
            # Reserve actions first; only the text editor absorbs reduced height.
            for widget in (self.message, self.reason, actions, self.feedback):
                widget.pack_forget()
            self.feedback.pack(side="bottom", fill="x", padx=12, pady=2)
            actions.pack(side="bottom", fill="x", padx=8, pady=4)
            self.message.pack(fill="both", expand=True, padx=12)
        else:
            copy.pack(anchor="w", padx=12, pady=4)
        self.character_count = ctk.CTkLabel(actions if inline else self, text="0 caracteres", anchor="e", width=90,
            font=TYPOGRAPHY["caption"], text_color=COLORS["muted"])
        if inline:
            self.character_count.grid(row=0, column=2, padx=(4, 0), sticky="e")
        else:
            self.character_count.pack(fill="x", padx=12)
        if inline:
            self.info.pack_forget()
            self.metadata = ctk.CTkFrame(self, fg_color="transparent", height=28)
            self.metadata.pack(fill="x", padx=12, pady=4, before=self.message)
            self.metadata.grid_columnconfigure(0, weight=1)
            self.angle = ctk.CTkLabel(self.metadata,text="",font=TYPOGRAPHY["caption"],anchor="w",width=100)
            self.angle.grid(row=0, column=0, sticky="ew")
            self.confidence = badge(self.metadata, "Confiança")
            self.confidence.grid(row=0, column=1, padx=4)
            self.version_status = badge(self.metadata, "Sem rascunho", "draft")
            self.version_status.grid(row=0, column=2)
        self.refresh()
        if inline:
            self._wrap = WrappedLabels(self, (self.info, self.feedback), padding=32, minimum=120)

    def message_modified(self, event=None):
        if self.message._textbox.edit_modified():
            self.message._textbox.edit_modified(False)
            self.update_presentation()
            notify_state(self)

    def update_presentation(self):
        """Reflect the current draft without changing stored state or permissions."""
        if hasattr(self, "character_count"):
            self.character_count.configure(text=f"{len(self.message.get('1.0', 'end-1c'))} caracteres")
        if hasattr(self, "metadata"):
            row = next((r for r in self.rows.values() if r["id"] == self.current_id), None)
            text, tone = confidence_badge(row["confianca"] if row else None)
            self.angle.configure(text=f"Ângulo: {row['angulo']}" if row else "Gere um rascunho em Mais ações para começar.")
            self.confidence.configure(text=text, text_color=COLORS[tone] if tone != "neutral" else COLORS["muted"])
            self.version_status.configure(text=STATUS_LABELS.get(row["status"], row["status"]) if row else "Sem rascunho")

    def change_contact_type(self, label):
        selected = CONTACT_TYPES.get(label)
        if selected is None:
            return
        previous = self.contact_type
        try:
            self.contact_preferences.save(self.lead_id, selected)
            self.contact_type = selected
            self.snapshot = None
            self.contact_type_label.configure(text="Contato provável · manual")
            self.feedback.configure(text="Tipo salvo para a próxima geração. Rascunho atual mantido; nova versão em Mais ações.")
        except Exception:
            self.contact_type_selector.set(next(label for label, value in CONTACT_TYPES.items() if value == previous))
            self.feedback.configure(text="Não foi possível salvar o tipo de contato. A escolha anterior foi mantida.")

    def refresh_contact_type(self):
        if self.busy:
            return
        lead = self.repository.get_lead(self.lead_id)
        if lead is None:
            return
        override = self.contact_preferences.get(self.lead_id)
        self.contact_type = override or classify_contact(lead["segmento"])
        self.contact_type_selector.set(next(label for label, value in CONTACT_TYPES.items() if value == self.contact_type))
        self.contact_type_label.configure(text="Contato provável · manual" if override else "Contato provável · pelo nicho")

    def toggle_reason(self):
        if self.options.winfo_manager():
            self.options.pack_forget()
        else:
            self.options.pack(side="bottom", fill="x", padx=8, pady=4, before=self.message)
            self.reason.focus_set()

    def copy_message(self):
        self.feedback.configure(text=copy_to_clipboard(self, self.message.get("1.0", "end-1c")))

    def confirm_discard(self):
        if self.message.get("1.0", "end-1c") == self.loaded_text:
            return True
        # Save directly here: refreshing the selector would re-enter this guard.
        def save_pending():
            try:
                if self.busy or self.current_id is None:
                    return False
                text = self.message.get("1.0", "end-1c")
                self.outreach.update(self.lead_id, self.current_id, status="EDITADA", message=text)
                self.loaded_text = text
                for row in self.rows.values():
                    if row["id"] == self.current_id:
                        row.update(mensagem=text, status="EDITADA")
                self.feedback.configure(text="Edição salva. Nenhuma mensagem foi enviada.")
                return True
            except Exception:
                self.feedback.configure(text="Não foi possível salvar a edição. Revise a mensagem e tente novamente.")
                return False
        return resolve_pending(self, "Mensagem com IA", save_pending)

    def discard_version(self):
        if self.confirm_discard():
            self.save("CANCELADA")

    def refresh(self, selected=None):
        rows = self.outreach.history(self.lead_id)
        self.rows = {draft_label(r): dict(r) for r in rows}
        saved = any(row["status"] != "CANCELADA" for row in self.rows.values())
        self.buttons[0].configure(text="Abrir rascunho salvo" if saved else "Gerar com IA",
            fg_color=COLORS["surface_secondary"] if saved else COLORS["primary"],
            hover_color=COLORS["surface_hover"] if saved else COLORS["primary_hover"])
        self.buttons[1].configure(state="normal" if saved and not self.busy else "disabled")
        self.history.configure(values=list(self.rows) or ["Nenhuma abordagem"])
        choice = next((label for label, row in self.rows.items() if row["id"] == selected), next(iter(self.rows), "Nenhuma abordagem"))
        self.history.set(choice)
        self.select(choice)

    def select(self, label):
        if getattr(self, "current_id", None) is not None and not self.confirm_discard():
            previous = next((name for name, row in self.rows.items() if row["id"] == self.current_id), None)
            if previous:
                self.history.set(previous)
            return
        # A discard choice permits replacement without a second prompt.
        self.loaded_text = self.message.get("1.0", "end-1c")
        row = self.rows.get(label)
        self.current_id = row["id"] if row else None
        self.message.configure(state="normal")
        self.message.delete("1.0", "end")
        if row:
            self.message.insert("1.0", row["mensagem"])
        self.loaded_text = row["mensagem"] if row else ""
        self.info.configure(text=f"Ângulo: {row['angulo']} · Confiança: {row['confianca']} · {row['status']}" if row else "Gere um rascunho para revisar.")
        editable = bool(row and row["status"] in ("GERADA", "EDITADA"))
        self.message.configure(state="normal" if editable else "disabled")
        for control in self.buttons[2:]:
            control.configure(state="normal" if editable and not self.busy else "disabled")
        self.update_presentation()
        notify_state(self)

    def generate(self, regenerate=False):
        if self.busy:
            return
        if hasattr(self, "loaded_text") and not self.confirm_discard():
            return
        if not regenerate:
            saved = next((row for row in getattr(self, "rows", {}).values() if row["status"] != "CANCELADA"), None)
            if saved:
                self.loaded_text = self.message.get("1.0", "end-1c")
                self.refresh(saved["id"])
                self.feedback.configure(text="Rascunho salvo aberto. Use Nova versão com IA para criar outro texto.")
                return
        reason = self.reason.get() if regenerate and hasattr(self, "reason") else ""
        try:
            provider = create_sales_provider()
            self.active_provider = provider
        except SalesConfigurationError as error:
            self.feedback.configure(text=str(error))
            return
        except Exception:
            log_current_error()
            self.feedback.configure(text="Confira a configuração de IA e se o lead ainda existe.")
            return
        self.busy = True
        if hasattr(self, "contact_type_selector"):
            self.contact_type_selector.configure(state="disabled")
        notify_state(self)
        for control in self.buttons:
            control.configure(state="disabled")
        self.history.configure(state="disabled")
        self.message.configure(state="disabled")
        self.feedback.configure(text="Gerando rascunho…")
        if hasattr(self, "reason"):
            self.reason.configure(state="disabled")
        def worker():
            try:
                agent = SalesAgent(self.repository, provider)
                if not regenerate or self.snapshot is None:
                    self.snapshot = agent.evidence(self.lead_id)
                self.pending.put((agent.generate(self.lead_id, evidence=self.snapshot,
                    reuse_existing=not regenerate, regeneration_reason=reason if regenerate else None), None))
            except SalesGenerationError as error:
                self.pending.put((None, str(error)))
            except Exception:
                log_current_error()
                self.pending.put((None, "Não foi possível gerar/salvar o rascunho. Confira a configuração e tente novamente."))
        threading.Thread(target=worker, daemon=True).start()
        self.job = self.after(100, self.poll)

    def poll(self):
        self.job = None
        try:
            draft_id, error = self.pending.get_nowait()
        except queue.Empty:
            self.job = self.after(100, self.poll)
            return
        self.busy = False
        if hasattr(self, "contact_type_selector"):
            self.contact_type_selector.configure(state="readonly")
        if hasattr(self, "reason"):
            self.reason.configure(state="normal")
        for control in self.buttons[:2]:
            control.configure(state="normal")
        self.history.configure(state="readonly")
        if error:
            row = next((r for r in self.rows.values() if r["id"] == self.current_id), None)
            editable = bool(row and row["status"] in ("GERADA", "EDITADA"))
            self.message.configure(state="normal" if editable else "disabled")
            for control in self.buttons[2:]:
                control.configure(state="normal" if editable else "disabled")
        else:
            if hasattr(self, "loaded_text"):
                self.loaded_text = self.message.get("1.0", "end-1c")
            self.refresh(draft_id)
        self.feedback.configure(text=error or "Rascunho salvo. Revise antes de aprovar.")
        notify_state(self)
        if getattr(self, "on_completed", None):
            self.on_completed(self.active_provider, error)

    def save(self, status):
        if self.busy or self.current_id is None:
            return
        try:
            self.outreach.update(self.lead_id, self.current_id, status=status, message=self.message.get("1.0", "end-1c"))
            if hasattr(self, "loaded_text"):
                self.loaded_text = self.message.get("1.0", "end-1c")
            self.refresh(self.current_id)
            self.feedback.configure(text="Versão salva. Nenhuma mensagem foi enviada.")
            if getattr(self, "on_completed", None):
                self.on_completed(None, None)
        except (ValueError, LookupError) as error:
            self.feedback.configure(text=str(error))
        except Exception:
            log_current_error()
            self.feedback.configure(text="Não foi possível salvar a versão no banco local.")

    def destroy(self):
        if self.job is not None:
            self.after_cancel(self.job)
        # An in-flight HTTP request may finish and save GERADA; never APPROVADA.
        super().destroy()
