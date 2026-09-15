"""Explicit Google Places search; all worker events are consumed via after()."""

import queue
import threading
from datetime import datetime
from pathlib import Path
from tkinter import messagebox

import customtkinter as ctk

from core.exporter import open_excel, open_folder
from core.lead_filter import DEFAULT_MIN_SCORE
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
from ui.theme import COLORS, TYPOGRAPHY, SIZES
from ui.components import heading, field, button, MetricStrip


class PlacesSearchPage(ctk.CTkFrame):
    def __init__(self, master, on_workspace=None):
        super().__init__(master, fg_color=COLORS["bg"])
        self.running = False
        self.pending = queue.Queue()
        self.cancel_event = threading.Event()
        self.poll_job = None
        self.last_exported_file = None
        heading(self, "Prospecção", "Encontre e qualifique novos leads para sua carteira.")
        form = ctk.CTkFrame(self, fg_color="transparent")
        form.pack(fill="x", padx=28, pady=(0, 16))
        self.entries = {}
        for column, (name, label, default) in enumerate((("city", "Cidade", ""), ("neighborhood", "Bairro (opcional)", ""), ("segment", "Segmento", ""), ("quantity", "Quantidade · até 100", "5"))):
            form.grid_columnconfigure(column, weight=1, uniform="inputs")
            cell = ctk.CTkFrame(form, fg_color="transparent")
            cell.grid(row=0, column=column, sticky="ew", padx=(0 if column == 0 else 12, 0))
            if name == "quantity":
                self.quantity_label = ctk.CTkLabel(cell, text="Meta de leads sem site próprio · até 100", font=TYPOGRAPHY["secondary"])
                self.quantity_label.pack(anchor="w", pady=(0, 5))
                self.entries[name] = ctk.CTkEntry(cell, height=SIZES["control"])
                self.entries[name].insert(0, default)
                self.entries[name].pack(fill="x")
            else:
                self.entries[name] = field(cell, label, value=default)
        actions = ctk.CTkFrame(self, fg_color="transparent")
        self.no_website_switch = ctk.CTkSwitch(form, text="Sem site próprio", command=self.update_target_label)
        self.no_website_switch.select()
        self.no_website_switch.grid(row=1, column=0, columnspan=3, sticky="w", pady=12)
        score_cell = ctk.CTkFrame(form, fg_color="transparent")
        score_cell.grid(row=1, column=3, sticky="ew", padx=(12, 0), pady=12)
        self.min_score = field(score_cell, "Score mínimo · modo sem site", value=str(DEFAULT_MIN_SCORE))
        self.target_hint = ctk.CTkLabel(form, text="Inclui redes sociais e plataformas externas. Busca até a meta, fim dos resultados ou limite de segurança.", text_color=COLORS["muted"], wraplength=850)
        self.target_hint.grid(row=2, column=0, columnspan=4, sticky="w")
        actions.pack(fill="x", padx=28, pady=(0, 16))
        self.start_button = button(actions, "Buscar leads", self.start, kind="primary")
        self.start_button.pack(side="left", padx=(0, 8))
        self.cancel_button = button(actions, "Cancelar", self.cancel, kind="danger", state="disabled", width=100)
        self.cancel_button.pack(side="left", padx=(0, 16))
        self.export_var = ctk.BooleanVar(value=True)
        self.export_checkbox = ctk.CTkCheckBox(actions, text="Exportar Excel ao finalizar", variable=self.export_var)
        self.export_checkbox.pack(side="left")
        self.run_status = ctk.CTkLabel(self, text="Pronto para buscar · Google Places utiliza a quota da sua API.", text_color=COLORS["muted"], font=TYPOGRAPHY["caption"])
        self.run_status.pack(anchor="w", padx=28)
        self.progress = ctk.CTkProgressBar(self, height=SIZES["progress"])
        self.progress.pack(fill="x", padx=28, pady=(8, 20))
        self.progress.set(0)
        self.metrics = MetricStrip(self, (("received", "ENCONTRADOS", "text"), ("inserted", "INSERIDOS", "accent"), ("duplicates", "DUPLICADOS", "text")))
        self.metrics.pack(fill="x", padx=28)
        self.priority_summary = ctk.CTkLabel(self, text="Os resultados aparecerão aqui após a busca.", text_color=COLORS["text_secondary"])
        self.priority_summary.pack(anchor="w", padx=28, pady=12)
        links = ctk.CTkFrame(self, fg_color="transparent")
        links.pack(fill="x", padx=28, pady=(0, 12))
        if on_workspace:
            button(links, "Ir para Carteira", on_workspace, kind="secondary").pack(side="left", padx=(0, 8))
        self.open_excel_button = button(links, "Abrir Excel", self.open_last_excel, state="disabled", width=110)
        self.open_folder_button = button(links, "Abrir pasta", self.open_last_folder, state="disabled", width=110)
        ctk.CTkLabel(self, text="ATIVIDADE DA BUSCA", font=TYPOGRAPHY["caption"], text_color=COLORS["muted"]).pack(anchor="w", padx=28, pady=(4, 8))
        self.output = ctk.CTkTextbox(self, font=TYPOGRAPHY["console"], fg_color=COLORS["sidebar"], height=130)
        self.output.pack(fill="both", expand=True, padx=28, pady=(0, 24))
        self.output.configure(state="disabled")

    def update_target_label(self):
        enabled = bool(self.no_website_switch.get())
        self.quantity_label.configure(text="Meta de leads sem site próprio · até 100" if enabled else "Quantidade · até 100")
        self.target_hint.configure(text="Inclui redes sociais e plataformas externas. Busca até a meta, fim dos resultados ou limite de segurança." if enabled else "")

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
        for control in (self.no_website_switch, self.min_score):
            control.configure(state="disabled" if running else "normal")
        self.run_status.configure(text="Busca em andamento…" if running else "Busca encerrada.")

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
            only_without_website = bool(self.no_website_switch.get())
            if only_without_website:
                try:
                    min_score = int(self.min_score.get().strip())
                    if not 0 <= min_score <= 100:
                        raise ValueError
                except ValueError:
                    raise ValueError("Score mínimo deve ser inteiro entre 0 e 100.") from None
                params.update(only_without_website=True, min_score=min_score)
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
                        value.inserted / value.requested if kind == "done" and value.stats is not None else 1
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
                    if value.stats is not None:
                        self.progress.set(value.inserted / value.requested)
                    self.metrics.set(dict(received=value.received, inserted=value.inserted, duplicates=value.duplicates))
                    self.priority_summary.configure(text=f"PRIORIDADE   Alta {value.high_priority}   ·   Boa {value.good_priority}   ·   Média {value.medium_priority}   ·   Baixa {value.low_priority}")
                    self.run_status.configure(text="Busca interrompida. Resultados parciais preservados." if value.cancelled else "Busca finalizada.")
                    for message in value.errors[:10]:
                        self.append(
                            message
                        )

                    if value.exported_file:
                        self.open_excel_button.pack(side="left", padx=(0, 8))
                        self.open_folder_button.pack(side="left")
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
