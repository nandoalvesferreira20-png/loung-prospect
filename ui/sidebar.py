"""Grouped navigation with one explicit active item."""
import customtkinter as ctk
from ui.theme import COLORS, TYPOGRAPHY, SIZES, FONT
from ui.components import button


class Sidebar(ctk.CTkFrame):
    def __init__(self, master, on_dashboard, on_search, on_prototype=None, on_workspace=None, on_places=None, on_day=None):
        super().__init__(master, width=SIZES["sidebar"], fg_color=COLORS["sidebar"], corner_radius=0)
        self.pack_propagate(False)
        brand = ctk.CTkFrame(self, fg_color="transparent")
        brand.pack(fill="x", padx=24, pady=(28, 24))
        ctk.CTkLabel(brand, text="LOUNG", font=(FONT, 25, "bold"), text_color=COLORS["text"]).pack(anchor="w")
        ctk.CTkLabel(brand, text="PROSPECT", font=(FONT, 12, "bold"), text_color=COLORS["accent"]).pack(anchor="w")
        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.pack(side="bottom", fill="x", padx=24, pady=18)
        ctk.CTkLabel(footer, text="Loung Tech  /  v1.0.0", font=TYPOGRAPHY["caption"], text_color=COLORS["muted"]).pack(anchor="w")
        nav = ctk.CTkScrollableFrame(self, fg_color="transparent", corner_radius=0)
        nav.pack(fill="both", expand=True, padx=10)
        self.buttons = {}
        groups = ((None, (("dashboard", "Visão Geral", on_dashboard),)),
            ("PROSPECÇÃO", (("places", "Buscar leads", on_places), ("workspace", "Carteira", on_workspace),
                            ("search", "Busca legada", on_search))),
            ("COMERCIAL", (("day", "Meu Dia", on_day),)),
            ("FERRAMENTAS", (("prototype", "Prototype Studio", on_prototype),)))
        for title, items in groups:
            if title:
                ctk.CTkLabel(nav, text=title, font=TYPOGRAPHY["caption"], text_color=COLORS["muted"]).pack(anchor="w", padx=12, pady=(20, 6))
            for key, label, command in items:
                widget = button(nav, label, command, kind="ghost", anchor="w", height=38)
                widget.pack(fill="x", pady=2)
                self.buttons[key] = widget
        self.set_active("dashboard")

    def set_active(self, page):
        for key, widget in self.buttons.items():
            widget.configure(fg_color=COLORS["selected"] if key == page else "transparent",
                             text_color=COLORS["text"] if key == page else COLORS["text_secondary"])
