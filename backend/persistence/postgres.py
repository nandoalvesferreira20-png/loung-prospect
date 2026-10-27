"""PostgreSQL adapter for the existing service SQL dialect, never a SQLite fallback.

Only fixed server SQL is accepted. RLS is enforced with a non-bypass runtime role.
Each connection rechecks membership; writes serialize per organization in PostgreSQL.
"""
from contextlib import contextmanager, closing
from threading import RLock
import json
import re
import psycopg
from psycopg.rows import dict_row
from fastapi import HTTPException
from backend.authorization import identity, Identity
from backend.repository import ReadRepository, DatabaseUnavailable
from backend.prospecting.storage import SelectionStore
from backend.persistence.errors import DatabaseAccessError
from backend.persistence.session_queries import MEMBERSHIPS_SQL, PROFILE_SQL, STATEMENTS
from backend.persistence.timing import measure, timed

TABLES = {'leads','lead_interactions','outreach','outreach_revisions','lead_contact_preferences','template_drafts'}

# Same four exact identities as LeadRepository.find_existing, under current RLS.
EXISTING_RESULTS_SQL = '''
WITH candidates AS (
    SELECT * FROM jsonb_to_recordset(?::jsonb) AS c(
        ordinal integer, provider text, provider_place_id text,
        google_maps text, empresa text, endereco text, telefone text)
)
SELECT c.ordinal, EXISTS (
    SELECT 1 FROM leads l WHERE
        (l.provider=c.provider AND l.provider_place_id=c.provider_place_id)
        OR l.google_maps=c.google_maps
        OR (l.empresa=c.empresa AND l.endereco=c.endereco)
        OR (l.empresa=c.empresa AND l.telefone=c.telefone)
) AS saved FROM candidates c ORDER BY c.ordinal
'''

class Row(dict):
    def __getitem__(self,key):
        return list(self.values())[key] if isinstance(key,int) else super().__getitem__(key)
    def __iter__(self):
        # sqlite Row iteration yields values, dict(row) still uses mapping keys.
        return iter(self.values())

class Cursor:
    def __init__(self, rows=(), lastrowid=None):
        self.rows=list(rows); self.lastrowid=lastrowid
    def fetchone(self): return self.rows.pop(0) if self.rows else None
    def fetchall(self): rows,self.rows=self.rows,[]; return rows
    def __iter__(self): return iter(self.rows)

class Connection:
    def __init__(self, database, mode):
        who=identity.get()
        if who is None or not who.organization_id:
            raise HTTPException(403,'Organização não autorizada.')
        self.mode=mode
        self.raw=database.open(who,mode)
        statement_id=None
        try:
            if mode!='ro':
                self.raw.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))',(who.organization_id,))
            statement_id='session_membership_recheck'
            member=self.raw.execute(STATEMENTS[statement_id],(who.organization_id,who.user_id)).fetchone()
            if not member: raise HTTPException(403,'Acesso à organização revogado.')
            self.columns={table:[] for table in TABLES}
            statement_id='schema_metadata'
            with measure('db_metadata'):
                for row in self.raw.execute(STATEMENTS[statement_id],(sorted(TABLES),)):
                    self.columns[row['table_name']].append(row['column_name'])
        except psycopg.Error as error:
            self.raw.close()
            raise DatabaseAccessError('database_context',error,statement_id) from None
        except Exception:
            self.raw.close(); raise

    @timed('db_query')
    def execute(self, query, params=()):
        if self.mode=='ro' and re.match(r'\s*(INSERT|UPDATE|DELETE)',query,re.I):
            raise DatabaseUnavailable('Conexão somente leitura.')
        if query.startswith('PRAGMA table_info('):
            table=query.split('(',1)[1].rstrip(')')
            return Cursor([(i,n) for i,n in enumerate(self.columns.get(table,[]))])
        if query in ('BEGIN','BEGIN IMMEDIATE'): return Cursor()
        sql=query.replace('?', '%s').replace('CAST(qualification_score AS REAL)','CAST(qualification_score AS DOUBLE PRECISION)')
        # PostgreSQL concatenation needs explicit casts for legacy synthetic event IDs.
        sql=re.sub(r"('(?:activity-|draft-|revision-)'\s*\|\|)id",r'\1id::text',sql)
        sql=re.sub(r'(julianday\([^)]*\) DESC)',r'\1 NULLS LAST',sql)
        insert=re.match(r'INSERT INTO (\w+)',sql,re.I)
        returning=bool(insert and insert[1] in ('leads','lead_interactions','outreach','outreach_revisions'))
        if returning: sql+=' RETURNING id'
        try:
            cur=self.raw.execute(sql,params)
            rows=[Row(r) for r in cur.fetchall()] if cur.description else []
            return Cursor(rows,rows[0]['id'] if returning else None)
        except psycopg.Error as error:
            raise DatabaseAccessError('database_query',error,'session_profile' if query==PROFILE_SQL else None) from None

    def __enter__(self): return self
    def __exit__(self,kind,error,tb):
        try:
            if kind: self.raw.rollback()
            else: self.raw.commit()
        except psycopg.Error:
            self.raw.close()
            if kind is None: raise DatabaseUnavailable('Transação PostgreSQL indisponível.') from None
    def close(self):
        if self.raw.closed:return
        try: self.raw.rollback()
        except psycopg.Error: raise DatabaseUnavailable('Conexão PostgreSQL indisponível.') from None
        finally: self.raw.close()

class Database:
    def __init__(self,dsn): self.dsn=dsn
    @timed('db_open')
    def open(self,who,mode="ro"):
        c = None
        stage = 'database_connect'
        try:
            with measure('db_connect'):
                c=psycopg.connect(self.dsn,connect_timeout=5,row_factory=dict_row,prepare_threshold=None)
            if mode=='ro':
                c.isolation_level=psycopg.IsolationLevel.REPEATABLE_READ
                c.read_only=True
            stage = 'runtime_role'
            c.execute(STATEMENTS['set_runtime_role'])
            stage = 'transaction_identity'
            c.execute(STATEMENTS['set_transaction_identity'],
                (json.dumps({'sub':who.user_id,'role':'authenticated'}),who.organization_id))
            return c
        except psycopg.Error as error:
            if c is not None:
                c.close()
            raise DatabaseAccessError(stage,error,{'runtime_role':'set_runtime_role','transaction_identity':'set_transaction_identity'}.get(stage)) from None
    def memberships(self,user_id):
        c=self.open(Identity(user_id))
        query_failed=False
        try:
            return c.execute(MEMBERSHIPS_SQL,(user_id,)).fetchall()
        except psycopg.Error as error:
            query_failed=True
            raise DatabaseAccessError('membership_query',error,'session_memberships') from None
        finally:
            try: c.rollback()
            except psycopg.Error:
                if not query_failed: raise DatabaseUnavailable('Conexão PostgreSQL indisponível.') from None
            finally: c.close()
    def connection(self,mode='ro'):
        try: return Connection(self,mode)
        except psycopg.Error as error: raise DatabaseAccessError('database_context',error) from None

class PgReader(ReadRepository):
    def __init__(self,database): self.database=database
    @contextmanager
    def connect(self):
        c=self.database.connection()
        try: yield c,set(c.columns['leads'])
        except BaseException:
            try:c.close()
            except DatabaseUnavailable:pass # Preserve the original query's SQLSTATE.
            raise
        else:c.close()

class PgStore(SelectionStore):
    def __init__(self,database,enabled):
        self.database=database; self.enabled=enabled; self.lock=RLock(); self.backed_up=True
        self.path=None
    def connect(self,mode='ro'): return self.database.connection(mode)
    def existing(self,rows):
        # Keep the authorized preflight even for start([]). No global cache and
        # no bypass role: database.connection rechecks membership for this read.
        with closing(self.connect()) as c:
            if not rows:return []
            fields=('provider','provider_place_id','google_maps','empresa','endereco','telefone')
            candidates=[{'ordinal':i,**{key:row.get(key) if isinstance(row.get(key),str) and row[key].strip() else None
                                      for key in fields}} for i,row in enumerate(rows)]
            return [r['saved'] for r in c.execute(EXISTING_RESULTS_SQL,(json.dumps(candidates),))]
    def _backup(self):
        # PostgreSQL backups are managed operationally, not via SQLite backup API.
        raise RuntimeError('SQLite backup is unavailable for PostgreSQL')

class PgCrmMixin:
    def activities(self,lead_id,offset=0,limit=20):
        data=super().activities(lead_id,offset,limit)
        with self.reader.connect() as (c,_):
            events=c.execute('SELECT a.*,p.display_name FROM audit_events a LEFT JOIN profiles p ON p.id=a.actor_id WHERE a.lead_id=? ORDER BY a.at DESC,a.id DESC',(lead_id,)).fetchall()
            actors={}
            for event in events:
                new=event['new_value'] or {}
                table=event['action'].split('.')[0]
                if event['action']=='leads.insert':
                    actors.setdefault('created',event['display_name'] or 'Importação legada')
                prefix={'lead_interactions':'activity-','outreach':'draft-','outreach_revisions':'revision-'}.get(table)
                if prefix: actors.setdefault(prefix+str(new.get('id')),event['display_name'] or 'Importação legada')
            for item in data['items']: item['actorName']=actors.get(item['id'],'Importação legada / autoria desconhecida')
        return data
