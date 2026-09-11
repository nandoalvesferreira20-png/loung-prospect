import customtkinter as ctk
from ui.theme import COLORS, FONT


class Sidebar(ctk.CTkFrame):
    def __init__(self, master, on_dashboard, on_search, on_prototype=None):
        super().__init__(master, width=250, fg_color=COLORS["sidebar"], corner_radius=0)

        self.on_dashboard = on_dashboard
        self.on_search = on_search
        self.on_prototype = on_prototype

        self.build_ui()

    def build_ui(self):
        ctk.CTkLabel(
            self,
            text="Loung Leads",
            font=(FONT, 25, "bold"),
            text_color=COLORS["accent"]
        ).pack(anchor="w", padx=24, pady=(32, 4))

        ctk.CTkLabel(
            self,
            text="Prospecção inteligente",
            font=(FONT, 13),
            text_color=COLORS["muted"]
        ).pack(anchor="w", padx=24, pady=(0, 35))

        self.dashboard_btn = ctk.CTkButton(
            self,
            text="🏠  Dashboard",
            height=42,
            anchor="w",
            fg_color="transparent",
            hover_color=COLORS["card_light"],
            text_color=COLORS["text"],
            command=self.on_dashboard
        )
        self.dashboard_btn.pack(fill="x", padx=18, pady=6)

        self.search_btn = ctk.CTkButton(
            self,
            text="🔍  Buscar Leads",
            height=42,
            anchor="w",
            fg_color=COLORS["primary"],
            hover_color=COLORS["primary_hover"],
            text_color=COLORS["text"],
            command=self.on_search
        )
        self.search_btn.pack(fill="x", padx=18, pady=6)
        self.prototype_btn = ctk.CTkButton(
            self, text="🎨 Prototype Studio", height=42, anchor="w",
            fg_color="transparent", hover_color=COLORS["card_light"],
            text_color=COLORS["text"], command=self.on_prototype,
        )
        self.prototype_btn.pack(fill="x", padx=18, pady=6)

        ctk.CTkButton(
            self,
            text="🤖  Qualificador IA",
            height=42,
            anchor="w",
            fg_color="transparent",
            hover_color=COLORS["card_light"],
            text_color=COLORS["muted"],
            state="disabled"
        ).pack(fill="x", padx=18, pady=6)

        ctk.CTkButton(
            self,
            text="📊  CRM",
            height=42,
            anchor="w",
            fg_color="transparent",
            hover_color=COLORS["card_light"],
            text_color=COLORS["muted"],
            state="disabled"
        ).pack(fill="x", padx=18, pady=6)

        ctk.CTkButton(
            self,
            text="⚙️  Configurações",
            height=42,
            anchor="w",
            fg_color="transparent",
            hover_color=COLORS["card_light"],
            text_color=COLORS["muted"],
            state="disabled"
        ).pack(fill="x", padx=18, pady=6)

        bottom = ctk.CTkFrame(self, fg_color="transparent")
        bottom.pack(side="bottom", fill="x", padx=22, pady=25)

        ctk.CTkLabel(
            bottom,
            text="v1.0.0",
            font=(FONT, 12),
            text_color=COLORS["muted"]
        ).pack(anchor="w")

        ctk.CTkLabel(
            bottom,
            text="● Playwright ativo",
            font=(FONT, 12),
            text_color=COLORS["success"]
        ).pack(anchor="w", pady=(6, 0))

    def set_active(self, page):
        self.prototype_btn.configure(fg_color=COLORS["primary"] if page == "prototype" else "transparent")
        if page == "prototype":
            self.dashboard_btn.configure(fg_color="transparent")
            self.search_btn.configure(fg_color="transparent")
        if page == "dashboard":
            self.dashboard_btn.configure(fg_color=COLORS["primary"], text_color=COLORS["text"])
            self.search_btn.configure(fg_color="transparent", text_color=COLORS["text"])

        if page == "search":
            self.search_btn.configure(fg_color=COLORS["primary"], text_color=COLORS["text"])
            self.dashboard_btn.configure(fg_color="transparent", text_color=COLORS["text"])
