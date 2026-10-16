"""One bounded worker, process-local results, cooperative cancellation."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from io import BytesIO, StringIO
from threading import Event, RLock
from time import monotonic
from uuid import uuid4
import csv
import sqlite3

from core.database.lead_repository import FIELDS, LeadRepository
from core.prospecting.service import prospect
from core.prospecting.limits import MAX_CANDIDATES_SCANNED, DEFAULT_MAX_REQUESTS, ProspectingStopReason, STOP_MESSAGES
from core.providers.environment import load_environment
from core.providers.google_places import GooglePlacesProvider
from .models import SearchRequest, SearchStatus
from .storage import SelectionStore

TERMINAL = {"completed", "failed", "cancelled"}


class JobError(Exception):
    def __init__(self, message, status=409):
        self.message, self.status = message, status


def configured_provider():
    # Existing configuration/key is loaded only on an explicit search action.
    load_environment()
    return GooglePlacesProvider(timeout=15, max_requests=DEFAULT_MAX_REQUESTS)


@dataclass
class Job:
    request: SearchRequest
    id: str = field(default_factory=lambda: uuid4().hex)
    status: str = "pending"
    rows: list = field(default_factory=list)
    cancel: Event = field(default_factory=Event)
    deadline: float = 0
    finished: float | None = None
    scanned: int = 0
    requests: int = 0
    pages: int = 0
    error: str | None = None
    message: str = "Aguardando execução."


class JobManager:
    def __init__(self, store: SelectionStore, provider_factory=configured_provider, *, timeout=120, retention=900, max_jobs=20):
        self.store, self.provider_factory = store, provider_factory
        self.timeout, self.retention, self.max_jobs = timeout, retention, max_jobs
        self.lock = RLock()
        self.jobs = {}
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="places-local")

    def close(self):
        with self.lock:
            for job in self.jobs.values():
                if job.status not in TERMINAL:
                    job.cancel.set()
        self.executor.shutdown(wait=True, cancel_futures=True)

    def _purge(self):
        for key, job in list(self.jobs.items()):
            if job.finished is not None and monotonic()-job.finished >= self.retention:
                del self.jobs[key]

    def reap(self):
        with self.lock:
            self._purge()

    def get(self, job_id):
        with self.lock:
            self._purge()
            if job_id not in self.jobs:
                raise JobError("Pesquisa não encontrada ou expirada. Inicie uma nova pesquisa.", 404)
            return self.jobs[job_id]

    def start(self, request):
        with self.lock:
            self._purge()
            if any(j.status not in TERMINAL for j in self.jobs.values()):
                raise JobError("Já existe uma pesquisa em andamento. Aguarde ou cancele antes de iniciar outra.", 429)
            if len(self.jobs) >= self.max_jobs:
                raise JobError("Limite de pesquisas recentes atingido. Aguarde a expiração dos resultados.", 429)
            # Reject an unavailable/incompatible workspace before consuming quota.
            self.store.existing([])
            job = Job(request)
            self.jobs[job.id] = job
            self.executor.submit(self._run, job)
            return self.status(job.id)

    def status(self, job_id):
        with self.lock:
            job = self.get(job_id)
            return SearchStatus(id=job.id, query=job.request, status=job.status, found=len(job.rows), scanned=job.scanned,
                requestsMade=job.requests, pagesFetched=job.pages, requested=job.request.quantity,
                cancelRequested=job.cancel.is_set(), message=job.message, error=job.error,
                writesEnabled=self.store.enabled,
                expiresInSeconds=max(0,int(self.retention-(monotonic()-job.finished))) if job.finished else self.retention)

    def cancel(self, job_id):
        with self.lock:
            job = self.get(job_id)
            if job.status not in TERMINAL:
                job.cancel.set()
                job.message = "Cancelamento solicitado. Aguardando a chamada em andamento terminar."
            return self.status(job_id)

    def rows(self, job_id):
        with self.lock:
            return [dict(row) for row in self.get(job_id).rows]

    def results(self, job_id, page, page_size):
        rows = self.rows(job_id)
        selected = rows[(page-1)*page_size:page*page_size]
        existing = self.store.existing(selected)
        return {"items":[{"id":row["_result_id"], "company":row["empresa"], "phone":row.get("telefone"),
            "niche":row.get("segmento"), "location":row.get("cidade"), "address":row.get("endereco"),
            "website":row.get("site"), "score":row.get("qualification_score"), "alreadySaved":saved}
            for row,saved in zip(selected,existing)], "total":len(rows), "page":page, "pageSize":page_size}

    def save(self, job_id, ids):
        with self.lock:
            job = self.get(job_id)
            if job.status not in TERMINAL:
                raise JobError("Aguarde a conclusão ou o cancelamento antes de salvar.")
            rows = {row["_result_id"]:row for row in job.rows}
            if any(value not in rows for value in ids):
                raise JobError("Seleção contém resultados inexistentes.",422)
            selected = [{k:v for k,v in rows[value].items() if k != "_result_id"} for value in dict.fromkeys(ids)]
        return self.store.save(selected)

    def export(self, job_id, format):
        if self.get(job_id).status not in TERMINAL:
            raise JobError("Aguarde a pesquisa terminar para exportar os resultados.")
        rows = self.rows(job_id)
        columns = {"empresa":"Empresa", "segmento":"Segmento", "cidade":"Cidade", "endereco":"Endereço",
                   "telefone":"Telefone", "site":"Site", "qualification_score":"Score", "google_maps":"Google Maps"}
        # Neutralize spreadsheet formulas from untrusted business data.
        def safe(value):
            text = "" if value is None else str(value)
            return "'"+text if text.lstrip().startswith(("=","+","-","@")) or text.startswith(("\t","\r","\n")) else text
        values = [[safe(row.get(key)) for key in columns] for row in rows]
        if format == "csv":
            output = StringIO(newline="")
            writer = csv.writer(output, delimiter=";")
            writer.writerow(columns.values()); writer.writerows(values)
            return output.getvalue().encode("utf-8-sig"), "text/csv; charset=utf-8"
        from openpyxl import Workbook
        output = BytesIO()
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Prospecção"
        sheet.append(list(columns.values()))
        for row in values:
            sheet.append(row)
        workbook.save(output)
        return output.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

    def _run(self, job):
        provider = None
        job.deadline = monotonic()+self.timeout
        manager = self

        class Stop:
            def is_set(self):
                return job.cancel.is_set() or monotonic() >= job.deadline

        class Tracked:
            @property
            def request_count(self): return provider.request_count
            @property
            def pages_fetched(self): return getattr(provider,"pages_fetched",0)
            def iter_search(self, **kwargs):
                for candidate in provider.iter_search(**kwargs):
                    with manager.lock:
                        job.scanned += 1
                        job.requests, job.pages = self.request_count, self.pages_fetched
                    yield candidate

        class Stage:
            def __init__(self):
                self.connection = sqlite3.connect(":memory:")
                self.connection.execute("CREATE TABLE leads(id INTEGER PRIMARY KEY,"+",".join(f'"{name}" TEXT' for name in (*FIELDS,"created_at","updated_at"))+")")
            def create_lead_if_new(self, data):
                if not isinstance(data.get("empresa"),str) or not data["empresa"].strip():
                    raise ValueError("Missing business name")
                if LeadRepository.find_existing(self.connection,data) is not None:
                    return None
                inserted = LeadRepository._insert(self.connection,data)
                with manager.lock:
                    job.rows.append({**data,"_result_id":len(job.rows)+1})
                return inserted

        stage = None
        try:
            with self.lock:
                job.status, job.message = "running", "Consultando Google Places e qualificando resultados."
            provider = self.provider_factory()
            stage = Stage()
            summary = prospect(city=job.request.location, segment=job.request.niche, limit=job.request.quantity,
                neighborhood=job.request.neighborhood, only_without_website=job.request.onlyWithoutWebsite,
                min_score=job.request.minScore, max_candidates_scanned=MAX_CANDIDATES_SCANNED,
                provider=Tracked(), repository=stage, cancel_event=Stop(), stream_results=True)
            with self.lock:
                job.status = "cancelled" if job.cancel.is_set() else "failed" if monotonic() >= job.deadline or summary.errors or summary.persistence_errors or summary.stop_code == ProspectingStopReason.PROVIDER_ERROR else "completed"
                if job.status == "failed":
                    job.error = "A pesquisa atingiu o tempo limite ou ocorreu uma falha no Google Places. Resultados parciais preservados."
                job.message = "Pesquisa cancelada; resultados parciais preservados." if job.status == "cancelled" else summary.stop_reason or STOP_MESSAGES.get(summary.stop_code) or ("Pesquisa concluída." if job.status == "completed" else "Pesquisa interrompida.")
        except Exception:
            with self.lock:
                job.status = "cancelled" if job.cancel.is_set() else "failed"
                job.error = None if job.cancel.is_set() else "Não foi possível pesquisar. Verifique a configuração Google Places, conexão e quota no backend."
                job.message = "Resultados parciais preservados."
        finally:
            if stage is not None:
                stage.connection.close()
            with self.lock:
                if provider is not None:
                    job.requests, job.pages = provider.request_count, getattr(provider,"pages_fetched",0)
                job.finished = monotonic()
