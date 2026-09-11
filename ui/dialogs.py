import customtkinter as ctk

from core.exporter import open_excel, open_folder


def format_finish_summary(summary):
    """Present scalar summary values without interpreting qualification objects."""
    info = (
        f"Leads exportados: {summary['leads']}\n"
        f"Falhas na coleta: {summary['falhas']}\n"
        f"Tempo: {summary['tempo_segundos']:.1f}s"
    )
    qualification = summary.get("qualification_summary")
    if qualification is not None:
        info += (
            f"\n\nQualificados: {qualification['qualified']}"
            f"\nOportunidades de website: {qualification['website_opportunities']}"
            f"\nDados insuficientes: {qualification['insufficient_data']}"
            f"\nErros de qualificação: {qualification['error']}"
        )
    return info


def show_finish_dialog(parent, summary):
    """
    Exibe o popup de conclusão da busca.
    """

    dialog = ctk.CTkToplevel(parent)
    dialog.title("Busca finalizada")
    dialog.geometry("480x440" if "qualification_summary" in summary else "430x320")
    dialog.resizable(False, False)

    dialog.grab_set()

    arquivo = summary.get("arquivo")

    ctk.CTkLabel(
        dialog,
        text="✅ Busca finalizada",
        font=("Arial", 24, "bold")
    ).pack(pady=(20, 10))

    info = format_finish_summary(summary)

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
