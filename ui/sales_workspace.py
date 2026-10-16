"""Inline SDR workspace. Each lead owns its editor and background result queue."""
import queue
import threading
from tkinter import messagebox
import customtkinter as ctk

from core.database.lead_repository import LeadRepository
from core.database.interaction_repository import InteractionRepository
from core.sales.contact import ContactService, SDR_STATUSES
from core.sales.config import create_groq_provider
from core.sales.errors import SalesConfigurationError
from ui.components import field, button, keyboard_focus, badge
from ui.sdr_components import Card, KpiCard, StatusDot, Stepper, LeadListItem, StatusBar, LineIcon, IconButton, attach_icon, FullWidthTabs
from ui.copy_field import add_copy_field, copy_to_clipboard
from ui.browser_action import BrowserAction
from ui.sales_panel import SalesPanel
from ui.sales_workspace_logic import list_sales_leads, sales_counts, filter_sales_leads
from ui.responsive_text import WrappedLabels
from ui.sdr_diagnostics import event, timed, log_current_error
from ui.theme import COLORS, TYPOGRAPHY, RADIUS, SPACING
from core.commercial.values import commercial_status, status_options
from ui.settings import UserSettings, BROWSER_CHOICES
from ui.sdr_formatting import local_date, STATUS_LABELS

BG, CARD, TEXT, MUTED, ACCENT = (COLORS[key] for key in ("bg", "surface", "text", "muted", "primary"))


class SalesWorkspacePage(ctk.CTkFrame):
    def __init__(self, master, repository=None):
        super().__init__(master, fg_color=BG)
        event("screen_init")
        self.repository = repository
        self.settings = UserSettings()
        self.browser_preference = self.settings.browser()
        self._closed = False
        self._data = []
        self._load_queue = queue.Queue()
        self._load_busy = False
        self._reload_requested = False
        self._load_job = self._filter_job = self._render_job = None
        self._page_index = 0
        self._page_size = 12
        self._row_pool = []
        self.selected_id = None
        self.editors = {}
        self.cards = {}
        self.connection_queue = queue.Queue()
        self.connection_job = None
        self.connection_busy = False
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=SPACING["lg"], pady=(SPACING["sm"], SPACING["xs"]))
        header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(header, text="SDR Inteligente", font=TYPOGRAPHY["title"], text_color=TEXT).grid(row=0, column=0, sticky="w")
        self.stepper = Stepper(header)
        self.stepper.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(8, 4))
        self.connection_label = StatusDot(header, text="Groq não verificada")
        self.connection_label.grid(row=2, column=0, sticky="w")
        self.test_button = attach_icon(button(header, "Testar Groq", self.test_connection, width=140), "sales")
        self.test_button.grid(row=0, column=1, padx=4)
        attach_icon(button(header, "Atualizar leads", self.refresh, width=150), "refresh").grid(row=0, column=2, padx=(4, 0))
        browser_row = Card(header, corner_radius=8)
        browser_row.grid(row=2, column=1, columnspan=2, sticky="e")
        ctk.CTkLabel(browser_row, text="Abrir WhatsApp com", font=TYPOGRAPHY["caption"], text_color=MUTED).pack(side="left", padx=(0, 8))
        self.browser_selector = ctk.CTkComboBox(browser_row, values=list(BROWSER_CHOICES), state="readonly",
            width=235, height=28, font=TYPOGRAPHY["caption"], command=self.choose_browser)
        self.browser_selector.set(next(label for label, value in BROWSER_CHOICES.items() if value == self.browser_preference))
        self.browser_selector.configure(border_width=0, fg_color=COLORS["bg_elevated"])
        self.browser_selector.pack(side="left")
        self.preference_notice = ctk.CTkLabel(header, text="", text_color=COLORS["warning"], font=TYPOGRAPHY["caption"], wraplength=360)
        try:
            with timed("groq_configuration_only"):
                create_groq_provider()  # local configuration only; no network request
        except SalesConfigurationError:
            self.connection_label.configure(text="Groq não configurada")
        metrics = ctk.CTkFrame(self, fg_color="transparent")
        metrics.pack(fill="x", padx=20, pady=(2, 8))
        self.metrics = {}
        for col, (key, title) in enumerate((("leads", "Total de leads"), ("pending", "Aguardando revisão"),
                ("contacted", "Contatados"), ("interested", "Interessados"), ("meetings", "Reuniões marcadas"))):
            metrics.grid_columnconfigure(col, weight=1, uniform="metrics")
            card = KpiCard(metrics, title.replace("Aguardando revisão", "A revisar").replace("Reuniões marcadas", "Reuniões").replace("Total de leads", "Leads"),
                tone=("accent", "warning", "info", "success", "draft")[col],
                icon=("workspace", "search", "sales", "dashboard", "day")[col])
            card.grid(row=0, column=col, sticky="nsew", padx=(0, SPACING["sm"]))
            self.metrics[key] = card.value
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=SPACING["lg"], pady=(SPACING["xs"], SPACING["md"]))
        body.grid_rowconfigure(0, weight=1)
        body.grid_columnconfigure(0, weight=0, minsize=360)
        body.grid_columnconfigure(1, weight=1, minsize=440)
        left = Card(body, fg_color=CARD, width=360)
        left.pack_propagate(False)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        form = ctk.CTkFrame(left, fg_color="transparent")
        form.pack(fill="x", padx=12, pady=12)
        self.filters = {}
        search = ctk.CTkFrame(form, fg_color="transparent")
        search.pack(fill="x")
        LineIcon(search, "places", background=CARD).pack(side="left", padx=(0, 8))
        IconButton(search, "clear", lambda: (self.filters["search"].delete(0, "end"), self.schedule_filter()),
               width=32, height=32).pack(side="right")
        self.filters["search"] = ctk.CTkEntry(search, placeholder_text="Buscar empresa", height=36)
        self.filters["search"].pack(side="left", fill="x", expand=True)
        self.filters["search"].bind("<KeyRelease>", lambda event: self.schedule_filter())
        self.filters["search"].bind("<Down>", lambda event: self.focus_leads())
        choices = ctk.CTkFrame(form, fg_color="transparent")
        choices.pack(fill="x", pady=(10, 0))
        for col, (key, label, options) in enumerate((("segment", "Segmento", ["Todos os segmentos"]), ("status", "Etapa", ["Todas as etapas", *SDR_STATUSES]))):
            choices.grid_columnconfigure(col, weight=1, uniform="filters")
            cell = ctk.CTkFrame(choices, fg_color="transparent")
            cell.grid(row=0, column=col, sticky="ew", padx=(0, 5))
            self.filters[key] = field(cell, label, options=options, value=options[0], width=100, command=lambda value: self.schedule_filter())
            self.filters[key].bind("<Return>", lambda event: self.schedule_filter())
        button(form, "Limpar filtros", self.clear_filters, kind="ghost", height=28).pack(anchor="w", pady=(4, 0))
        pager = ctk.CTkFrame(left, fg_color="transparent")
        pager.pack(side="bottom", fill="x", padx=12, pady=8)
        button(pager, "Anterior", lambda: self.change_page(-1), width=65, height=28, kind="ghost").pack(side="left")
        button(pager, "Próxima", lambda: self.change_page(1), width=65, height=28, kind="ghost").pack(side="right")
        self.page_notice = ctk.CTkLabel(pager, text="Carregando…", text_color=MUTED)
        self.page_notice.pack()
        self.list_state = ctk.CTkLabel(left, text="Carregando leads…", text_color=MUTED, wraplength=230, justify="left")
        self.list_state.pack(fill="x", padx=14)
        self.lead_list = ctk.CTkScrollableFrame(left, fg_color="transparent", width=320)
        self.lead_list.pack(fill="both", expand=True, padx=6, pady=(0, 6))
        self.right = ctk.CTkFrame(body, fg_color=CARD, corner_radius=RADIUS["surface"])
        self.right.grid(row=0, column=1, sticky="nsew")
        self.empty = ctk.CTkLabel(self.right, text="Selecione uma empresa\n\nRevise os dados e a mensagem antes de abrir o WhatsApp.\nUse ↓ na busca para navegar pela lista.", wraplength=340, justify="left", text_color=MUTED)
        self.empty.pack(padx=24, pady=40)
        event("components_ready")
        keyboard_focus(header)
        keyboard_focus(form)
        keyboard_focus(pager)
        self._load_job = self.after(1, self.refresh)

    def choose_browser(self, label):
        selected = BROWSER_CHOICES.get(label)
        if selected is None:
            return
        self.browser_preference = selected
        try:
            self.settings.save_browser(selected)
            self.preference_notice.grid_remove()
        except OSError:
            self.preference_notice.configure(text="Escolha aplicada nesta sessão. Não foi possível salvar a preferência local.")
            self.preference_notice.grid(row=3, column=1, columnspan=2, sticky="e")

    def clear_filters(self):
        self.filters["search"].delete(0, "end")
        self.filters["segment"].set("Todos os segmentos")
        self.filters["status"].set("Todas as etapas")
        self.apply_filters()

    def focus_leads(self):
        if self.cards:
            self.cards.get(self.selected_id, next(iter(self.cards.values())))._canvas.focus_set()
        return "break"

    def move_focus(self, identity, delta):
        keys = list(self.cards)
        if identity in keys:
            card = self.cards[keys[max(0, min(len(keys) - 1, keys.index(identity) + delta))]]
            card._canvas.focus_set()
            canvas = self.lead_list._parent_canvas
            y, height = card.winfo_y(), card.winfo_height()
            top, viewport = canvas.canvasy(0), canvas.winfo_height()
            target = y if y < top else y + height - viewport if y + height > top + viewport else top
            canvas.yview_moveto(max(0, target) / max(1, self.lead_list.winfo_height()))
        return "break"

    def refresh(self):
        if self._closed:
            return
        if self._load_busy:
            self._reload_requested = True
            return
        self._load_busy = True
        self.page_notice.configure(text="Carregando…")
        repository = self.repository
        results = self._load_queue
        def load():
            try:
                with timed("database_load"):
                    repo = repository if repository is not None else LeadRepository()
                    rows = list_sales_leads(repo)
                    stats = sales_counts(rows)
                results.put((repo, rows, stats, False))
            except Exception:
                log_current_error()
                results.put((None, None, None, True))
        threading.Thread(target=load, daemon=True).start()
        self._load_job = self.after(30, self.poll_load)

    def poll_load(self):
        self._load_job = None
        if self._closed:
            return
        try:
            repo, rows, stats, error = self._load_queue.get_nowait()
        except queue.Empty:
            self._load_job = self.after(30, self.poll_load)
            return
        self._load_busy = False
        if self._reload_requested:
            self._reload_requested = False
            self.refresh()
            return
        if error:
            self.page_notice.configure(text="Falha ao carregar. Atualize.")
            self.list_state.configure(text="Não foi possível carregar os leads. Use Atualizar leads para tentar novamente.", text_color=COLORS["danger"])
            return
        self.repository, self._data = repo, rows
        with timed("indicators"):
            for key, label in self.metrics.items():
                label.configure(text=str(stats[key]))
            self.filters["segment"].configure(values=["Todos os segmentos", *sorted({r["segmento"] for r in rows if r["segmento"]})])
        self.apply_filters()
        # Do not query every cached editor during every list refresh.
        if self.selected_id in self.editors:
            self.editors[self.selected_id].update_summary(sync_status=False)

    def schedule_filter(self):
        if self._filter_job is not None:
            self.after_cancel(self._filter_job)
        self._filter_job = self.after(180, self.apply_filters)

    def apply_filters(self):
        self._filter_job = None
        self._page_index = 0
        self.render_page()

    def change_page(self, delta):
        self._page_index = max(0, self._page_index + delta)
        self.render_page()

    def render_page(self):
        if self._closed:
            return
        if self._render_job is not None:
            self.after_cancel(self._render_job)
            self._render_job = None
        rows = filter_sales_leads(self._data, **{key: widget.get() for key, widget in self.filters.items()})
        pages = max(1, (len(rows) + self._page_size - 1) // self._page_size)
        self._page_index = min(self._page_index, pages - 1)
        start = self._page_index * self._page_size
        visible = rows[start:start + self._page_size]
        self.page_notice.configure(text=f"{self._page_index + 1}/{pages} · {len(rows)} leads")
        self.list_state.configure(text="" if rows else ("Nenhuma empresa corresponde aos filtros. Use Limpar filtros." if self._data else "Sua carteira está vazia. Importe uma planilha ou busque leads na Prospecção."), text_color=MUTED)
        self.cards = {}
        for item in self._row_pool:
            item["card"].pack_forget()
            item["card"].lead_id = None
        self._render_batch(visible, 0)

    def _render_batch(self, rows, start):
        self._render_job = None
        if self._closed:
            return
        with timed("render_batch"):
            for index in range(start, min(start + 3, len(rows))):
                row = rows[index]
                if index == len(self._row_pool):
                    card = LeadListItem(self.lead_list)
                    card._canvas.configure(takefocus=1)
                    name, details = card.name, card.details
                    for widget in (card, name, details, card.tags, card.stage, card.draft):
                        widget.bind("<Enter>", lambda event, c=card: c.configure(fg_color=COLORS["surface_hover"]))
                        widget.bind("<Leave>", lambda event, c=card: c.selected(c.lead_id == self.selected_id))
                        widget.bind("<Button-1>", lambda event, c=card: (c._canvas.focus_set(), self.select_lead(c.lead_id)) if c.lead_id is not None else None)
                    card.bind("<Return>", lambda event, c=card: self.select_lead(c.lead_id))
                    card.bind("<space>", lambda event, c=card: self.select_lead(c.lead_id))
                    card.bind("<Down>", lambda event, c=card: self.move_focus(c.lead_id, 1))
                    card.bind("<Up>", lambda event, c=card: self.move_focus(c.lead_id, -1))
                    card.bind("<FocusIn>", lambda event, c=card: c.configure(border_color=COLORS["accent"]))
                    card.bind("<FocusOut>", lambda event, c=card: c.configure(border_color=COLORS["accent"] if c.lead_id == self.selected_id else COLORS["border"]))
                    self._row_pool.append(dict(card=card, name=name, details=details))
                item = self._row_pool[index]
                card = item["card"]
                card.lead_id = row["id"]
                card.selected(row["id"] == self.selected_id)
                item["name"].configure(text=row["empresa"])
                draft_label = {"GERADA": "Rascunho de IA", "EDITADA": "IA editada", "APROVADA": "IA aprovada"}.get(row.get("draft_status"), "Sem rascunho de IA")
                item["details"].configure(text=row["segmento"] or "Sem segmento")
                card.stage.configure(text=row["display_status"])
                has_draft = row.get("draft_status") in ("GERADA", "EDITADA", "APROVADA")
                card.draft.configure(text=draft_label if has_draft else "Sem rascunho",
                    text_color=COLORS["draft"] if has_draft else MUTED,
                    fg_color=COLORS["draft_surface"] if has_draft else COLORS["surface_secondary"])
                card.pack(fill="x", pady=4)
                self.cards[row["id"]] = card
        if start + 3 < len(rows):
            self._render_job = self.after(10, lambda: self._render_batch(rows, start + 3))
        else:
            event("list_ready", visible=len(rows), pooled=len(self._row_pool))

    def select_lead(self, lead_id):
        if lead_id == self.selected_id:
            return
        with timed("selected_lead_query"):
            row = self.repository.get_lead(lead_id)
        if row is None:
            self.refresh()
            return
        self.empty.pack_forget()
        for frame in self.editors.values():
            frame.pack_forget()
        self.selected_id = lead_id
        if lead_id not in self.editors:
            with timed("selected_lead_widgets"):
                self.editors[lead_id] = self.build_editor(row)
        self.editors[lead_id].pack(fill="both", expand=True, padx=12, pady=10)
        self.editors[lead_id].update_summary(sync_status=False)
        for identity, card in self.cards.items():
            card.configure(fg_color=COLORS["bg_elevated"] if identity == lead_id else CARD,
                           border_color=COLORS["accent"] if identity == lead_id else COLORS["border"])
        self.prune_editors()
        self.stepper.set(2 if self.editors[lead_id].contact.open_button.cget("state") == "normal" else 1)

    def prune_editors(self):
        # Keep pending work and unsaved edits; clean hidden editors are expendable.
        for identity, frame in list(self.editors.items()):
            if len(self.editors) <= 3:
                break
            if identity != self.selected_id and frame.can_release():
                frame.destroy()
                del self.editors[identity]

    def build_editor(self, row):
        lead_id = row["id"]
        frame = ctk.CTkFrame(self.right, fg_color="transparent")
        title = ctk.CTkLabel(frame, text=row["empresa"], font=TYPOGRAPHY["lead_title"],
            text_color=TEXT, justify="left", anchor="w")
        title.pack(fill="x")
        chips = ctk.CTkFrame(frame, fg_color="transparent")
        chips.pack(fill="x", pady=(4, 8))
        segment_chip = badge(chips, row["segmento"] or "Sem segmento")
        segment_chip.pack(side="left", padx=(0, 4))
        stage_chip = badge(chips, commercial_status(row["status"]), "accent")
        stage_chip.pack(side="left", padx=(0, 4))
        phone_chip = badge(chips, "Telefone")
        phone_chip.pack(side="left")
        phone_value = {"text": (row["whatsapp"] or "").strip() or row["telefone"]}
        button(chips, "Copiar", lambda: frame.sales.feedback.configure(text=copy_to_clipboard(chips, phone_value["text"])),
            kind="ghost", width=55, height=26).pack(side="left", padx=4)
        # Only the selected section scrolls: the message and contact action stay in view.
        tabs = frame.tabs = FullWidthTabs(frame, fg_color=BG, corner_radius=8, anchor="w")
        for name in ("Mensagem", "Dados do lead", "Histórico"):
            tabs.add(name)
        footer = ctk.CTkFrame(frame, fg_color="transparent")
        footer.pack(side="bottom", fill="x", pady=(6, 0))
        tabs.pack(fill="both", expand=True)
        frame.sales = SalesPanel(tabs.tab("Mensagem"), self.repository, lead_id,
            inline=True, on_completed=self.generation_completed)
        contact = frame.contact = ContactPanel(tabs.tab("Dados do lead"),
            self.repository, lead_id, frame.sales, notice_parent=footer,
            get_browser=lambda: self.browser_preference)
        # One status surface for both draft and browser feedback.
        frame.sales._wrap.labels = (frame.sales.info,)
        frame.sales.feedback.destroy()
        frame.sales.feedback = contact.notice
        def show_presentation_state():
            contact.update_availability()
            if self.selected_id == lead_id:
                self.stepper.set(2 if contact.open_button.cget("state") == "normal" else 1)
        frame.sales.on_state_changed = show_presentation_state
        frame.contact_is_saved = lambda: all(widget.get() == contact.saved_values[key]
            for key, widget in contact.fields.items())
        frame.can_release = lambda: (not frame.sales.busy
            and frame.sales.message.get("1.0", "end-1c") == frame.sales.loaded_text
            and frame.contact_is_saved() and not contact.browser_action.busy)

        def update_state(*, sync_status=True):
            current = self.repository.get_lead(lead_id)
            if current is None:
                return
            phone = (current["whatsapp"] or "").strip() or current["telefone"] or "Telefone não informado"
            segment_chip.configure(text=current["segmento"] or "Sem segmento")
            stage_chip.configure(text=commercial_status(current["status"]))
            phone_chip.configure(text=phone)
            phone_value["text"] = (current["whatsapp"] or "").strip() or current["telefone"]
            frame.sales.refresh_contact_type()
            contact.update_availability()
        contact.on_saved = lambda: (update_state(), self.refresh())
        frame.update_summary = update_state
        update_state()
        history = ctk.CTkTextbox(tabs.tab("Histórico"), wrap="word", font=TYPOGRAPHY["secondary"])
        def show_history():
            parts = []
            for item in frame.sales.outreach.history(lead_id):
                parts.append(f"{local_date(item['criado_em'])} · #{item['id']} · {STATUS_LABELS.get(item['status'], item['status'])}\nRevisão: {local_date(item['revisado_em']) if item['revisado_em'] else '—'}\n{item['mensagem']}")
            for item in frame.sales.outreach.revisions(lead_id):
                parts.append(f"Versão anterior · {local_date(item['recorded_at'])}\n{item['mensagem']}")
            for item in InteractionRepository(self.repository.path).list_interactions(lead_id):
                parts.append(f"{local_date(item['created_at'])} · {item['tipo']}\n{item['descricao']}")
            history.configure(state="normal")
            history.delete("1.0", "end")
            history.insert("1.0", "\n\n".join(parts) or "Nenhum histórico registrado.")
            history.configure(state="disabled")
        button(tabs.tab("Histórico"), "Atualizar histórico", show_history, height=30).pack(anchor="w", pady=(0, 6))
        history.pack(fill="both", expand=True)
        show_history()
        keyboard_focus(frame)
        frame._wrap = WrappedLabels(frame, (title,), padding=0, minimum=150)
        return frame

    def generation_completed(self, provider, error):
        if provider is not None and getattr(provider, "provider_name", None) == "groq":
            self.connection_label.configure(text="Erro de conexão" if error else
                ("Groq conectada" if provider.connection_verified else "Groq não verificada"))
        self.refresh()

    def test_connection(self):
        event("groq_test_requested")
        if self.connection_busy:
            return
        try:
            provider = create_groq_provider()
        except SalesConfigurationError:
            self.connection_label.configure(text="Groq não configurada")
            return
        self.connection_busy = True
        self.test_button.configure(state="disabled")
        self.connection_label.configure(text="Verificando Groq…")
        def worker():
            try:
                with timed("groq_test"):
                    provider.test_connection()
                self.connection_queue.put(True)
            except Exception:
                log_current_error()
                self.connection_queue.put(False)
        threading.Thread(target=worker, daemon=True).start()
        self.connection_job = self.after(100, self.poll_connection)

    def poll_connection(self):
        self.connection_job = None
        try:
            success = self.connection_queue.get_nowait()
        except queue.Empty:
            self.connection_job = self.after(100, self.poll_connection)
            return
        self.connection_busy = False
        self.test_button.configure(state="normal")
        self.connection_label.configure(text="Groq conectada" if success else "Erro de conexão")

    def destroy(self):
        self._closed = True
        for job in (self.connection_job, self._load_job, self._filter_job, self._render_job):
            if job is not None:
                self.after_cancel(job)
        event("screen_destroy")
        super().destroy()

    def can_leave(self):
        for frame in self.editors.values():
            if not frame.sales.confirm_discard():
                return False
            if not frame.contact_is_saved() and not messagebox.askyesno(
                    "Acompanhamento não salvo", "Descartar as alterações do acompanhamento comercial e sair?", parent=self):
                return False
        return True


class ContactPanel(ctk.CTkScrollableFrame):
    def __init__(self, master, repository, lead_id, sales, *, notice_parent=None, get_browser=None):
        super().__init__(master, fg_color="transparent")
        self.pack(fill="both", expand=True)
        self.service, self.lead_id, self.sales = ContactService(repository), lead_id, sales
        self.browser_action = BrowserAction(self, self.browser_completed, browser=get_browser,
            unavailable=self.browser_unavailable)
        row = repository.get_lead(lead_id)
        ctk.CTkLabel(self, text="Acompanhamento comercial", font=TYPOGRAPHY["section"]).pack(anchor="w", pady=(4, 0))
        hint = ctk.CTkLabel(self, text="Registre seus próximos avanços quando necessário. Para conversar, revise a mensagem e use Abrir WhatsApp. Datas: dd/mm/aaaa HH:MM, no horário local.",
            text_color=MUTED, justify="left", anchor="w", wraplength=400)
        hint.pack(fill="x", pady=(0, 8))
        self.fields = {}
        form = ctk.CTkFrame(self, fg_color="transparent")
        form.pack(fill="x")
        form.grid_columnconfigure((0, 1), weight=1, uniform="contact")
        from ui.commercial_logic import format_date
        for index, (key, label, value, options) in enumerate((
            ("responsible", "Responsável", row["responsavel"], None),
            ("status", "Etapa comercial", commercial_status(row["status"]), status_options(row["status"])),
            ("contact_at", "Último contato manual", format_date(row["ultimo_contato"]), None),
            ("notes", "Observações comerciais", row["observacoes"], None))):
            cell = ctk.CTkFrame(form, fg_color="transparent")
            cell.grid(row=index // 2, column=index % 2, sticky="ew", padx=(0, 8), pady=(0, 8))
            kwargs = dict(command=lambda value: self.update_availability()) if options else {}
            self.fields[key] = field(cell, label, value=value or "", options=options, width=150, **kwargs)
            self.fields[key].bind("<KeyRelease>", lambda event: self.update_availability())
        self.saved_values = {key: widget.get() for key, widget in self.fields.items()}
        button(self, "Salvar acompanhamento", self.save, height=34).pack(anchor="w", pady=(0, 6))
        self.save_feedback = ctk.CTkLabel(self, text="", text_color=MUTED, justify="left", anchor="w", wraplength=400)
        self.save_feedback.pack(fill="x")
        ctk.CTkLabel(self, text="Dados do lead", font=TYPOGRAPHY["section"]).pack(anchor="w", pady=(12, 4))
        for key, label in (("empresa", "Empresa"), ("segmento", "Segmento"), ("telefone", "Telefone"),
                ("whatsapp", "WhatsApp"), ("email", "Email"), ("endereco", "Endereço"), ("cidade", "Cidade"),
                ("google_maps", "Google Maps"), ("site", "Site"), ("opportunity", "Oportunidade (hipótese)")):
            add_copy_field(self, label, row[key])
        footer = notice_parent if notice_parent is not None else self
        actions = ctk.CTkFrame(footer, fg_color="transparent")
        actions.pack(fill="x")
        self.open_button = button(actions, "Abrir WhatsApp", self.open_whatsapp, kind="primary", width=190, height=40)
        self.open_button.pack(side="right")
        self.copy_button = button(actions, "Copiar link", self.copy_link, kind="ghost", width=100, height=36)
        self.copy_button.pack(side="left")
        self.notice = StatusBar(footer, text="", wraplength=400, justify="left", anchor="w", font=TYPOGRAPHY["caption"], text_color=MUTED)
        self.notice.pack(fill="x", pady=(4, 0))
        self._wrap = WrappedLabels(footer, (self.notice,), padding=0)
        self._hint_wrap = WrappedLabels(self, (hint, self.save_feedback), padding=20)
        self.update_availability()

    def update_availability(self):
        try:
            self.current_url()
            enabled, message = True, "Revise a mensagem. A conversa será aberta sem envio automático."
            if self.browser_action.busy:
                enabled, message = False, "Abrindo o navegador… Aguarde a confirmação."
        except ValueError as error:
            enabled, message = False, str(error)
            if message == "A mensagem não pode ficar vazia.":
                message = "Sem rascunho. Gere uma abordagem na aba Mensagem e revise o texto antes de abrir a conversa."
        except Exception:
            enabled, message = False, "Não foi possível verificar os requisitos. Atualize os leads."
        self.open_button.configure(state="normal" if enabled else "disabled")
        self.copy_button.configure(state="normal" if enabled else "disabled")
        self.notice.configure(text=message, text_color=MUTED if enabled else COLORS["warning"])

    def save(self):
        from ui.commercial_logic import parse_contact_date
        try:
            values = {key: widget.get() for key, widget in self.fields.items()}
            values["contact_at"] = parse_contact_date(values["contact_at"])
            self.service.save_tracking(self.lead_id, **values)
            self.saved_values = {key: widget.get() for key, widget in self.fields.items()}
            self.save_feedback.configure(text="Acompanhamento salvo. Nenhuma mensagem enviada.", text_color=COLORS["success"])
            self.update_availability()
            if getattr(self, "on_saved", None):
                self.on_saved()
            return True
        except ValueError as error:
            self.save_feedback.configure(text=str(error), text_color=COLORS["danger"])
        except Exception:
            self.save_feedback.configure(text="Não foi possível salvar o acompanhamento.", text_color=COLORS["danger"])
        return False

    def current_url(self):
        if self.sales.busy:
            raise ValueError("Aguarde a geração e revise a mensagem.")
        if self.fields["status"].get() == "Não contatar":
            raise ValueError("Contato bloqueado: este lead está marcado como Não contatar.")
        if any(row["id"] == self.sales.current_id and row["status"] == "CANCELADA" for row in self.sales.rows.values()):
            raise ValueError("Esta versão foi descartada. Abra outro rascunho ou gere uma nova versão na aba Mensagem.")
        return self.service.preview_url(self.lead_id, self.sales.message.get("1.0", "end-1c"))

    def copy_link(self):
        try:
            self.notice.configure(text=copy_to_clipboard(self, self.current_url()))
        except ValueError as error:
            self.notice.configure(text=str(error))
        except Exception:
            log_current_error()
            self.notice.configure(text="Não foi possível preparar o link. Atualize os dados do lead.")

    def open_whatsapp(self):
        try:
            url = self.current_url()
            if self.browser_action.open(url):
                self.update_availability()
        except ValueError as error:
            self.update_availability()
            self.notice.configure(text=str(error))
        except Exception:
            log_current_error()
            self.notice.configure(text="Não foi possível preparar o link. Atualize os dados do lead.")

    def browser_completed(self, success):
        self.update_availability()
        self.notice.configure(text="Conversa solicitada ao navegador. Revise e envie manualmente; o status não foi alterado."
                              if success else "Não foi possível abrir a conversa no navegador escolhido. Tente novamente ou use Copiar link.",
                              text_color=COLORS["success"] if success else COLORS["warning"])

    def browser_unavailable(self):
        self.update_availability()
        label = next((label for label, value in BROWSER_CHOICES.items()
                      if value == self.browser_action.requested_browser), "O navegador escolhido")
        if messagebox.askyesno("Navegador não encontrado",
                f"{label} não foi encontrado neste computador.\n\nAbrir esta conversa pelo navegador padrão do sistema?",
                parent=self.winfo_toplevel()):
            try:
                # Revalidate current lead/message, including restrictions changed meanwhile.
                if self.browser_action.open(self.current_url(), browser="default"):
                    self.update_availability()
            except ValueError as error:
                self.notice.configure(text=str(error))
            except Exception:
                self.notice.configure(text="Não foi possível abrir o navegador padrão. Use Copiar link e cole no navegador.",
                                      text_color=COLORS["warning"])
        else:
            self.notice.configure(text=f"{label} não encontrado. Escolha outro navegador em Abrir WhatsApp com.",
                                  text_color=COLORS["warning"])

    def destroy(self):
        self.browser_action.close()
        super().destroy()
