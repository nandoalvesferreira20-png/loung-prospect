# ui/home.py

import threading
import time
from tkinter import messagebox

import customtkinter as ctk

from core.scraper import run_scraper
from ui.dialogs import show_finish_dialog


class HomePage(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color="#020617")

        self.running = False
        self.stop_requested = False
        self.start_time = None
        self.timer_job = None

        self.build_ui()

    def build_ui(self):
        # =========================
        # Título
        # =========================

        title = ctk.CTkLabel(
            self,
            text="Buscar novos leads",
            font=("Arial", 30, "bold"),
            text_color="#f8fafc"
        )
        title.pack(
            anchor="w",
            padx=40,
            pady=(35, 5)
        )

        desc = ctk.CTkLabel(
            self,
            text=(
                "Encontre clínicas e consultórios automaticamente "
                "e exporte para Excel."
            ),
            font=("Arial", 15),
            text_color="#94a3b8"
        )
        desc.pack(
            anchor="w",
            padx=40,
            pady=(0, 25)
        )

        # =========================
        # Formulário
        # =========================

        card = ctk.CTkFrame(
            self,
            fg_color="#0f172a",
            corner_radius=18
        )
        card.pack(
            fill="x",
            padx=40,
            pady=10
        )

        self.cidades = ctk.CTkEntry(
            card,
            placeholder_text=(
                "Cidades: Praia Grande, Santos, São Vicente"
            ),
            height=44
        )
        self.cidades.pack(
            fill="x",
            padx=25,
            pady=(25, 12)
        )
        self.cidades.insert(
            0,
            "Praia Grande"
        )

        self.segmentos = ctk.CTkEntry(
            card,
            placeholder_text=(
                "Segmentos: clínica odontológica, clínica médica"
            ),
            height=44
        )
        self.segmentos.pack(
            fill="x",
            padx=25,
            pady=12
        )
        self.segmentos.insert(
            0,
            "clínica odontológica"
        )

        self.quantidade = ctk.CTkEntry(
            card,
            placeholder_text="Máximo por busca",
            height=44
        )
        self.quantidade.pack(
            fill="x",
            padx=25,
            pady=12
        )
        self.quantidade.insert(
            0,
            "5"
        )

        self.output = ctk.CTkEntry(
            card,
            placeholder_text="Arquivo de saída",
            height=44
        )
        self.output.pack(
            fill="x",
            padx=25,
            pady=12
        )
        self.output.insert(
            0,
            "exports/leads_loungtech.xlsx"
        )

        # =========================
        # Botões
        # =========================

        self.qualification_switch = ctk.CTkSwitch(
            card,
            text="Qualificar leads automaticamente",
        )
        self.qualification_switch.deselect()
        self.qualification_switch.pack(anchor="w", padx=25, pady=(12, 0))

        buttons = ctk.CTkFrame(
            card,
            fg_color="transparent"
        )
        buttons.pack(
            fill="x",
            padx=25,
            pady=(18, 25)
        )

        self.start_btn = ctk.CTkButton(
            buttons,
            text="🚀 Iniciar busca",
            height=48,
            font=("Arial", 16, "bold"),
            fg_color="#2563eb",
            hover_color="#1d4ed8",
            command=self.start_search
        )
        self.start_btn.pack(
            side="left",
            fill="x",
            expand=True
        )

        self.stop_btn = ctk.CTkButton(
            buttons,
            text="⛔ Parar",
            width=130,
            height=48,
            font=("Arial", 14, "bold"),
            fg_color="#dc2626",
            hover_color="#b91c1c",
            state="disabled",
            command=self.stop_search
        )
        self.stop_btn.pack(
            side="left",
            padx=(10, 0)
        )

        # =========================
        # Progresso
        # =========================

        progress_container = ctk.CTkFrame(
            self,
            fg_color="transparent"
        )
        progress_container.pack(
            fill="x",
            padx=40,
            pady=(12, 0)
        )

        self.progress_label = ctk.CTkLabel(
            progress_container,
            text="0 / 0 empresas",
            font=("Arial", 13),
            text_color="#94a3b8"
        )
        self.progress_label.pack(
            side="left"
        )

        self.timer_label = ctk.CTkLabel(
            progress_container,
            text="Tempo: 00:00",
            font=("Arial", 13),
            text_color="#94a3b8"
        )
        self.timer_label.pack(
            side="right"
        )

        self.progress = ctk.CTkProgressBar(
            self,
            height=12,
            progress_color="#2563eb",
            fg_color="#1e293b"
        )
        self.progress.pack(
            fill="x",
            padx=40,
            pady=(6, 15)
        )
        self.progress.set(0)

        # =========================
        # Logs
        # =========================

        self.logs = ctk.CTkTextbox(
            self,
            fg_color="#020617",
            border_color="#1e293b",
            border_width=1,
            text_color="#e5e7eb",
            font=("Consolas", 12)
        )
        self.logs.pack(
            fill="both",
            expand=True,
            padx=40,
            pady=(5, 35)
        )

        self.log("Pronto para iniciar.")
        self.log(
            "Dica: comece com quantidade 5 para testar."
        )

    # ==================================================
    # Logs
    # ==================================================

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
            text="🚀 Iniciar busca"
        )

        self.stop_btn.configure(
            state="disabled",
            text="⛔ Parar"
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

