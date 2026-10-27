"""Explicit, read-only access diagnostics. Never prints credentials or SQL errors.
Use --env-file .env --database for the intended configured PostgreSQL only.
"""
import argparse
import json
import os
from pathlib import Path
from uuid import uuid4
from dotenv import dotenv_values
from backend.persistence.errors import database_error_code
import psycopg
from psycopg.conninfo import conninfo_to_dict


def emit(stage, **values):
    print(json.dumps({'stage':stage,**values}))



def diagnose(values, database=False):
    required=('SUPABASE_URL','LOUNG_POSTGRES_DSN')
    configured=all(bool(values.get(k)) for k in required)
    emit('configuration',configured=configured,**{k:bool(values.get(k)) for k in required})
    if not configured:return False
    if not database:return True
    dsn=values.get('LOUNG_POSTGRES_DSN','')
    try:parts=conninfo_to_dict(dsn)
    except Exception:
        emit('database_configuration',result='DB_DSN_INVALID');return False
    host=parts.get('host','');user=parts.get('user','');base_user=user.split('.')[0]
    pooler=host.endswith('.pooler.supabase.com')
    mode='shared_pooler_session' if pooler and parts.get('port','5432')=='5432' else 'shared_pooler_transaction' if pooler else 'direct_or_other'
    emit('database_configuration',mode=mode,restricted_login=base_user=='loung_web',pooler_username_has_project_suffix='.' in user if pooler else None,tls_required=parts.get('sslmode') in ('require','verify-ca','verify-full'))
    if base_user!='loung_web':
        emit('database_connect',result='REFUSED_NON_RESTRICTED_LOGIN');return False
    c=None;stage='database_connect'
    try:
        c=psycopg.connect(dsn,connect_timeout=5,prepare_threshold=None)
        c.read_only=True
        emit(stage,result='ok')
        stage='runtime_role'
        c.execute('SET LOCAL ROLE loung_api')
        restricted=c.execute("SELECT current_user='loung_api' AND NOT (rolsuper OR rolbypassrls) FROM pg_roles WHERE rolname=current_user").fetchone()[0]
        emit(stage,result='ok' if restricted else 'failed',restricted=restricted)
        if not restricted:return False
        stage='transaction_identity'
        synthetic=str(uuid4())
        c.execute("SELECT set_config('request.jwt.claims',%s,true),set_config('app.organization_id','',true)",(json.dumps({'sub':synthetic,'role':'authenticated'}),))
        matches=c.execute('SELECT auth.uid()=%s::uuid',(synthetic,)).fetchone()[0]
        emit(stage,result='ok' if matches else 'failed',auth_uid_matches=matches)
        if not matches:return False
        stage='membership_rls'
        count=c.execute('SELECT count(*) FROM public.organization_members m JOIN public.organizations o ON o.id=m.organization_id WHERE m.user_id=auth.uid()').fetchone()[0]
        emit(stage,result='ok',unknown_identity_has_no_access=count==0)
        return count==0
    except Exception as error:
        emit(stage,result=database_error_code(error),error_type=type(error).__name__)
        return False
    finally:
        if c is not None:c.close() # Roll back read-only transaction, including SET LOCAL.


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--env-file',type=Path)
    p.add_argument('--database',action='store_true')
    args=p.parse_args()
    if args.env_file and not args.env_file.is_file():p.error('Arquivo de ambiente não encontrado.')
    # Explicit file, never automatic loading of desktop configuration. Process wins.
    values={**(dotenv_values(args.env_file) if args.env_file else {}),**os.environ}
    if not diagnose(values,args.database):raise SystemExit(1)
if __name__=='__main__':main()
