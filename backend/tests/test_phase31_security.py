"""Security and source migration tests; all identities are synthetic."""
from datetime import datetime,timezone,timedelta
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4
import hashlib
import sqlite3
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi import HTTPException
from fastapi.testclient import TestClient
from backend.authorization import TokenVerifier
from backend.config import Settings
from backend.main import create_app
from backend.scripts.migrate_sqlite import inspect_source,apply
from core.database.schema import initialize_database

@pytest.fixture
def signer():
    key=ec.generate_private_key(ec.SECP256R1())
    v=TokenVerifier('https://synthetic.supabase.invalid')
    v.keys=SimpleNamespace(get_signing_key_from_jwt=lambda token:SimpleNamespace(key=key.public_key()))
    claims={'sub':str(uuid4()),'role':'authenticated','iss':v.issuer,'aud':'authenticated','iat':datetime.now(timezone.utc),'exp':datetime.now(timezone.utc)+timedelta(minutes=5)}
    return key,v,claims


def test_valid_token(signer):
    key,v,claims=signer
    assert v.verify('Bearer '+jwt.encode(claims,key,algorithm='ES256'))==claims['sub']

@pytest.mark.parametrize('change',[{'exp':1},{'aud':'other'},{'iss':'https://attacker.invalid'},{'role':'service_role'},{'sub':'not-uuid'},{'exp':None}])
def test_invalid_claims(signer,change):
    key,v,claims=signer;claims.update(change)
    with pytest.raises(HTTPException) as e:v.verify('Bearer '+jwt.encode(claims,key,algorithm='ES256'))
    assert e.value.status_code==401


def test_signature_algorithm_and_missing(signer):
    key,v,claims=signer
    wrong=ec.generate_private_key(ec.SECP256R1())
    for token in [None,'Bearer garbage','Bearer '+jwt.encode(claims,wrong,algorithm='ES256'),'Bearer '+jwt.encode(claims,'synthetic-key-32-characters-long!!',algorithm='HS256')]:
        with pytest.raises(HTTPException) as e:v.verify(token)
        assert e.value.status_code==401


def configured(tmp_path):return create_app(Settings(tmp_path/'unused.db',True,'postgres','postgresql://localhost:1/loung_test','https://synthetic.supabase.invalid'))

def test_protected_endpoints(tmp_path):
    app=configured(tmp_path)
    with TestClient(app) as c:
        for path in ['/v1/leads','/v1/pipeline','/v1/session','/v1/sdr/leads/1','/v1/followups']:
            assert c.get(path).status_code==401
        assert c.get('/health').status_code==200


def test_nonmember_and_connection_failure(tmp_path,monkeypatch):
    app=configured(tmp_path)
    app.state.verifier=SimpleNamespace(verify=lambda token:str(uuid4()))
    monkeypatch.setattr(app.state.database,'memberships',lambda user:[])
    with TestClient(app) as c:assert c.get('/v1/leads').status_code==403
    def unavailable(user):
        from backend.repository import DatabaseUnavailable
        raise DatabaseUnavailable()
    monkeypatch.setattr(app.state.database,'memberships',unavailable)
    with TestClient(app) as c:
        r=c.get('/v1/leads');assert r.status_code==503;assert 'postgresql://' not in r.text


def test_requested_org_requires_membership(tmp_path,monkeypatch):
    app=configured(tmp_path);user=str(uuid4());org=str(uuid4())
    app.state.verifier=SimpleNamespace(verify=lambda token:user)
    monkeypatch.setattr(app.state.database,'memberships',lambda user:[{'organization_id':org,'role':'member','name':'Synthetic'}])
    with TestClient(app) as c:assert c.get('/v1/leads',headers={'x-organization-id':str(uuid4())}).status_code==403


def source(tmp_path):
    p=tmp_path/'source.db';initialize_database(p)
    with sqlite3.connect(p) as c:
        c.execute("INSERT INTO leads(empresa,status,created_at,updated_at,provider,provider_place_id) VALUES('SYNTHETIC','Etapa própria','2026-01-01T00:00:00+00:00','2026-01-01T00:00:00+00:00','google','test-place')")
        c.execute("INSERT INTO lead_interactions(lead_id,tipo,created_at) VALUES(1,'Observação','2026-01-01T00:00:00+00:00')")
        c.execute("INSERT INTO outreach(lead_id,mensagem,status,criado_em,atualizado_em) VALUES(1,'Mensagem sintética','EDITADA','2026-01-01','2026-01-01')")
        c.execute("INSERT INTO outreach_revisions(lead_id,outreach_id,mensagem,status,recorded_at) VALUES(1,1,'Versão anterior','GERADA','2026-01-01')")
    return p


def test_backup_source_unchanged_and_history(tmp_path):
    p=source(tmp_path);before=hashlib.sha256(p.read_bytes()).hexdigest()
    data,report=inspect_source(p,tmp_path/'backups')
    assert report['integrity']=='ok' and report['rejectedCount']==0
    assert data['outreach_revisions'][0]['mensagem']=='Versão anterior'
    assert data['leads'][0]['status']=='Etapa própria'
    assert hashlib.sha256(p.read_bytes()).hexdigest()==before
    assert Path(report['backup']).exists() and report['applied'] is False


def test_invalid_records_prevent_all_writes(tmp_path):
    p=source(tmp_path)
    with sqlite3.connect(p) as c:
        c.execute("UPDATE leads SET qualification_score='invalid'")
        c.execute("INSERT INTO lead_interactions(lead_id,tipo,created_at) VALUES(999,'Outro','invalid-date')")
    data,report=inspect_source(p,tmp_path/'backups')
    assert report['rejectedCount']==2 and report['orphans']==1 and report['dateWarnings']>0
    with pytest.raises(ValueError):apply(data,report,'not-a-dsn',str(uuid4()),'test')
