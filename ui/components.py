"""Small reusable desktop primitives; callbacks and widget APIs stay native."""
from tkinter import ttk
import customtkinter as ctk
from ui.theme import COLORS, FONT, SPACING, RADIUS, TYPOGRAPHY, SIZES


def button_options(kind="secondary"):
    styles = {
        "primary": dict(fg_color=COLORS["primary"], hover_color=COLORS["primary_hover"], text_color=COLORS["text"]),
        "secondary": dict(fg_color=COLORS["surface_secondary"], hover_color=COLORS["surface_hover"], text_color=COLORS["text"]),
        "ghost": dict(fg_color="transparent", hover_color=COLORS["surface_hover"], text_color=COLORS["text_secondary"]),
        "danger": dict(fg_color=COLORS["danger_surface"], hover_color=COLORS["danger_hover"], text_color=COLORS["danger"]),
    }
    return {**styles[kind], "height": SIZES["control"], "corner_radius": RADIUS["control"],
            "font": TYPOGRAPHY["button"], "text_color_disabled": COLORS["disabled"]}


def button(parent, text, command, *, kind="secondary", **kwargs):
    return ctk.CTkButton(parent, text=text, command=command, **{**button_options(kind), **kwargs})


def heading(parent, title, subtitle=""):
    frame = ctk.CTkFrame(parent, fg_color="transparent")
    frame.pack(fill="x", padx=SPACING["page"], pady=(SPACING["page"], SPACING["section"]))
    ctk.CTkLabel(frame, text=title, font=TYPOGRAPHY["title"], text_color=COLORS["text"]).pack(anchor="w")
    if subtitle:
        ctk.CTkLabel(frame, text=subtitle, font=TYPOGRAPHY["secondary"], text_color=COLORS["muted"], anchor="w").pack(anchor="w", pady=(4, 0))
    return frame


def section_label(parent, text):
    widget = ctk.CTkLabel(parent, text=text, font=TYPOGRAPHY["section"], text_color=COLORS["text"])
    widget.pack(anchor="w", pady=(12, 8))
    return widget


def field(parent, label, *, options=None, value="", **kwargs):
    ctk.CTkLabel(parent, text=label, font=TYPOGRAPHY["secondary"], text_color=COLORS["text_secondary"]).pack(anchor="w", pady=(0, 5))
    widget = (ctk.CTkComboBox(parent, values=list(options), height=SIZES["control"], **kwargs)
              if options is not None else ctk.CTkEntry(parent, height=SIZES["control"], **kwargs))
    if options is not None:
        widget.set(value)
    elif value:
        widget.insert(0, value)
    widget.pack(fill="x")
    return widget


class StatCard(ctk.CTkFrame):
    def __init__(self, master, title, value, subtitle="", tone="text"):
        super().__init__(master, fg_color=COLORS["surface"], corner_radius=RADIUS["surface"])
        ctk.CTkLabel(self, text=title, font=TYPOGRAPHY["caption"], text_color=COLORS["text_secondary"]).pack(anchor="w", padx=16, pady=(12, 0))
        self.value = ctk.CTkLabel(self, text=str(value), font=TYPOGRAPHY["value"], text_color=COLORS[tone])
        self.value.pack(anchor="w", padx=16, pady=(0, 12 if not subtitle else 0))
        if subtitle:
            ctk.CTkLabel(self, text=subtitle, font=TYPOGRAPHY["caption"], text_color=COLORS["muted"]).pack(anchor="w", padx=16, pady=(0, 12))

    def set(self, value):
        self.value.configure(text=str(value))


class MetricStrip(ctk.CTkFrame):
    def __init__(self, master, metrics):
        super().__init__(master, fg_color="transparent")
        self.cards = {}
        for column, (key, title, tone) in enumerate(metrics):
            self.grid_columnconfigure(column, weight=1, uniform="metrics")
            card = StatCard(self, title, "—", tone=tone)
            card.grid(row=0, column=column, sticky="ew", padx=(0 if column == 0 else 8, 0))
            self.cards[key] = card

    def set(self, values):
        for key, card in self.cards.items():
            card.set(values.get(key, "—"))


def badge(parent, text, tone="neutral"):
    fg, color = {"neutral": ("surface_secondary", "text_secondary"), "accent": ("selected", "accent"),
                 "success": ("success_surface", "success"), "warning": ("warning_surface", "warning"),
                 "danger": ("danger_surface", "danger")}[tone]
    return ctk.CTkLabel(parent, text=text, fg_color=COLORS[fg], text_color=COLORS[color],
                       corner_radius=RADIUS["badge"], font=TYPOGRAPHY["caption"], padx=10, height=26)


def style_table(master):
    style = ttk.Style(master)
    if style.theme_use() != "clam":
        style.theme_use("clam")
    style.configure("Loung.Treeview", background=COLORS["surface"], fieldbackground=COLORS["surface"],
        foreground=COLORS["text_secondary"], borderwidth=0, rowheight=SIZES["row"], font=(FONT, 10))
    style.configure("Loung.Treeview.Heading", background=COLORS["surface_secondary"], foreground=COLORS["text"],
        relief="flat", borderwidth=0, padding=(10, 10), font=(FONT, 10, "bold"))
    style.map("Loung.Treeview", background=[("selected", COLORS["selected"])], foreground=[("selected", COLORS["text"])])
    style.map("Loung.Treeview.Heading", background=[("active", COLORS["surface_hover"])])
    for orientation in ("Vertical", "Horizontal"):
        style.configure(f"Loung.{orientation}.TScrollbar", troughcolor=COLORS["bg"], background=COLORS["border"],
            bordercolor=COLORS["bg"], arrowcolor=COLORS["muted"], lightcolor=COLORS["border"], darkcolor=COLORS["border"])


def table(parent, columns, widths=None):
    style_table(parent)
    widget = ttk.Treeview(parent, columns=columns, show="headings", selectmode="browse", style="Loung.Treeview")
    for name in columns:
        widget.heading(name, text=name, anchor="w")
        widget.column(name, width=(widths or {}).get(name, 145), minwidth=65, anchor="w")
    vertical = ttk.Scrollbar(parent, orient="vertical", command=widget.yview, style="Loung.Vertical.TScrollbar")
    horizontal = ttk.Scrollbar(parent, orient="horizontal", command=widget.xview, style="Loung.Horizontal.TScrollbar")
    widget.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
    vertical.pack(side="right", fill="y")
    horizontal.pack(side="bottom", fill="x")
    widget.pack(fill="both", expand=True)
    widget.tag_configure("alternate", background=COLORS["surface_secondary"])
    return widget


def empty_message(parent, text=""):
    widget = ctk.CTkLabel(parent, text=text, font=TYPOGRAPHY["body"], text_color=COLORS["muted"])
    widget.pack(anchor="w", padx=SPACING["page"], pady=SPACING["sm"])
    return widget
