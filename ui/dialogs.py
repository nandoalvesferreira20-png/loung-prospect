import customtkinter as ctk

from core.exporter import open_excel, open_folder


def show_finish_dialog(parent, summary):
    """
    Exibe o popup de conclusão da busca.
    """

    dialog = ctk.CTkToplevel(parent)
    dialog.title("Busca finalizada")
    dialog.geometry("430x320")
    dialog.resizable(False, False)

    dialog.grab_set()

    arquivo = summary.get("arquivo")

    ctk.CTkLabel(
        dialog,
        text="✅ Busca finalizada",
        font=("Arial", 24, "bold")
    ).pack(pady=(20, 10))

    info = (
        f"Leads encontrados: {summary['leads']}\n"
        f"Falhas: {summary['falhas']}\n"
        f"Tempo: {summary['tempo_segundos']:.1f}s"
    )

    ctk.CTkLabel(
        dialog,
        text=info,
        justify="left",
        font=("Arial", 15)
    ).pack(pady=10)

    if arquivo:

        ctk.CTkButton(
            dialog,
            text="📄 Abrir Excel",
            command=lambda: open_excel(arquivo)
        ).pack(fill="x", padx=35, pady=(15, 8))

        ctk.CTkButton(
            dialog,
            text="📂 Abrir Pasta",
            command=lambda: open_folder(arquivo)
        ).pack(fill="x", padx=35)

    ctk.CTkButton(
        dialog,
        text="Fechar",
        fg_color="#374151",
        hover_color="#4B5563",
        command=dialog.destroy
    ).pack(fill="x", padx=35, pady=(20, 0))