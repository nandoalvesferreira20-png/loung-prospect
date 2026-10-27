"""Synthetic adapter/CRM regression. No PostgreSQL instance or migrations."""
from contextlib import contextmanager
from types import SimpleNamespace
import pytest
from fastapi import HTTPException
from backend.authorization import Identity, identity
from backend.persistence.postgres import Connection, TABLES
from backend.persistence.session_queries import STATEMENTS
from backend.persistence.timing import current, measure
from backend.crm.service import CrmService
from backend.prospecting.storage import SelectionStore
from backend.tests.test_api import database


class Raw:
    def __init__(self, member=True):
        self.calls=[]
        self.member=member
        self.closed=False

    def execute(self, sql, params):
        self.calls.append((sql,params))
        if sql==STATEMENTS['session_membership_recheck']:
            return SimpleNamespace(fetchone=lambda: {'role':'owner'} if self.member else None)
        assert sql==STATEMENTS['schema_metadata']
        assert params==(sorted(TABLES),)
        return [{'table_name':table,'column_name':name} for table in sorted(TABLES-{'template_drafts'}) for name in ('id','organization_id')]

    def close(self):self.closed=True


def test_metadata_single_roundtrip_preserves_order_and_missing_tables():
    raw=Raw()
    token=identity.set(Identity('synthetic-user','synthetic-org','owner'))
    try:
        connection=Connection(SimpleNamespace(open=lambda *a:raw),'ro')
        assert len(raw.calls)==2  # Membership still checked, then one metadata query.
        assert connection.columns['leads']==['id','organization_id']
        assert connection.columns['template_drafts']==[]
        assert connection.execute('PRAGMA table_info(leads)').fetchall()==[(0,'id'),(1,'organization_id')]
    finally:identity.reset(token)


def test_revoked_membership_fails_before_metadata():
    raw=Raw(False)
    token=identity.set(Identity('synthetic-user','synthetic-org','owner'))
    try:
        with pytest.raises(HTTPException) as error:Connection(SimpleNamespace(open=lambda *a:raw),'ro')
        assert error.value.status_code==403 and raw.closed and len(raw.calls)==1
    finally:identity.reset(token)


def test_commercial_counts_match_followups_with_one_snapshot(database):
    service=CrmService(SelectionStore(database,False))
    expected=service.followups(limit=1)
    original=service.reader.connect
    connections=[]
    @contextmanager
    def counted():
        connections.append(1)
        with original() as connection:yield connection
    service.reader.connect=counted
    before=database.read_bytes()
    result=service.metrics()
    assert len(connections)==1
    assert {key:result[key] for key in ('pending','overdue','invalidDates')}=={key:expected[key] for key in ('pending','overdue','invalidDates')}
    assert database.read_bytes()==before


def test_timings_are_request_local_and_reset_on_failure():
    values={}
    token=current.set(values)
    try:
        with pytest.raises(ValueError), measure('db_query'):raise ValueError('synthetic')
        assert values['db_query']>=0
    finally:current.reset(token)
    with measure('db_query'):pass
    assert current.get() is None
