"""Read-only target evidence; never imports source data or changes schema."""
import argparse
import hashlib
import json
from uuid import UUID
import psycopg
from psycopg import sql
from backend.scripts.migrate_sqlite import ORDER,migration_dsn,safe_failure


def inspect_target(dsn,organization,source_id):
    with psycopg.connect(dsn,connect_timeout=5,prepare_threshold=None) as c:
        c.read_only=True
        c.isolation_level=psycopg.IsolationLevel.REPEATABLE_READ
        result={'readOnly':c.execute('SHOW transaction_read_only').fetchone()[0]=='on'}
        # No role switching or claims impersonation: inspect the actual migration login.
        result['permissions']={}
        result['counts']={}
        for table in (*ORDER,'migration_map','audit_events'):
            name='public.'+table
            result['permissions'][table]={p:c.execute('SELECT has_table_privilege(current_user,%s,%s)',(name,p)).fetchone()[0] for p in ('SELECT','INSERT')}
            if result['permissions'][table]['SELECT']:
                result['counts'][table]=c.execute(sql.SQL('SELECT count(*) FROM public.{} WHERE organization_id=%s').format(sql.Identifier(table)),(organization,)).fetchone()[0]
        result['mappedForSource']=c.execute('SELECT table_name,count(*) FROM public.migration_map WHERE organization_id=%s AND source=%s GROUP BY table_name ORDER BY table_name',(organization,source_id)).fetchall()
        result['sequences']={t:c.execute("SELECT has_sequence_privilege(current_user,%s,'USAGE')",('public.'+t+'_id_seq',)).fetchone()[0] for t in ORDER[:4]}
        result['auditFunctions']=[]
        for name,definition,definer in c.execute("SELECT p.proname,pg_get_functiondef(p.oid),p.prosecdef FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname='public' AND p.proname IN ('stamp_actor','audit_change')"):
            result['auditFunctions'].append({'name':name,'sha256':hashlib.sha256(definition.encode()).hexdigest(),'securityDefiner':definer,'usesAuthUid':'auth.uid()' in definition})
        result['triggers']=c.execute("SELECT c.relname,t.tgname,t.tgenabled FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' AND NOT t.tgisinternal ORDER BY c.relname,t.tgname").fetchall()
        result['foreignKeys']=c.execute("SELECT c.relname,k.conname,k.convalidated FROM pg_constraint k JOIN pg_class c ON c.oid=k.conrelid JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' AND k.contype='f' ORDER BY c.relname,k.conname").fetchall()
        return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--organization',required=True)
    parser.add_argument('--source-id',required=True)
    parser.add_argument('--env-file')
    args=parser.parse_args()
    try:
        result=inspect_target(migration_dsn(args.env_file),str(UUID(args.organization)),args.source_id)
    except Exception as error:
        print(json.dumps({'failureDiagnostic':safe_failure(error,'read_only_target_inspection')}))
        raise SystemExit(1) from None
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
