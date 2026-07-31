import customtkinter as ctk
from ui.theme import COLORS, FONT


class StatCard(ctk.CTkFrame):
    def __init__(self, master, title, value, subtitle=""):
        super().__init__(master, fg_color=COLORS["card"], corner_radius=18)

        ctk.CTkLabel(
            self,
            text=title,
            font=(FONT, 14),
            text_color=COLORS["muted"]
        ).pack(anchor="w", padx=18, pady=(16, 4))

        ctk.CTkLabel(
            self,
            text=value,
            font=(FONT, 30, "bold"),
            text_color=COLORS["text"]
        ).pack(anchor="w", padx=18)

        ctk.CTkLabel(
            self,
            text=subtitle,
            font=(FONT, 12),
            text_color=COLORS["accent"]
        ).pack(anchor="w", padx=18, pady=(4, 16))