"""Loung Prospect desktop design tokens. No external assets or fonts."""
COLORS = {
    "background": "#090E18", "surface": "#151F30", "surface_secondary": "#19263A",
    "surface_hover": "#1C2839", "sidebar": "#0B1220", "border": "#263246",
    "primary": "#2563EB", "primary_hover": "#1D4ED8", "accent": "#85B5FF",
    "text_primary": "#F8FAFC", "text_secondary": "#94A3B8", "text_muted": "#94A3B8",
    "success": "#7CCDA6", "warning": "#E6BD73", "danger": "#F0969D",
    "danger_surface": "#362028", "danger_hover": "#4C2932", "selected": "#1D3558",
    "disabled": "#8C99AC", "success_surface": "#183029", "warning_surface": "#30291E",
    "info": "#85B5FF", "draft": "#C4B5FD", "draft_surface": "#302640",
}
COLORS.update(bg_base=COLORS["background"], bg_surface=COLORS["surface"], bg_elevated=COLORS["surface_secondary"])
COLORS.update(bg=COLORS["background"], card=COLORS["surface"], card_light=COLORS["surface_secondary"],
              text=COLORS["text_primary"], muted=COLORS["text_muted"])
SPACING = dict(xs=4, sm=8, md=12, lg=16, xl=24, xxl=32, page=28, section=20)
RADIUS = dict(control=8, surface=12, badge=6)
FONT = "Segoe UI"
TYPOGRAPHY = {"title": (FONT, 28, "bold"), "section": (FONT, 17, "bold"),
              "value": (FONT, 28, "bold"), "body": (FONT, 14), "secondary": (FONT, 13),
              "caption": (FONT, 12), "button": (FONT, 13, "bold"), "console": ("Consolas", 12), "kpi": (FONT, 24, "bold"),
              "lead_title": (FONT, 22, "bold"), "list_title": (FONT, 14, "bold"), "message": (FONT, 15)}
SIZES = dict(sidebar=216, control=40, row=44, progress=5, page_min=1100)


def install_theme():
    """Apply supported CTk theme defaults before constructing widgets."""
    import customtkinter as ctk
    ctk.set_appearance_mode("dark")
    theme = ctk.ThemeManager.theme
    for name in ("CTk", "CTkToplevel"):
        theme[name]["fg_color"] = COLORS["bg"]
    theme["CTkFrame"].update(fg_color=COLORS["surface"], top_fg_color=COLORS["surface_secondary"],
        border_color=COLORS["border"], corner_radius=RADIUS["surface"], border_width=0)
    for name in ("CTkLabel", "CTkButton", "CTkEntry", "CTkComboBox", "CTkTextbox", "CTkCheckBox", "CTkSwitch", "CTkSegmentedButton", "DropdownMenu"):
        theme[name]["text_color"] = COLORS["text"]
        if "text_color_disabled" in theme[name]:
            theme[name]["text_color_disabled"] = COLORS["disabled"]
    theme["CTkButton"].update(fg_color=COLORS["surface_secondary"], hover_color=COLORS["surface_hover"],
        border_color=COLORS["border"], corner_radius=RADIUS["control"])
    for name in ("CTkEntry", "CTkComboBox"):
        theme[name].update(fg_color=COLORS["bg"], border_color=COLORS["border"], border_width=1, corner_radius=RADIUS["control"])
    theme["CTkEntry"]["placeholder_text_color"] = COLORS["muted"]
    theme["CTkComboBox"].update(button_color=COLORS["border"], button_hover_color=COLORS["surface_hover"])
    theme["CTkTextbox"].update(fg_color=COLORS["bg"], border_color=COLORS["border"], corner_radius=RADIUS["control"],
        scrollbar_button_color=COLORS["border"], scrollbar_button_hover_color=COLORS["muted"])
    theme["CTkProgressBar"].update(fg_color=COLORS["border"], progress_color=COLORS["primary"])
    theme["CTkCheckBox"].update(fg_color=COLORS["primary"], hover_color=COLORS["primary_hover"], border_color=COLORS["muted"], border_width=2)
    theme["CTkSwitch"].update(progress_color=COLORS["primary"], fg_color=COLORS["border"])
    theme["CTkSegmentedButton"].update(fg_color=COLORS["surface"], selected_color=COLORS["selected"],
        selected_hover_color=COLORS["surface_hover"], unselected_color=COLORS["surface"], unselected_hover_color=COLORS["surface_hover"])
    theme["DropdownMenu"].update(fg_color=COLORS["surface_secondary"], hover_color=COLORS["selected"])
    theme["CTkScrollbar"].update(button_color=COLORS["border"], button_hover_color=COLORS["muted"])
    theme["CTkFont"].update(family=FONT, size=13)
