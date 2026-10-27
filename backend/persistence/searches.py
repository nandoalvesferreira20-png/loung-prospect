"""Durable search snapshots; one local worker, organization-scoped cache."""
import json
from contextlib import closing
from contextvars import copy_context
from backend.prospecting.jobs import JobManager,Job,JobError,TERMINAL,search_event
from backend.prospecting.models import SearchRequest
from backend.repository import DatabaseUnavailable
from backend.persistence.postgres import PgReader

class PgJobManager(JobManager):
    def checkpoint(self,job):
        payload={'query':job.request.model_dump(mode='json'),'status':job.status,'rows':job.rows,'scanned':job.scanned,'requests':job.requests,'pages':job.pages,'error':job.error,'message':job.message,'duplicates':job.duplicates,'failure_type':job.failure_type}
        with closing(self.store.connect('rw')) as c, c:
            c.execute('INSERT INTO prospecting_searches(id,payload) VALUES(?,?::jsonb) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload',(job.id,json.dumps(payload)))
    def start(self,request):
        with self.lock:
            self._purge()
            if any(j.status not in TERMINAL for j in self.jobs.values()):
                raise JobError('Já existe uma pesquisa em andamento.',429)
            if len(self.jobs)>=self.max_jobs:
                raise JobError('Limite de pesquisas recentes atingido.',429)
            self.store.existing([])
            job=Job(request)
            self.checkpoint(job)
            self.jobs[job.id]=job
            self.executor.submit(copy_context().run,self._run,job)
            return self.status(job.id)
    def _run(self,job):
        super()._run(job)
        try:
            with self.lock:self.checkpoint(job)
        except Exception:
            with self.lock:
                job.status='failed';job.failure_type='SEARCH_PERSISTENCE'
                job.error='Não foi possível persistir o histórico da pesquisa. Resultados temporários disponíveis.'
                search_event('search.persistence_failed',job)
    def get(self,job_id):
        try:return super().get(job_id)
        except JobError:
            reader=PgReader(self.store.database)
            with reader.connect() as (c,_):
                saved=c.execute('SELECT payload FROM prospecting_searches WHERE id=?',(job_id,)).fetchone()
            if not saved:raise JobError('Pesquisa não encontrada.',404)
            p=saved['payload'];job=Job(SearchRequest.model_validate(p['query']),id=job_id)
            for key in ('status','rows','scanned','requests','pages','error','message'):setattr(job,key,p[key])
            job.duplicates=p.get('duplicates',0);job.failure_type=p.get('failure_type')
            if job.status not in TERMINAL:job.status='failed';job.message='Execução interrompida por reinício. Inicie nova pesquisa.'
            return job
