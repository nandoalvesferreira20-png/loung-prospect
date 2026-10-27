import json
import pytest
from backend.scripts.migrate_sqlite import migration_dsn,safe_failure


def test_missing_configuration_is_explicit(monkeypatch):
    monkeypatch.delenv('LOUNG_MIGRATION_DSN',raising=False)
    with pytest.raises(ValueError,match='LOUNG_MIGRATION_DSN'):
        migration_dsn()


def test_explicit_env_file_no_interpolation_or_environment_mutation(tmp_path,monkeypatch):
    monkeypatch.delenv('LOUNG_MIGRATION_DSN',raising=False)
    p=tmp_path/'synthetic.env'
    p.write_text('LOUNG_MIGRATION_DSN=synthetic-${PASSWORD}\nOTHER_SECRET=private',encoding='utf8')
    assert migration_dsn(p)=='synthetic-${PASSWORD}'
    import os
    assert 'LOUNG_MIGRATION_DSN' not in os.environ
    monkeypatch.setenv('LOUNG_MIGRATION_DSN','process-value')
    assert migration_dsn(p)=='process-value'


def test_failure_never_serializes_message_or_parameters():
    import psycopg
    error=psycopg.OperationalError('password=private connection secret PII')
    result=safe_failure(error,'connect')
    assert result['type']=='OperationalError'
    assert 'private' not in json.dumps(result)
    assert 'PII' not in json.dumps(result)
