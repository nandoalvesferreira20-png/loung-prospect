"""Small reusable desktop primitives; callbacks and widget APIs stay native."""
from tkinter import ttk
import customtkinter as ctk
from ui.responsive_text import WrappedLabels
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


def keyboard_focus(container):
    """Opt-in keyboard/focus treatment, keeping the shared palette and controls."""
    for widget in container.winfo_children():
        if isinstance(widget, (ctk.CTkButton, ctk.CTkEntry, ctk.CTkComboBox, ctk.CTkTextbox)):
            original_color, original_width = widget.cget("border_color"), widget.cget("border_width")
            widget.bind("<FocusIn>", lambda event, w=widget: w.configure(border_color=COLORS["accent"], border_width=2), add="+")
            widget.bind("<FocusOut>", lambda event, w=widget, color=original_color, width=original_width: w.configure(border_color=color, border_width=width), add="+")
            if isinstance(widget, ctk.CTkButton):
                widget._canvas.configure(takefocus=1)
                widget.bind("<Return>", lambda event, w=widget: w.invoke(), add="+")
                widget.bind("<space>", lambda event, w=widget: w.invoke(), add="+")
            elif isinstance(widget, ctk.CTkComboBox):
                widget.bind("<Alt-Down>", lambda event, w=widget: w._open_dropdown_menu(), add="+")
        else:
            keyboard_focus(widget)


def heading(parent, title, subtitle=""):
    frame = ctk.CTkFrame(parent, fg_color="transparent")
    frame.pack(fill="x", padx=SPACING["page"], pady=(SPACING["page"], SPACING["section"]))
    title_label = ctk.CTkLabel(frame, text=title, font=TYPOGRAPHY["title"], text_color=COLORS["text"], anchor="w", justify="left")
    title_label.pack(fill="x")
    labels = [title_label]
    if subtitle:
        subtitle_label = ctk.CTkLabel(frame, text=subtitle, font=TYPOGRAPHY["secondary"], text_color=COLORS["muted"], anchor="w", justify="left")
        subtitle_label.pack(fill="x", pady=(4, 0))
        labels.append(subtitle_label)
    line = ctk.CTkFrame(frame, height=1, fg_color=COLORS["border"])
    line.pack(fill="x", pady=(16, 0))
    frame._wrap = WrappedLabels(frame, labels, padding=0, minimum=150)
    return frame


def panel(parent):
    """Shared surface; keep native geometry APIs and caller-owned contents."""
    return ctk.CTkFrame(parent, fg_color=COLORS["surface"], border_width=1,
                       border_color=COLORS["border"], corner_radius=RADIUS["surface"])


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
        super().__init__(master, fg_color=COLORS["surface"], corner_radius=RADIUS["surface"], border_width=1, border_color=COLORS["border"])
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
                 "danger": ("danger_surface", "danger"), "draft": ("draft_surface", "draft")}[tone]
    return ctk.CTkLabel(parent, text=text, fg_color=COLORS[fg], text_color=COLORS[color],
                       corner_radius=RADIUS["badge"], font=TYPOGRAPHY["caption"], padx=10, height=26)


def style_table(master):
    style = ttk.Style(master)
    if style.theme_use() != "clam":
        style.theme_use("clam")
    style.configure("Loung.Treeview", background=COLORS["surface"], fieldbackground=COLORS["surface"],
        foreground=COLORS["text_secondary"], borderwidth=0, rowheight=SIZES["row"], font=(FONT, 11))
    style.configure("Loung.Treeview.Heading", background=COLORS["surface_secondary"], foreground=COLORS["text"],
        relief="flat", borderwidth=0, padding=(10, 10), font=(FONT, 10, "bold"))
    style.map("Loung.Treeview", background=[("selected", COLORS["selected"])], foreground=[("selected", COLORS["text"])])
    style.map("Loung.Treeview.Heading", background=[("active", COLORS["surface_hover"])])
    for orientation in ("Vertical", "Horizontal"):
        style.configure(f"Loung.{orientation}.TScrollbar", troughcolor=COLORS["bg"], background=COLORS["border"],
            bordercolor=COLORS["bg"], arrowcolor=COLORS["muted"], lightcolor=COLORS["border"], darkcolor=COLORS["border"])


def table(parent, columns, widths=None, *, compact_columns=None):
    style_table(parent)
    widget = ttk.Treeview(parent, columns=columns, show="headings", selectmode="browse", style="Loung.Treeview")
    for name in columns:
        widget.heading(name, text=name, anchor="w")
        widget.column(name, width=(widths or {}).get(name, 145), minwidth=50, anchor="w", stretch=False)
    vertical = ttk.Scrollbar(parent, orient="vertical", command=widget.yview, style="Loung.Vertical.TScrollbar")
    horizontal = ttk.Scrollbar(parent, orient="horizontal", command=widget.xview, style="Loung.Horizontal.TScrollbar")
    widget.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
    vertical.pack(side="right", fill="y")
    horizontal.pack(side="bottom", fill="x")
    widget.pack(fill="both", expand=True)
    widget.tag_configure("alternate", background=COLORS["surface_secondary"])
    preferred = {name: (widths or {}).get(name, 145) for name in columns}
    state = {"width": None, "job": None}
    def fit():
        state["job"] = None
        available = max(1, state["width"] - 4)
        # Keep every column reachable; primary columns lead and overflow scrolls.
        visible = tuple(dict.fromkeys((*(compact_columns or ()), *columns)))
        widget.configure(displaycolumns=visible)
        total = sum(preferred[name] for name in visible)
        for name in visible:
            width = preferred[name]
            widget.column(name, width=max(width, int(available * width / total)))
    def resize(event):
        if event.width > 1 and event.width != state["width"]:
            state["width"] = event.width
            if state["job"] is not None:
                widget.after_cancel(state["job"])
            state["job"] = widget.after(80, fit)
    def cleanup(event):
        if event.widget == widget and state["job"] is not None:
            widget.after_cancel(state["job"])
            state["job"] = None
    widget.bind("<Configure>", resize, add="+")
    widget.bind("<Destroy>", cleanup, add="+")
    return widget


def empty_message(parent, text=""):
    widget = ctk.CTkLabel(parent, text=text, font=TYPOGRAPHY["body"], text_color=COLORS["muted"])
    widget.pack(anchor="w", padx=SPACING["page"], pady=SPACING["sm"])
    return widget
