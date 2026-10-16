"""Explicit human generation and clipboard only; no commercial writes."""
import customtkinter as ctk

from core.outreach import OutreachRequest, TemplateOutreachGenerator, context_from_lead
from ui.components import button, field
from ui.copy_field import copy_to_clipboard
from ui.theme import COLORS
from ui.pending_edits import resolve_pending

CHANNEL_LABELS = {"WhatsApp": "whatsapp", "Instagram": "instagram", "Telefone": "phone"}
OBJECTIVE_LABELS = {"Primeiro contato": "first_contact", "Follow-up": "follow_up", "Reativação": "reactivation"}
TONE_LABELS = {"Profissional e próximo": "professional", "Amigável": "friendly", "Direto": "direct"}


class OutreachSession:
    def __init__(self, generator=None):
        self.generator = generator if generator is not None else TemplateOutreachGenerator()
        self.last_result = None
        self.selection = None
        self.variation = 0

    def generate(self, lead, channel, objective, tone, another=False):
        selection = (channel, objective, tone)
        variation = (self.variation + 1) % 3 if another and self.last_result and selection == self.selection else 0
        result = self.generator.generate(OutreachRequest(context_from_lead(lead), channel, objective, tone, variation))
        self.last_result, self.selection, self.variation = result, selection, variation
        return result


class OutreachPanel(ctk.CTkFrame):
    def __init__(self, master, load_lead, drafts=None, lead_id=None):
        super().__init__(master, fg_color="transparent")
        self.pack(fill="both", expand=True)
        self.load_lead = load_lead  # fresh read on explicit generation, including responsible
        self.session = OutreachSession()
        self.drafts, self.lead_id = drafts, lead_id
        self.loaded_text = ""
        controls = ctk.CTkFrame(self, fg_color="transparent")
        controls.pack(fill="x", padx=12)
        self.selectors = []
        for label, mapping in (("Canal", CHANNEL_LABELS), ("Objetivo", OBJECTIVE_LABELS), ("Tom", TONE_LABELS)):
            column = ctk.CTkFrame(controls, fg_color="transparent")
            column.pack(side="left", fill="x", expand=True, padx=4)
            control = field(column, label, options=list(mapping), value=next(iter(mapping)), state="readonly")
            self.selectors.append((control, mapping))
        ctk.CTkLabel(self, text="Mensagem por modelo · sem IA. Salve o rascunho para continuar depois. Revise antes de copiar.",
                     text_color=COLORS["muted"], wraplength=630).pack(padx=16, pady=8, anchor="w")
        self.message = ctk.CTkTextbox(self, wrap="word")
        self.message.pack(fill="both", expand=True, padx=16, pady=8)
        actions = ctk.CTkFrame(self, fg_color="transparent")
        actions.pack(fill="x", padx=16, pady=8)
        button(actions, "Gerar por modelo", self.generate, kind="primary", width=130).pack(side="left", padx=(0, 8))
        self.another = button(actions, "Nova versão por modelo", lambda: self.generate(another=True), state="disabled", width=165)
        self.another.pack(side="left", padx=(0, 8))
        button(actions, "Salvar rascunho", self.save, width=130).pack(side="left", padx=(0, 8))
        button(actions, "Copiar", self.copy_message, kind="ghost", width=75).pack(side="left")
        self.feedback = ctk.CTkLabel(self, text="", wraplength=630, justify="left", text_color=COLORS["muted"])
        self.feedback.pack(fill="x", padx=16, pady=(0, 8))
        if drafts is not None:
            saved = drafts.load(lead_id)
            if saved:
                self.loaded_text = saved["message"]
                self.message.insert("1.0", saved["message"])
                for (control, mapping), key in zip(self.selectors, ("channel", "objective", "tone")):
                    control.set(next((label for label, value in mapping.items() if value == saved[key]), next(iter(mapping))))
                self.feedback.configure(text="Rascunho salvo carregado. Nenhuma mensagem foi enviada.")

    def has_pending_edits(self):
        return self.message.get("1.0", "end-1c") != self.loaded_text

    def confirm_pending(self):
        return not self.has_pending_edits() or resolve_pending(self, "Mensagem por modelo", self.save)

    def save(self):
        try:
            if self.drafts is None:
                raise ValueError("Não foi possível acessar os rascunhos. Reabra os detalhes.")
            text = self.message.get("1.0", "end-1c")
            choices = [mapping[control.get()] for control, mapping in self.selectors]
            self.drafts.save(self.lead_id, text, *choices)
            self.loaded_text = text
            self.feedback.configure(text="Rascunho por modelo salvo. Nenhuma mensagem foi enviada.")
            return True
        except Exception as error:
            self.feedback.configure(text=f"Não foi possível salvar: {error}")
            return False

    def generate(self, another=False):
        if self.has_pending_edits() and not self.confirm_pending():
            return
        try:
            lead = self.load_lead()
            if lead is None:
                raise ValueError("Lead não encontrado. Reabra os detalhes.")
            choices = [mapping[control.get()] for control, mapping in self.selectors]
            result = self.session.generate(lead, *choices, another=another)
        except (ValueError, TypeError, KeyError) as error:
            self.feedback.configure(text=f"Não foi possível gerar: {error}")
            return
        self.message.delete("1.0", "end")
        self.message.insert("1.0", result.message)
        self.another.configure(state="normal")
        self.feedback.configure(text=" · ".join((f"Versão {self.session.variation + 1}/3 · {len(result.message)} caracteres", *result.warnings)))

    def copy_message(self):
        self.feedback.configure(text=copy_to_clipboard(self, self.message.get("1.0", "end-1c")))
