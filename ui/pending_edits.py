"""One explicit save/discard/continue decision for pending desktop edits."""
import customtkinter as ctk
from ui.components import button
from ui.theme import COLORS, TYPOGRAPHY


def ask_pending_action(parent, section):
    owner = parent.winfo_toplevel()
    previous_grab = owner.grab_current()
    dialog = ctk.CTkToplevel(owner)
    dialog.title("Alterações não salvas")
    dialog.geometry("580x210")
    dialog.resizable(False, False)
    dialog.transient(owner)
    result = {"action": "continue"}

    def choose(action):
        result["action"] = action
        dialog.destroy()

    ctk.CTkLabel(dialog, text=f"Há alterações não salvas em {section}.",
                 font=TYPOGRAPHY["section"], wraplength=530, justify="left").pack(padx=24, pady=(24, 8), anchor="w")
    ctk.CTkLabel(dialog, text="Salve antes de continuar ou descarte somente as alterações pendentes.",
                 text_color=COLORS["muted"], wraplength=530, justify="left").pack(padx=24, anchor="w")
    actions = ctk.CTkFrame(dialog, fg_color="transparent")
    actions.pack(fill="x", padx=24, pady=24)
    for label, action, kind in (("Salvar", "save", "primary"),
                                 ("Descartar alterações", "discard", "secondary"),
                                 ("Continuar editando", "continue", "ghost")):
        button(actions, label, lambda value=action: choose(value), kind=kind, width=150).pack(side="left", padx=(0, 8))
    dialog.protocol("WM_DELETE_WINDOW", lambda: choose("continue"))
    dialog.grab_set()
    dialog.wait_window()
    if previous_grab is not None and previous_grab.winfo_exists():
        previous_grab.grab_set()
    return result["action"]


def resolve_pending(parent, section, save):
    action = ask_pending_action(parent, section)
    return action == "discard" or (action == "save" and save() is True)
