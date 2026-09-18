"""Human review panel; worker communicates through a queue, never Tk calls."""
import queue
import threading
import customtkinter as ctk

from core.sales.agent import SalesAgent, SalesGenerationError
from core.sales.errors import SalesConfigurationError
from core.sales.provider import create_sales_provider
from core.database.outreach_repository import OutreachRepository
from ui.components import button
from ui.theme import COLORS


class SalesPanel(ctk.CTkFrame):
    def __init__(self, master, repository, lead_id):
        super().__init__(master, fg_color="transparent")
        self.pack(fill="both", expand=True)
        self.repository, self.lead_id = repository, lead_id
        self.outreach = OutreachRepository(repository.path)
        self.pending = queue.Queue()
        self.busy, self.job, self.current_id, self.snapshot = False, None, None, None
        self.rows = {}
        ctk.CTkLabel(self, text="Rascunhos de IA · aprovação salva a versão, sem enviar contato.",
                     text_color=COLORS["muted"], wraplength=650).pack(pady=8)
        self.history = ctk.CTkComboBox(self, values=["Nenhuma abordagem"], state="readonly", command=self.select)
        self.history.pack(fill="x", padx=12)
        self.info = ctk.CTkLabel(self, text="", wraplength=650)
        self.info.pack(padx=12, pady=8)
        self.message = ctk.CTkTextbox(self, wrap="word")
        self.message.pack(fill="both", expand=True, padx=12)
        actions = ctk.CTkFrame(self, fg_color="transparent")
        actions.pack(fill="x", padx=12, pady=8)
        self.buttons = []
        for index, (label, command) in enumerate((("Gerar abordagem com IA", self.generate),
                ("Regenerar", lambda: self.generate(True)), ("Salvar edição", lambda: self.save("EDITADA")),
                ("Aprovar", lambda: self.save("APROVADA")), ("Cancelar", lambda: self.save("CANCELADA")))):
            control = button(actions, label, command, kind="primary" if index == 0 else "secondary")
            control.grid(row=index // 3, column=index % 3, padx=4, pady=4, sticky="ew")
            self.buttons.append(control)
        self.feedback = ctk.CTkLabel(self, text="Revisão humana obrigatória. Confiança não é probabilidade de venda.", wraplength=650)
        self.feedback.pack(padx=12, pady=8)
        self.refresh()

    def refresh(self, selected=None):
        rows = self.outreach.history(self.lead_id)
        self.rows = {f"#{r['id']} · {r['criado_em'][:19]} UTC · {r['status']}": dict(r) for r in rows}
        self.history.configure(values=list(self.rows) or ["Nenhuma abordagem"])
        choice = next((label for label, row in self.rows.items() if row["id"] == selected), next(iter(self.rows), "Nenhuma abordagem"))
        self.history.set(choice)
        self.select(choice)

    def select(self, label):
        row = self.rows.get(label)
        self.current_id = row["id"] if row else None
        self.message.configure(state="normal")
        self.message.delete("1.0", "end")
        if row:
            self.message.insert("1.0", row["mensagem"])
        self.info.configure(text=f"Ângulo: {row['angulo']} · Confiança: {row['confianca']} · {row['status']}" if row else "Gere um rascunho para revisar.")
        editable = bool(row and row["status"] in ("GERADA", "EDITADA"))
        self.message.configure(state="normal" if editable else "disabled")
        for control in self.buttons[2:]:
            control.configure(state="normal" if editable and not self.busy else "disabled")

    def generate(self, regenerate=False):
        if self.busy:
            return
        try:
            agent = SalesAgent(self.repository, create_sales_provider())
            if not regenerate or self.snapshot is None:
                self.snapshot = agent.evidence(self.lead_id)
        except SalesConfigurationError as error:
            self.feedback.configure(text=str(error))
            return
        except Exception:
            self.feedback.configure(text="Confira a configuração de IA e se o lead ainda existe.")
            return
        self.busy = True
        for control in self.buttons:
            control.configure(state="disabled")
        self.history.configure(state="disabled")
        self.message.configure(state="disabled")
        self.feedback.configure(text="Gerando rascunho…")
        def worker():
            try:
                self.pending.put((agent.generate(self.lead_id, evidence=self.snapshot), None))
            except SalesGenerationError as error:
                self.pending.put((None, str(error)))
            except Exception:
                self.pending.put((None, "Não foi possível gerar/salvar o rascunho. Confira a configuração e tente novamente."))
        threading.Thread(target=worker, daemon=True).start()
        self.job = self.after(100, self.poll)

    def poll(self):
        self.job = None
        try:
            draft_id, error = self.pending.get_nowait()
        except queue.Empty:
            self.job = self.after(100, self.poll)
            return
        self.busy = False
        for control in self.buttons[:2]:
            control.configure(state="normal")
        self.history.configure(state="readonly")
        if error:
            row = next((r for r in self.rows.values() if r["id"] == self.current_id), None)
            editable = bool(row and row["status"] in ("GERADA", "EDITADA"))
            self.message.configure(state="normal" if editable else "disabled")
            for control in self.buttons[2:]:
                control.configure(state="normal" if editable else "disabled")
        else:
            self.refresh(draft_id)
        self.feedback.configure(text=error or "Rascunho salvo. Revise antes de aprovar.")

    def save(self, status):
        if self.busy or self.current_id is None:
            return
        try:
            self.outreach.update(self.lead_id, self.current_id, status=status, message=self.message.get("1.0", "end-1c"))
            self.refresh(self.current_id)
            self.feedback.configure(text="Versão salva. Nenhuma mensagem foi enviada.")
        except (ValueError, LookupError) as error:
            self.feedback.configure(text=str(error))
        except Exception:
            self.feedback.configure(text="Não foi possível salvar a versão no banco local.")

    def destroy(self):
        if self.job is not None:
            self.after_cancel(self.job)
        # An in-flight HTTP request may finish and save GERADA; never APPROVADA.
        super().destroy()
