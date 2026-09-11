"""Explicit Google Places search; all worker events are consumed via after()."""

import queue
import threading
from datetime import datetime
from pathlib import Path
from tkinter import messagebox

import customtkinter as ctk

from core.exporter import open_excel, open_folder
from core.prospecting.service import (
    ProspectingError,
    create_provider,
    prospect,
)
from core.providers.google_places import (
    GooglePlacesConfigurationError,
)
from ui.places_logic import (
    parse_search,
    summary_text,
)
from ui.theme import COLORS


class PlacesSearchPage(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(
            master,
            fg_color=COLORS["bg"],
        )

        self.running = False
        self.pending = queue.Queue()
        self.cancel_event = threading.Event()
        self.poll_job = None

        self.last_exported_file = None

        ctk.CTkLabel(
            self,
            text="Google Places API",
            font=("Arial", 28, "bold"),
        ).pack(
            anchor="w",
            padx=24,
            pady=24,
        )

        ctk.CTkLabel(
            self,
            text=(
                "Buscar, qualificar, salvar na Carteira de Leads "
                "e exportar Excel. A consulta consome quota da API."
            ),
        ).pack(
            anchor="w",
            padx=24,
        )

        form = ctk.CTkFrame(
            self
        )

        form.pack(
            fill="x",
            padx=24,
            pady=16,
        )

        self.entries = {}

        fields = (
            (
                "city",
                "Cidade",
                "",
            ),
            (
                "segment",
                "Segmento",
                "",
            ),
            (
                "quantity",
                "Quantidade (1–100)",
                "5",
            ),
        )

        for column, (
            name,
            label,
            default,
        ) in enumerate(fields):

            form.grid_columnconfigure(
                column,
                weight=1,
            )

            ctk.CTkLabel(
                form,
                text=label,
            ).grid(
                row=0,
                column=column,
                padx=12,
                sticky="w",
            )

            entry = ctk.CTkEntry(
                form
            )

            entry.insert(
                0,
                default,
            )

            entry.grid(
                row=1,
                column=column,
                padx=12,
                pady=12,
                sticky="ew",
            )

            self.entries[name] = entry

        # --------------------------------------------------
        # Export option
        # --------------------------------------------------

        export_frame = ctk.CTkFrame(
            self
        )

        export_frame.pack(
            fill="x",
            padx=24,
            pady=(0, 8),
        )

        self.export_var = ctk.BooleanVar(
            value=True
        )

        self.export_checkbox = ctk.CTkCheckBox(
            export_frame,
            text="Exportar Excel ao finalizar",
            variable=self.export_var,
        )

        self.export_checkbox.pack(
            side="left",
            padx=12,
            pady=12,
        )

        self.open_excel_button = ctk.CTkButton(
            export_frame,
            text="Abrir Excel",
            command=self.open_last_excel,
            state="disabled",
            width=120,
        )

        self.open_excel_button.pack(
            side="right",
            padx=(6, 12),
            pady=12,
        )

        self.open_folder_button = ctk.CTkButton(
            export_frame,
            text="Abrir pasta",
            command=self.open_last_folder,
            state="disabled",
            width=120,
        )

        self.open_folder_button.pack(
            side="right",
            padx=6,
            pady=12,
        )

        # --------------------------------------------------
        # Actions
        # --------------------------------------------------

        self.start_button = ctk.CTkButton(
            self,
            text="Buscar e qualificar",
            command=self.start,
        )

        self.start_button.pack(
            anchor="w",
            padx=24,
            pady=8,
        )

        self.cancel_button = ctk.CTkButton(
            self,
            text="Cancelar",
            command=self.cancel,
            state="disabled",
        )

        self.cancel_button.pack(
            anchor="w",
            padx=24,
        )

        # --------------------------------------------------
        # Progress
        # --------------------------------------------------

        self.progress = ctk.CTkProgressBar(
            self
        )

        self.progress.pack(
            fill="x",
            padx=24,
            pady=12,
        )

        self.progress.set(
            0
        )

        # --------------------------------------------------
        # Output
        # --------------------------------------------------

        self.output = ctk.CTkTextbox(
            self
        )

        self.output.pack(
            fill="both",
            expand=True,
            padx=24,
            pady=(0, 24),
        )

        self.output.configure(
            state="disabled"
        )

    # ------------------------------------------------------
    # Helpers
    # ------------------------------------------------------

    def append(self, text):
        self.output.configure(
            state="normal"
        )

        self.output.insert(
            "end",
            text + "\n",
        )

        self.output.see(
            "end"
        )

        self.output.configure(
            state="disabled"
        )

    def set_running(self, running):
        self.running = running

        self.start_button.configure(
            state=(
                "disabled"
                if running
                else "normal"
            )
        )

        self.cancel_button.configure(
            state=(
                "normal"
                if running
                else "disabled"
            )
        )

        self.export_checkbox.configure(
            state=(
                "disabled"
                if running
                else "normal"
            )
        )

        for entry in self.entries.values():
            entry.configure(
                state=(
                    "disabled"
                    if running
                    else "normal"
                )
            )

    def build_export_path(
        self,
        city,
        segment,
    ):
        """Build a safe timestamped export path."""

        def slug(value):
            cleaned = (
                value.strip()
                .lower()
                .replace(" ", "-")
            )

            allowed = (
                "abcdefghijklmnopqrstuvwxyz"
                "0123456789-_"
            )

            cleaned = "".join(
                char
                if char in allowed
                else "-"
                for char in cleaned
            )

            while "--" in cleaned:
                cleaned = cleaned.replace(
                    "--",
                    "-",
                )

            return (
                cleaned.strip("-")
                or "busca"
            )

        timestamp = datetime.now().strftime(
            "%Y%m%d_%H%M%S"
        )

        filename = (
            f"{slug(city)}_"
            f"{slug(segment)}_"
            f"{timestamp}.xlsx"
        )

        return (
            Path("output")
            / "google_places"
            / filename
        )

    # ------------------------------------------------------
    # Search
    # ------------------------------------------------------

    def start(self):
        if self.running:
            return

        try:
            params = parse_search(
                **{
                    key: widget.get()
                    for key, widget
                    in self.entries.items()
                }
            )

            # Validate key locally before thread.
            # No HTTP request here.
            provider = create_provider()

        except ValueError as error:
            messagebox.showerror(
                "Google Places",
                str(error),
                parent=self,
            )

            return

        except GooglePlacesConfigurationError:
            messagebox.showerror(
                "Google Places",
                (
                    "Configure GOOGLE_PLACES_API_KEY "
                    "no ambiente ou .env."
                ),
                parent=self,
            )

            return

        except Exception:
            messagebox.showerror(
                "Google Places",
                (
                    "Confira o .env e as dependências "
                    "em requirements.txt."
                ),
                parent=self,
            )

            return

        export_path = None

        if self.export_var.get():
            export_path = self.build_export_path(
                params["city"],
                params["segment"],
            )

        self.cancel_event.clear()
        self.set_running(True)

        self.progress.configure(
            mode="indeterminate"
        )

        self.progress.start()

        self.append(
            (
                "Exportação Excel: ativada"
                if export_path is not None
                else "Exportação Excel: desativada"
            )
        )

        def worker():
            try:
                result = prospect(
                    **params,
                    provider=provider,
                    cancel_event=self.cancel_event,
                    export_path=export_path,
                    log=lambda text: (
                        self.pending.put(
                            (
                                "log",
                                text,
                            )
                        )
                    ),
                    progress=lambda done, total: (
                        self.pending.put(
                            (
                                "progress",
                                done / total,
                            )
                        )
                    ),
                )

                self.pending.put(
                    (
                        "done",
                        result,
                    )
                )

            except ProspectingError as error:
                self.pending.put(
                    (
                        "error",
                        (
                            f"{error}\n"
                            f"Requests: "
                            f"{error.summary.requests_made}"
                        ),
                    )
                )

            except Exception:
                self.pending.put(
                    (
                        "error",
                        (
                            "Falha local na prospecção. "
                            "Nenhum detalhe sensível foi exibido."
                        ),
                    )
                )

        threading.Thread(
            target=worker,
            daemon=True,
        ).start()

        self.poll_job = self.after(
            100,
            self.poll,
        )

    # ------------------------------------------------------
    # Worker event consumption
    # ------------------------------------------------------

    def poll(self):
        self.poll_job = None

        while True:
            try:
                kind, value = (
                    self.pending.get_nowait()
                )

            except queue.Empty:
                break

            if kind == "log":
                self.append(
                    value
                )

            elif kind == "progress":
                self.progress.stop()

                self.progress.configure(
                    mode="determinate"
                )

                self.progress.set(
                    value
                )

            else:
                self.progress.stop()

                self.progress.configure(
                    mode="determinate"
                )

                self.progress.set(
                    (
                        1
                        if (
                            kind == "done"
                            and not value.cancelled
                        )
                        else 0
                    )
                )

                self.set_running(
                    False
                )

                self.append(
                    (
                        summary_text(value)
                        if kind == "done"
                        else value
                    )
                )

                if kind == "done":
                    for message in value.errors[:10]:
                        self.append(
                            message
                        )

                    if value.exported_file:
                        self.last_exported_file = Path(
                            value.exported_file
                        )

                        self.open_excel_button.configure(
                            state="normal"
                        )

                        self.open_folder_button.configure(
                            state="normal"
                        )

                        self.append(
                            ""
                        )

                        self.append(
                            "EXPORTAÇÃO"
                        )

                        self.append(
                            (
                                f"Excel: "
                                f"{value.exported_rows} leads"
                            )
                        )

                        self.append(
                            str(
                                self.last_exported_file
                            )
                        )

                    elif value.export_error:
                        self.append(
                            ""
                        )

                        self.append(
                            (
                                "Excel não foi gerado "
                                "devido a um erro de exportação."
                            )
                        )

                    self.append(
                        ""
                    )

                    self.append(
                        (
                            "Abra a Carteira de Leads "
                            "ou clique em Atualizar lista "
                            "para consultar as inserções."
                        )
                    )

        if self.running:
            self.poll_job = self.after(
                100,
                self.poll,
            )

    # ------------------------------------------------------
    # Export actions
    # ------------------------------------------------------

    def open_last_excel(self):
        if not self.last_exported_file:
            return

        try:
            open_excel(
                self.last_exported_file
            )

        except Exception as error:
            messagebox.showerror(
                "Excel",
                str(error),
                parent=self,
            )

    def open_last_folder(self):
        if not self.last_exported_file:
            return

        try:
            open_folder(
                self.last_exported_file
            )

        except Exception as error:
            messagebox.showerror(
                "Pasta",
                str(error),
                parent=self,
            )

    # ------------------------------------------------------
    # Cancellation / destruction
    # ------------------------------------------------------

    def cancel(self):
        self.cancel_event.set()

        self.cancel_button.configure(
            state="disabled"
        )

        self.append(
            (
                "Cancelamento solicitado; "
                "aguardando a consulta/etapa "
                "atual terminar."
            )
        )

    def destroy(self):
        self.cancel_event.set()

        if self.poll_job is not None:
            self.after_cancel(
                self.poll_job
            )

        super().destroy()