import customtkinter as ctk
from ui.theme import COLORS, FONT
from ui.components import StatCard


class DashboardPage(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color=COLORS["bg"])
        self.build_ui()

    def build_ui(self):
        ctk.CTkLabel(
            self,
            text="Dashboard",
            font=(FONT, 30, "bold"),
            text_color=COLORS["text"]
        ).pack(anchor="w", padx=40, pady=(35, 5))

        ctk.CTkLabel(
            self,
            text="Visão geral da prospecção da Loung Tech.",
            font=(FONT, 15),
            text_color=COLORS["muted"]
        ).pack(anchor="w", padx=40, pady=(0, 25))

        grid = ctk.CTkFrame(self, fg_color="transparent")
        grid.pack(fill="x", padx=40, pady=10)

        cards = [
            ("Leads coletados", "0", "Aguardando busca"),
            ("Qualificados", "0", "Em breve"),
            ("Com site", "0", "Em breve"),
            ("Sem site", "0", "Em breve"),
        ]

        for i, card in enumerate(cards):
            StatCard(grid, *card).grid(row=0, column=i, padx=8, sticky="ew")

        for i in range(4):
            grid.columnconfigure(i, weight=1)