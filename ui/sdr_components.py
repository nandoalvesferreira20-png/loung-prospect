"""Small presentation components; no repository, provider or contact decisions."""
import tkinter as tk
import customtkinter as ctk
from ui.theme import COLORS, TYPOGRAPHY, RADIUS, SPACING
from ui.components import button, badge
from ui.responsive_text import WrappedLabels
from ui.sdr_formatting import feedback_tone


class Card(ctk.CTkFrame):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **{**dict(fg_color=COLORS["bg_elevated"],
            border_color=COLORS["border"], border_width=1, corner_radius=RADIUS["surface"]), **kwargs})


class FullWidthTabs(ctk.CTkTabview):
    """Keep CTk's native tab API while extending its tab bar to the panel width."""
    def _set_grid_segmented_button(self):
        super()._set_grid_segmented_button()
        self._segmented_button.grid_configure(sticky="nsew")


class LineIcon(tk.Canvas):
    """One local vector icon family, drawn without image/font dependencies."""
    def __init__(self, parent, name, *, background=None, color=None, size=20):
        super().__init__(parent, width=size, height=size, highlightthickness=0,
                         bg=background or COLORS["sidebar"])
        self.name, self.color, self.size = name, color or COLORS["text_secondary"], size
        self.paint()

    def paint(self):
        self.delete("all")
        k = self.size / 24
        def line(*coords):
            self.create_line(*(v*k for v in coords), fill=self.color, width=1.7)
        def rect(*coords):
            self.create_rectangle(*(v*k for v in coords), outline=self.color, width=1.7)
        def oval(*coords):
            self.create_oval(*(v*k for v in coords), outline=self.color, width=1.7)
        if self.name in ("places", "search"):
            oval(3, 3, 15, 15); line(14, 14, 21, 21)
        elif self.name == "dashboard":
            for x, y in ((3,3), (14,3), (3,14), (14,14)):
                rect(x, y, x+7, y+7)
        elif self.name == "day":
            oval(3,3,21,21); line(12,6,12,12,17,15)
        elif self.name == "sales":
            line(3,4,21,4,21,17,9,17,4,21,4,17,3,17,3,4)
            line(7,8,17,8); line(7,12,14,12)
        elif self.name == "prototype":
            rect(3,3,21,21); line(3,9,21,9); line(9,9,9,21)
        elif self.name == "refresh":
            self.create_arc(3*k,3*k,21*k,21*k,start=35,extent=285,style="arc",outline=self.color,width=1.7)
            line(19,2,20,8,14,7)
        elif self.name == "clear":
            line(6,6,18,18); line(6,18,18,6)
        else:
            rect(4,3,20,21)
            for y in (8,12,16): line(8,y,17,y)


class KpiCard(Card):
    def __init__(self, parent, title, tone="accent", icon="workspace"):
        super().__init__(parent)
        self.grid_columnconfigure(0, weight=1)
        self.value = ctk.CTkLabel(self, text="—", font=TYPOGRAPHY["kpi"], height=28, text_color=COLORS[tone], anchor="w")
        self.value.grid(row=0,column=0,sticky="w",padx=SPACING["md"],pady=(SPACING["xs"],0))
        LineIcon(self, icon, background=COLORS["bg_elevated"], color=COLORS[tone], size=18).grid(row=0,column=1,padx=SPACING["md"])
        ctk.CTkLabel(self,text=title,height=18,font=TYPOGRAPHY["caption"],text_color=COLORS["text_secondary"]).grid(
            row=1,column=0,columnspan=2,sticky="w",padx=SPACING["md"],pady=(0,SPACING["sm"]))


class StatusDot(ctk.CTkFrame):
    def __init__(self, parent, text):
        super().__init__(parent, fg_color="transparent")
        self.dot = ctk.CTkLabel(self, text="●", width=16)
        self.dot.pack(side="left")
        self.label = ctk.CTkLabel(self, text=text, font=TYPOGRAPHY["caption"], text_color=COLORS["muted"])
        self.label.pack(side="left", padx=SPACING["xs"])
        self.configure(text=text)

    def configure(self, **kwargs):
        text = kwargs.pop("text", None)
        if text is not None:
            tone = "success" if text == "Groq conectada" else "danger" if text in ("Erro de conexão", "Groq não configurada") else "warning"
            self.dot.configure(text_color=COLORS[tone])
            self.label.configure(text=text)
        super().configure(**kwargs)

    def cget(self, key):
        return self.label.cget(key) if key == "text" else super().cget(key)


class Stepper(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")
        self.steps = []
        for i, title in enumerate(("Selecionar lead", "Revisar mensagem", "Abrir WhatsApp")):
            label = ctk.CTkLabel(self,text=f"{i+1}  {title}",font=TYPOGRAPHY["caption"],corner_radius=8)
            label.grid(row=0,column=i,sticky="ew",padx=(0,SPACING["sm"]))
            self.grid_columnconfigure(i,weight=1)
            self.steps.append(label)
        self.set(0)

    def set(self, active):
        for i, label in enumerate(self.steps):
            label.configure(text_color=COLORS["text"] if i == active else COLORS["muted"],
                            fg_color=COLORS["selected"] if i == active else "transparent")


class StatusBar(ctk.CTkLabel):
    """Label-compatible feedback with cancellable expiry, no toast windows."""
    def __init__(self, parent, *, timeout=8000, **kwargs):
        self.expiry = None
        self.timeout = timeout
        super().__init__(parent, **{**dict(text="", anchor="w", justify="left", font=TYPOGRAPHY["caption"],
            fg_color=COLORS["bg_elevated"], corner_radius=8, padx=12, pady=6,
            text_color=COLORS["text_secondary"]), **kwargs})

    def configure(self, **kwargs):
        if "text" in kwargs:
            kwargs.setdefault("text_color", COLORS[feedback_tone(kwargs["text"])])
            if self.expiry is not None:
                self.after_cancel(self.expiry)
                self.expiry = None
            if self.timeout and kwargs["text"] and not kwargs["text"].startswith(("Gerando", "Abrindo")):
                self.expiry = self.after(self.timeout, self.clear)
        super().configure(**kwargs)

    def clear(self):
        self.expiry = None
        super().configure(text="")

    def destroy(self):
        if self.expiry is not None:
            self.after_cancel(self.expiry)
        super().destroy()


class LeadListItem(Card):
    def __init__(self, parent):
        super().__init__(parent, cursor="hand2", border_width=2)
        self.name = ctk.CTkLabel(self,text="",font=TYPOGRAPHY["list_title"],anchor="w",justify="left")
        self.name.pack(fill="x",padx=12,pady=(8,0))
        self.details = ctk.CTkLabel(self,text="",font=TYPOGRAPHY["caption"],text_color=COLORS["muted"],anchor="w")
        self.details.pack(fill="x",padx=12)
        self.tags = ctk.CTkFrame(self,fg_color="transparent")
        self.tags.pack(fill="x",padx=12,pady=(4,8))
        self.stage = badge(self.tags,"Novo","accent")
        self.stage.pack(side="left",padx=(0,4))
        self.draft = badge(self.tags,"Sem rascunho")
        self.draft.pack(side="left")
        self._wrap = WrappedLabels(self,(self.name,self.details),padding=24)

    def selected(self, active):
        self.configure(fg_color=COLORS["bg_elevated"] if active else COLORS["bg_surface"],
                       border_color=COLORS["accent"] if active else COLORS["border"])


def PrimaryButton(parent, text, command, **kwargs):
    return button(parent,text,command,kind="primary",**kwargs)


def SecondaryButton(parent, text, command, **kwargs):
    return button(parent,text,command,kind="secondary",**kwargs)


def GhostButton(parent, text, command, **kwargs):
    return button(parent,text,command,kind="ghost",**kwargs)


def IconButton(parent, text, command, **kwargs):
    control = button(parent,"",command,kind="ghost",**{**dict(width=32,height=32), **kwargs})
    attach_icon(control, text, background=COLORS["surface"])
    return control


def attach_icon(control, name, *, background=None):
    icon = LineIcon(control, name, size=16, background=background or COLORS["surface_secondary"])
    icon.place(x=8, rely=.5, anchor="w")
    icon.bind("<Button-1>", lambda event: control.invoke())
    control.vector_icon = icon
    return control
