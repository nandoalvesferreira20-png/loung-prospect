"""Fixed disposable PostgreSQL only. Never reads environment DSNs or real data."""
import json
from types import SimpleNamespace
import psycopg
from psycopg.rows import dict_row
import pytest
from backend.persistence.postgres import PgStore
from backend.prospecting.storage import SelectionStore

DSN='postgresql://postgres@127.0.0.1:55432/postgres?sslmode=disable&max_protocol_version=3.0'


class Adapter:
    def __init__(self, raw):self.raw=raw;self.calls=[]
    def execute(self, sql, params=()):
        self.calls.append(sql)
        return self.raw.execute(sql.replace('?', '%s'),params)
    def close(self):self.raw.close()


@pytest.fixture
def connect():
    connections=[]
    def opened(org='org-a',user='user-a'):
        try:raw=psycopg.connect(DSN,connect_timeout=2,row_factory=dict_row,prepare_threshold=None)
        except psycopg.OperationalError:pytest.skip('Start web/scripts/prospecting-postgres.mjs')
        assert raw.execute('SELECT value FROM prospecting_test_marker').fetchone()['value']=='prospecting-isolated-memory'
        raw.rollback();raw.read_only=True
        raw.execute('SET LOCAL ROLE loung_api')
        raw.execute("SELECT set_config('app.organization_id',%s,true),set_config('request.jwt.claims',%s,true)",(org,json.dumps({'sub':user})))
        c=Adapter(raw);connections.append(c);return c
    yield opened
    for c in connections:c.close()


def store_for(connection):
    store=PgStore.__new__(PgStore)
    store.connect=lambda:connection
    return store


def test_twenty_new_results_use_one_query_instead_of_eighty(connect):
    rows=[dict(provider='google_places',provider_place_id=f'new-{i}',google_maps=f'new-map-{i}',
               empresa=f'Synthetic {i}',endereco=f'new-address-{i}',telefone=f'new-phone-{i}') for i in range(20)]
    c=connect()
    assert store_for(c).existing(rows)==[False]*20
    assert len(c.calls)==1
    # Reproduce the previous adapter path without sleeping or accessing a real DB.
    old=SelectionStore.__new__(SelectionStore)
    calls=[]
    class OldConnection:
        def execute(self,sql,params=()):
            calls.append(sql);return SimpleNamespace(fetchone=lambda:None)
        def close(self):pass
    old.connect=OldConnection
    assert old.existing(rows)==[False]*20
    assert sum(sql.startswith('SELECT') for sql in calls)==80


@pytest.mark.parametrize('row,expected',[
    ({'provider':'google_places','provider_place_id':'a'},True),
    ({'google_maps':'map-a'},True),
    ({'empresa':'Synthetic A','endereco':'address-a'},True),
    ({'empresa':'Synthetic A','telefone':'phone-a'},True),
    ({'provider_place_id':'a'},False),
    ({'empresa':'Synthetic A'},False),
    ({'google_maps':' '},False),
    ({'google_maps':42},False),
    ({'empresa':' Synthetic A ','telefone':'phone-a'},False),
    ({'provider':'google_places','provider_place_id':'b'},False),
])
def test_exact_identities_and_no_cross_organization_duplicates(connect,row,expected):
    assert store_for(connect()).existing([row])==[expected]


def test_batch_order_and_membership_isolation(connect):
    rows=[{'google_maps':'map-b'},{'google_maps':'map-a'},{}]
    assert store_for(connect()).existing(rows)==[False,True,False]
    assert store_for(connect('org-b','user-b')).existing(rows)==[True,False,False]
    assert store_for(connect('org-b','user-a')).existing(rows)==[False,False,False]


def test_empty_batch_keeps_authorized_connection_preflight(connect):
    c=connect()
    assert store_for(c).existing([])==[]
    assert c.raw.closed and not c.calls
