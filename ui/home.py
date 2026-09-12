# ui/home.py

import threading
import time
from tkinter import messagebox

import customtkinter as ctk

from core.scraper import run_scraper
from ui.dialogs import show_finish_dialog
from ui.theme import COLORS, TYPOGRAPHY, SIZES
from ui.components import heading, field, button


class HomePage(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color=COLORS["bg"])

        self.running = False
        self.stop_requested = False
        self.start_time = None
        self.timer_job = None

        self.build_ui()

    def build_ui(self):
        heading(self, "Busca legada", "Prospecção pelo navegador, com exportação para Excel.")
        form = ctk.CTkFrame(self, fg_color="transparent")
        form.pack(fill="x", padx=28, pady=(0, 12))
        for col in range(2):
            form.grid_columnconfigure(col, weight=1, uniform="fields")
        for index, (name, label, value) in enumerate((("cidades", "Cidades · separadas por vírgula", "Praia Grande"),
                ("segmentos", "Segmentos · separados por vírgula", "clínica odontológica"),
                ("quantidade", "Máximo por busca", "5"), ("output", "Arquivo de saída", "exports/leads_loungtech.xlsx"))):
            cell = ctk.CTkFrame(form, fg_color="transparent")
            cell.grid(row=index // 2, column=index % 2, sticky="ew", padx=(0, 12), pady=(0, 12))
            setattr(self, name, field(cell, label, value=value))
        self.qualification_switch = ctk.CTkSwitch(form, text="Qualificar leads automaticamente")
        self.qualification_switch.deselect()
        self.qualification_switch.grid(row=2, column=0, columnspan=2, sticky="w", pady=(0, 12))
        actions = ctk.CTkFrame(self, fg_color="transparent")
        actions.pack(fill="x", padx=28, pady=(0, 16))
        self.start_btn = button(actions, "Iniciar busca", self.start_search, kind="primary")
        self.start_btn.pack(side="left", padx=(0, 8))
        self.stop_btn = button(actions, "Parar", self.stop_search, kind="danger", state="disabled", width=100)
        self.stop_btn.pack(side="left")
        progress_row = ctk.CTkFrame(self, fg_color="transparent")
        progress_row.pack(fill="x", padx=28)
        self.progress_label = ctk.CTkLabel(progress_row, text="0 / 0 empresas", text_color=COLORS["muted"])
        self.progress_label.pack(side="left")
        self.timer_label = ctk.CTkLabel(progress_row, text="Tempo: 00:00", text_color=COLORS["muted"])
        self.timer_label.pack(side="right")
        self.progress = ctk.CTkProgressBar(self, height=SIZES["progress"])
        self.progress.pack(fill="x", padx=28, pady=(8, 20))
        self.progress.set(0)
        self.logs = ctk.CTkTextbox(self, fg_color=COLORS["sidebar"], font=TYPOGRAPHY["console"], height=140)
        self.logs.pack(fill="both", expand=True, padx=28, pady=(0, 24))
        self.log("Pronto para iniciar.")

    def log(self, text):
        """
        Pode ser chamado pela thread do scraper.
        A atualização visual é enviada para a thread principal.
        """

        self.after(
            0,
            self._append_log,
            str(text)
        )

    def _append_log(self, text):
        self.logs.insert(
            "end",
            text + "\n"
        )
        self.logs.see("end")

    # ==================================================
    # Busca
    # ==================================================

    def start_search(self):
        if self.running:
            return

        cidades = [
            cidade.strip()
            for cidade in self.cidades.get().split(",")
            if cidade.strip()
        ]

        segmentos = [
            segmento.strip()
            for segmento in self.segmentos.get().split(",")
            if segmento.strip()
        ]

        output = self.output.get().strip()

        try:
            quantidade = int(
                self.quantidade.get().strip()
            )

        except ValueError:
            messagebox.showerror(
                "Valor inválido",
                "A quantidade precisa ser um número inteiro."
            )
            return

        if not cidades:
            messagebox.showwarning(
                "Cidades",
                "Informe pelo menos uma cidade."
            )
            return

        if not segmentos:
            messagebox.showwarning(
                "Segmentos",
                "Informe pelo menos um segmento."
            )
            return

        if quantidade < 1:
            messagebox.showwarning(
                "Quantidade",
                "A quantidade precisa ser maior que zero."
            )
            return

        if not output:
            messagebox.showwarning(
                "Arquivo de saída",
                "Informe onde o arquivo será salvo."
            )
            return

        if not output.lower().endswith(".xlsx"):
            messagebox.showwarning(
                "Arquivo de saída",
                "O arquivo de saída precisa terminar com .xlsx."
            )
            return

        self.running = True
        self.stop_requested = False
        self.start_time = time.monotonic()

        self.progress.set(0)

        self.progress_label.configure(
            text="0 / 0 empresas"
        )

        self.timer_label.configure(
            text="Tempo: 00:00"
        )

        self.start_btn.configure(
            state="disabled",
            text="Buscando..."
        )

        self.stop_btn.configure(
            state="normal"
        )

        self.set_form_state("disabled")

        self.log("")
        self.log("========================================")
        self.log("🚀 Nova busca iniciada")
        self.log("========================================")

        self.update_timer()

        thread = threading.Thread(
            target=self.worker,
            args=(
                cidades,
                segmentos,
                quantidade,
                output,
                bool(self.qualification_switch.get()),
            ),
            daemon=True
        )

        thread.start()

    def stop_search(self):
        if not self.running:
            return

        self.stop_requested = True

        self.stop_btn.configure(
            state="disabled",
            text="Parando..."
        )

        self.log(
            "⛔ Cancelamento solicitado. "
            "Aguarde o encerramento da empresa atual."
        )

    # ==================================================
    # Worker
    # ==================================================

    def worker(
        self,
        cidades,
        segmentos,
        quantidade,
        output,
        qualification_enabled=False,
    ):
        try:
            summary = run_scraper(
                cidades=cidades,
                segmentos=segmentos,
                max_results=quantidade,
                output=output,
                log=self.log,
                on_progress=self.update_progress,
                should_stop=lambda: self.stop_requested,
                qualification_enabled=qualification_enabled,
            )

            self.after(
                0,
                self.finish_search,
                summary
            )

        except Exception as error:
            self.log(
                f"❌ Erro inesperado: {error}"
            )

            self.after(
                0,
                self.handle_error,
                str(error)
            )

    # ==================================================
    # Progresso
    # ==================================================

    def update_progress(
        self,
        processed,
        total,
        message
    ):
        """
        Callback chamado pelo scraper.
        """

        self.after(
            0,
            self._apply_progress,
            processed,
            total,
            message
        )

    def _apply_progress(
        self,
        processed,
        total,
        message
    ):
        if total > 0:
            progress_value = processed / total
        else:
            progress_value = 0

        progress_value = max(
            0,
            min(progress_value, 1)
        )

        self.progress.set(
            progress_value
        )

        self.progress_label.configure(
            text=f"{processed} / {total} empresas"
        )

    # ==================================================
    # Cronômetro
    # ==================================================

    def update_timer(self):
        if not self.running or self.start_time is None:
            return

        elapsed = int(
            time.monotonic() - self.start_time
        )

        minutes, seconds = divmod(
            elapsed,
            60
        )

        self.timer_label.configure(
            text=f"Tempo: {minutes:02d}:{seconds:02d}"
        )

        self.timer_job = self.after(
            1000,
            self.update_timer
        )

    def stop_timer(self):
        if self.timer_job is not None:
            self.after_cancel(
                self.timer_job
            )
            self.timer_job = None

    # ==================================================
    # Finalização
    # ==================================================

    def finish_search(self, summary):
        self.running = False
        self.stop_timer()
        self.restore_interface()

        status = summary.get(
            "status",
            "concluído"
        )

        leads = summary.get(
            "leads",
            0
        )

        processados = summary.get(
            "processados",
            0
        )

        total = summary.get(
            "total",
            0
        )

        falhas = summary.get(
            "falhas",
            0
        )

        elapsed = summary.get(
            "tempo_segundos",
            0
        )

        arquivo = summary.get(
            "arquivo"
        )

        minutes, seconds = divmod(
            int(elapsed),
            60
        )

        if total > 0:
            self.progress.set(
                processados / total
            )

        self.progress_label.configure(
            text=f"{processados} / {total} empresas"
        )

        self.timer_label.configure(
            text=f"Tempo: {minutes:02d}:{seconds:02d}"
        )

        if status == "cancelado":
            title = "Busca interrompida"

            message = (
                "A busca foi interrompida.\n\n"
                f"Leads salvos: {leads}\n"
                f"Empresas processadas: {processados}/{total}\n"
                f"Falhas: {falhas}\n"
                f"Tempo: {minutes:02d}:{seconds:02d}"
            )

            self.log(
                "⏹ Busca interrompida pelo usuário."
            )

        else:
            title = "Busca finalizada"

            message = (
                "A busca foi concluída.\n\n"
                f"Leads salvos: {leads}\n"
                f"Empresas processadas: {processados}/{total}\n"
                f"Falhas: {falhas}\n"
                f"Tempo: {minutes:02d}:{seconds:02d}"
            )

            self.log(
                "✅ Busca concluída com sucesso."
            )

        if arquivo:
            message += (
                f"\n\nArquivo salvo em:\n{arquivo}"
            )

        show_finish_dialog(
            self,
            summary
        )
    def handle_error(self, error):
        self.running = False
        self.stop_timer()
        self.restore_interface()

        messagebox.showerror(
            "Erro durante a busca",
            (
                "A busca foi interrompida por um erro.\n\n"
                f"{error}"
            )
        )

    # ==================================================
    # Estado da interface
    # ==================================================

    def restore_interface(self):
        self.start_btn.configure(
            state="normal",
            text="Iniciar busca"
        )

        self.stop_btn.configure(
            state="disabled",
            text="Parar"
        )

        self.set_form_state("normal")

    def set_form_state(self, state):
        self.qualification_switch.configure(state=state)
        self.cidades.configure(
            state=state
        )

        self.segmentos.configure(
            state=state
        )

        self.quantidade.configure(
            state=state
        )

        self.output.configure(
            state=state
        )

