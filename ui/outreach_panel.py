"""Explicit human generation and clipboard only; no commercial writes."""
import customtkinter as ctk

from core.outreach import OutreachRequest, TemplateOutreachGenerator, context_from_lead
from ui.components import button, field
from ui.copy_field import copy_to_clipboard
from ui.theme import COLORS

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
    def __init__(self, master, load_lead):
        super().__init__(master, fg_color="transparent")
        self.pack(fill="both", expand=True)
        self.load_lead = load_lead  # fresh read on explicit generation, including responsible
        self.session = OutreachSession()
        controls = ctk.CTkFrame(self, fg_color="transparent")
        controls.pack(fill="x", padx=12)
        self.selectors = []
        for label, mapping in (("Canal", CHANNEL_LABELS), ("Objetivo", OBJECTIVE_LABELS), ("Tom", TONE_LABELS)):
            column = ctk.CTkFrame(controls, fg_color="transparent")
            column.pack(side="left", fill="x", expand=True, padx=4)
            control = field(column, label, options=list(mapping), value=next(iter(mapping)), state="readonly")
            self.selectors.append((control, mapping))
        ctk.CTkLabel(self, text="Revise e edite antes de copiar. Nenhum contato é enviado ou registrado.",
                     text_color=COLORS["muted"], wraplength=630).pack(padx=16, pady=8, anchor="w")
        self.message = ctk.CTkTextbox(self, wrap="word")
        self.message.pack(fill="both", expand=True, padx=16, pady=8)
        actions = ctk.CTkFrame(self, fg_color="transparent")
        actions.pack(fill="x", padx=16, pady=8)
        button(actions, "Gerar mensagem", self.generate, kind="primary").pack(side="left", padx=(0, 8))
        self.another = button(actions, "Gerar outra versão", lambda: self.generate(another=True), state="disabled")
        self.another.pack(side="left", padx=(0, 8))
        button(actions, "Copiar", self.copy_message, kind="ghost").pack(side="left")
        self.feedback = ctk.CTkLabel(self, text="", wraplength=630, justify="left", text_color=COLORS["muted"])
        self.feedback.pack(fill="x", padx=16, pady=(0, 8))

    def generate(self, another=False):
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
