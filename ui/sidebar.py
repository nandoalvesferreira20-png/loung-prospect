"""Grouped navigation with one explicit active item."""
import customtkinter as ctk
from ui.theme import COLORS, TYPOGRAPHY, SIZES, FONT
from ui.components import button
from ui.sdr_components import LineIcon


class Sidebar(ctk.CTkFrame):
    def __init__(self, master, on_dashboard, on_search, on_prototype=None, on_workspace=None, on_places=None, on_day=None, on_sales=None):
        super().__init__(master, width=SIZES["sidebar"], fg_color=COLORS["sidebar"], corner_radius=0)
        self.pack_propagate(False)
        brand = ctk.CTkFrame(self, fg_color="transparent")
        brand.pack(fill="x", padx=24, pady=(20, 16))
        ctk.CTkLabel(brand, text="LOUNG", font=(FONT, 25, "bold"), text_color=COLORS["text"]).pack(anchor="w")
        ctk.CTkLabel(brand, text="PROSPECT", font=(FONT, 12, "bold"), text_color=COLORS["accent"]).pack(anchor="w")
        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.pack(side="bottom", fill="x", padx=24, pady=12)
        ctk.CTkLabel(footer, text="Loung Tech  /  v1.0.0", font=TYPOGRAPHY["caption"], text_color=COLORS["muted"]).pack(anchor="w")
        nav = ctk.CTkScrollableFrame(self, fg_color="transparent", corner_radius=0)
        nav.pack(fill="both", expand=True, padx=10)
        self.buttons = {}
        self.rows, self.icons, self.markers = {}, {}, {}
        groups = ((None, (("dashboard", "Visão Geral", on_dashboard),)),
            ("PROSPECÇÃO", (("places", "Buscar leads", on_places), ("workspace", "Carteira", on_workspace),
                            ("search", "Busca legada", on_search))),
            ("COMERCIAL", (("day", "Meu Dia", on_day), ("sales", "SDR Inteligente", on_sales))),
            ("FERRAMENTAS", (("prototype", "Prototype Studio", on_prototype),)))
        for title, items in groups:
            if title:
                ctk.CTkLabel(nav, text=title, font=TYPOGRAPHY["caption"], text_color=COLORS["muted"]).pack(anchor="w", padx=12, pady=(12, 4))
            for key, label, command in items:
                row = ctk.CTkFrame(nav, fg_color="transparent", corner_radius=8)
                row.pack(fill="x", pady=2)
                marker = ctk.CTkFrame(row, width=3, corner_radius=0, fg_color=COLORS["sidebar"])
                marker.pack(side="left", fill="y", pady=8)
                icon = LineIcon(row, key)
                icon.pack(side="left", padx=(8, 4))
                icon.bind("<Button-1>", lambda event, callback=command: callback() if callback else None)
                widget = button(row, label, command, kind="ghost", anchor="w", height=38, width=130)
                widget.pack(side="left", fill="x", expand=True)
                self.buttons[key], self.rows[key], self.icons[key], self.markers[key] = widget, row, icon, marker
        self.set_active("dashboard")

    def set_active(self, page):
        for key, widget in self.buttons.items():
            active = key == page
            background = COLORS["bg_elevated"] if active else COLORS["sidebar"]
            widget.configure(fg_color=background, text_color=COLORS["text"] if active else COLORS["text_secondary"])
            self.rows[key].configure(fg_color=background)
            self.markers[key].configure(fg_color=COLORS["accent"] if active else background)
            self.icons[key].configure(bg=background)
            self.icons[key].color = COLORS["accent"] if active else COLORS["text_secondary"]
            self.icons[key].paint()
