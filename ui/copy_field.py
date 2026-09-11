"""Selectable read-only lead details and a shared Tk clipboard action."""
from tkinter import TclError

import customtkinter as ctk

from ui.theme import COLORS


def available_text(value):
    if value is None or not str(value).strip():
        return None
    return str(value)


def copy_to_clipboard(widget, value):
    """Return inline feedback; absent values leave the clipboard untouched."""
    text = available_text(value)
    if text is None:
        return "Não disponível"
    try:
        widget.clipboard_clear()
        widget.clipboard_append(text)
    except TclError:
        return "Não foi possível copiar"
    return "Copiado!"


def copy_selection(entry):
    if entry.select_present():
        text = entry.get()[entry.index("sel.first"):entry.index("sel.last")]
        copy_to_clipboard(entry, text)
    return "break"


def add_copy_field(parent, label, value):
    text = available_text(value)
    row = ctk.CTkFrame(parent, fg_color="transparent")
    row.pack(fill="x", pady=4)
    row.grid_columnconfigure(0, weight=1)
    ctk.CTkLabel(row, text=label).grid(row=0, column=0, sticky="w")
    entry = ctk.CTkEntry(row, fg_color=COLORS["card"], text_color=COLORS["text"],
                         border_color=COLORS["border"])
    entry.insert(0, text if text is not None else "Não disponível")
    # CTkEntry forwards this native Tk Entry state: selection remains enabled,
    # while typing, paste, cut and programmatic insertion/deletion cannot edit it.
    entry.configure(state="readonly")
    entry.grid(row=1, column=0, sticky="ew")
    entry.bind("<Control-c>", lambda event: copy_selection(entry))
    entry.bind("<Control-C>", lambda event: copy_selection(entry))
    button = ctk.CTkButton(row, text="Copiar", width=90,
                           state="normal" if text is not None else "disabled")
    button.configure(command=lambda: button.configure(text=copy_to_clipboard(entry, text)))
    button.grid(row=1, column=1, padx=(8, 0))
    return entry, button
