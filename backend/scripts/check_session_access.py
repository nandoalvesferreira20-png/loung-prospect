"""Explicit read-only reproduction of the database portion of /v1/session.
Never accepts administrative login, prints bound values or changes grants/data.
--user-id is an existing Auth UUID, not a JWT or credential; omitted uses a random nonmember.
"""
import argparse
import json
import os
from pathlib import Path
from uuid import UUID,uuid4
from dotenv import dotenv_values
from psycopg.conninfo import conninfo_to_dict
from backend.authorization import identity,Identity
from backend.persistence.postgres import Database,PgReader
from backend.persistence.errors import DatabaseAccessError,permission_details
from backend.persistence.session_queries import PROFILE_SQL


def emit(stage,**values):print(json.dumps({'stage':stage,**values}))


def diagnose(dsn,user):
    try:parts=conninfo_to_dict(dsn)
    except Exception:emit('configuration',result='INVALID_DSN');return False
    if parts.get('user','').split('.')[0]!='loung_web':
        emit('configuration',result='REFUSED_NON_RESTRICTED_LOGIN');return False
    db=Database(dsn)
    try:
        rows=db.memberships(user)
        emit('session_memberships',result='ok',authorized=bool(rows))
        if rows:
            row=rows[0];token=identity.set(Identity(user,row['organization_id'],row['role']))
            try:
                with PgReader(db).connect() as (c,_):c.execute(PROFILE_SQL,(user,)).fetchone()
                emit('session_profile',result='ok')
            finally:identity.reset(token)
        # A separate probe, after the actual session path: missing schema USAGE
        # can break this direct call even if pre-resolved policy calls succeeded.
        c=db.open(Identity(user))
        try:
            c.execute('SELECT auth.uid()')
            emit('auth_uid_probe',result='ok')
        except Exception as error:
            state=getattr(error,'sqlstate',None)
            emit('auth_uid_probe',result='failed',sqlstate=state,**permission_details(error))
            return False
        finally:c.close()
        return bool(rows)
    except DatabaseAccessError as error:
        emit(error.stage,result=error.code,statement_id=error.statement_id,sqlstate=error.sqlstate,**error.permission)
        return False
    except Exception as error:
        emit('session_probe',result='FAILED',error_type=type(error).__name__)
        return False


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--env-file',required=True,type=Path);p.add_argument('--user-id',type=UUID)
    a=p.parse_args()
    if not a.env_file.is_file():p.error('Arquivo de ambiente não encontrado.')
    values={**dotenv_values(a.env_file),**os.environ}
    if not diagnose(values.get('LOUNG_POSTGRES_DSN',''),str(a.user_id or uuid4())):raise SystemExit(1)
if __name__=='__main__':main()
