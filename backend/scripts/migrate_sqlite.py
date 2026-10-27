"""Read-only source, verified backup, explicit opt-in target transaction.
Usage: python -m backend.scripts.migrate_sqlite --sqlite PATH --organization UUID --source-id stable-name
No network is accessed without --apply --confirm UUID. Target DSN only from environment.
"""
import argparse
from contextlib import closing
from datetime import datetime,timezone
import hashlib
import json
import os
import re
from pathlib import Path
import sqlite3
from uuid import UUID,uuid4

ORDER=('leads','lead_interactions','outreach','outreach_revisions','lead_contact_preferences','template_drafts')
REQUIRED={'leads':('empresa','created_at','updated_at'), 'lead_interactions':('lead_id','tipo','created_at'), 'outreach':('lead_id','mensagem','status','criado_em','atualizado_em'), 'outreach_revisions':('lead_id','outreach_id','mensagem','status','recorded_at'), 'lead_contact_preferences':('lead_id','contact_type','updated_at'), 'template_drafts':('lead_id','message','channel','objective','tone','updated_at')}
DATES={'created_at','updated_at','criado_em','atualizado_em','recorded_at','analyzed_at','ultimo_contato','proximo_contato','consent_at'}


def inspect_source(path,backup_dir):
    path=Path(path).resolve(strict=True)
    backup_dir=Path(backup_dir);backup_dir.mkdir(parents=True,exist_ok=True)
    backup=backup_dir/f'{path.stem}-phase31-{uuid4().hex}.db'
    if backup.resolve()==path: raise ValueError('Backup deve ter caminho separado')
    with closing(sqlite3.connect(path.as_uri()+'?mode=ro',uri=True)) as source:
        source.execute('PRAGMA query_only=ON')
        with closing(sqlite3.connect(backup)) as target:
            source.backup(target)
            if target.execute('PRAGMA integrity_check').fetchone()[0]!='ok': raise ValueError('Backup inválido')
    # Validate/migrate the consistent backup; source is never reopened writable.
    with closing(sqlite3.connect(backup.resolve().as_uri()+'?mode=ro',uri=True)) as c:
        c.row_factory=sqlite3.Row
        names={r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        unknown=names-set(ORDER)-{'sqlite_sequence'}
        if unknown: raise ValueError('Tabelas não mapeadas; revisão necessária')
        data={t:[dict(r) for r in c.execute('SELECT * FROM "'+t+'"')] if t in names else [] for t in ORDER}
    report={'backup':str(backup),'backupSha256':hashlib.sha256(backup.read_bytes()).hexdigest(),'integrity':'ok','tables':{},'dateWarnings':0,'duplicateGroups':0,'orphans':0,'applied':False}
    rejected=[];leads={r.get('id') for r in data['leads']};outreach={(r.get('id'),r.get('lead_id')) for r in data['outreach']}
    keys=set()
    for table,rows in data.items():
        invalid=0
        for row in rows:
            errors=[]
            primary = 'lead_id' if table in ('lead_contact_preferences','template_drafts') else 'id'
            if row.get(primary) is None or any(row.get(k) is None for k in REQUIRED[table]):errors.append('required')
            if table=='leads' and (not isinstance(row.get('empresa'),str) or not row['empresa'].strip()):errors.append('company')
            if table!='leads' and row.get('lead_id') not in leads:errors.append('orphan');report['orphans']+=1
            if table=='outreach_revisions' and (row.get('outreach_id'),row.get('lead_id')) not in outreach:errors.append('orphan_revision')
            if table=='outreach' and row.get('status') not in ('GERADA','EDITADA','APROVADA','ENVIADA','RESPONDEU','CANCELADA'):errors.append('status')
            if table=='lead_contact_preferences' and row.get('contact_type') not in ('recepcao_equipe','contato_direto','indefinido'):errors.append('contact_type')
            for k in ('id','lead_id','outreach_id','qualification_score','quantidade_avaliacoes','do_not_contact'):
                if row.get(k) is not None:
                    try:
                        value=int(row[k])
                        if str(value)!=str(row[k]):raise ValueError()
                        if k in ('id','lead_id','outreach_id') and not 0<value<2**53:raise ValueError()
                        row[k]=value
                    except (TypeError,ValueError):errors.append('integer')
            for k in DATES:
                if row.get(k):
                    try:
                        if datetime.fromisoformat(row[k]).utcoffset() is None:report['dateWarnings']+=1
                    except (TypeError,ValueError):report['dateWarnings']+=1
            if table=='leads':
                # Count repeated identities without including PII in the report.
                for fields in (('provider','provider_place_id'),('google_maps',),('empresa','endereco'),('empresa','telefone')):
                    if all(isinstance(row.get(k),str) and row[k].strip() for k in fields):
                        key=(fields,tuple(row[k] for k in fields))
                        if key in keys:report['duplicateGroups']+=1
                        keys.add(key)
            if errors:invalid+=1;rejected.append((table,row.get('id',row.get('lead_id')),sorted(set(errors))))
        report['tables'][table]={'source':len(rows),'migrated':0,'ignored':0,'rejected':invalid}
    report['rejectedCount']=len(rejected)
    report['rejectionReasons']={reason:sum(reason in item[2] for item in rejected) for reason in sorted({r for item in rejected for r in item[2]})}
    return data,report


class MissingMigrationConfiguration(ValueError):
    pass


def safe_failure(error, phase):
    """Never serialize PostgreSQL messages/detail/context: they may contain row values."""
    import psycopg
    def identifier(value):
        return value if isinstance(value,str) and re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]{0,62}',value) else None
    diag=getattr(error,'diag',None)
    state=getattr(error,'sqlstate',None)
    return {'phase':phase,
            'type':type(error).__name__ if isinstance(error,(psycopg.Error,MissingMigrationConfiguration)) else 'ConfigurationOrMappingError',
            'sqlstate':state if isinstance(state,str) and re.fullmatch(r'[0-9A-Z]{5}',state) else None,
            'constraint':identifier(getattr(diag,'constraint_name',None)),
            'table':identifier(getattr(diag,'table_name',None)),
            'schema':identifier(getattr(diag,'schema_name',None))}


def migration_dsn(env_file=None):
    dsn=os.environ.get('LOUNG_MIGRATION_DSN')
    if not dsn and env_file:
        from dotenv import dotenv_values
        dsn=dotenv_values(env_file,interpolate=False).get('LOUNG_MIGRATION_DSN')
    if not dsn:
        raise MissingMigrationConfiguration('LOUNG_MIGRATION_DSN ausente; configure o ambiente ou use --env-file com essa variável')
    return dsn


def apply(data,report,dsn,organization,source_id):
    for counts in report['tables'].values():
        counts['migrated']=0;counts['ignored']=0
    report['phase']='validation'
    report['applied']=False
    report.pop('failureDiagnostic',None)
    try:
        return _apply(data,report,dsn,organization,source_id)
    except Exception as error:
        report['failureDiagnostic']=safe_failure(error,report['phase'])
        # Counters describe committed rows only, never attempted writes.
        for counts in report['tables'].values():
            counts['migrated']=0;counts['ignored']=0
        raise


def _apply(data,report,dsn,organization,source_id):
    if report['rejectedCount']:raise ValueError('Registros inválidos; nenhuma escrita permitida')
    import psycopg
    from psycopg import sql
    from psycopg.rows import dict_row
    report['phase']='connect'
    with psycopg.connect(dsn,connect_timeout=5,row_factory=dict_row,prepare_threshold=None) as c:
        report['phase']='lock'
        c.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))',(organization,))
        report['phase']='organization'
        if not c.execute('SELECT id FROM organizations WHERE id=%s',(organization,)).fetchone():raise ValueError('Organização inexistente')
        report['phase']='identity'
        c.execute("SELECT set_config('app.organization_id',%s,true),set_config('request.jwt.claims','{}',true)",(organization,))
        mapping={}
        for table in ORDER:
            report['phase']=table+'.columns'
            cols={r['column_name'] for r in c.execute("SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name=%s",(table,))}
            for original in data[table]:
                if set(original)-cols:
                    raise ValueError('Colunas de origem sem mapeamento; revisão necessária')
                old=original.get('id',original.get('lead_id'))
                report['phase']=table+'.mapping_lookup'
                previous=c.execute('SELECT new_id FROM migration_map WHERE organization_id=%s AND source=%s AND table_name=%s AND legacy_id=%s',(organization,source_id,table,old)).fetchone()
                if previous:
                    mapping[(table,old)]=previous['new_id'];report['tables'][table]['ignored']+=1;continue
                row={k:v for k,v in original.items() if k in cols and k not in ('id','organization_id','created_by','updated_by')}
                row['organization_id']=organization
                if table!='leads':row['lead_id']=mapping[('leads',original['lead_id'])]
                if table=='outreach_revisions':row['outreach_id']=mapping[('outreach',original['outreach_id'])]
                report['phase']=table+'.deduplicate'
                existing=None
                if table=='leads':
                    row['status']=row.get('status') or 'Novo'
                    for fields in (('provider','provider_place_id'),('google_maps',),('empresa','endereco'),('empresa','telefone')):
                        if all(isinstance(row.get(k),str) and row[k].strip() for k in fields):
                            query=sql.SQL('SELECT id FROM leads WHERE organization_id=%s AND ')+sql.SQL(' AND ').join(sql.SQL('{}=%s').format(sql.Identifier(k)) for k in fields)+sql.SQL(' LIMIT 1')
                            existing=c.execute(query,[organization,*[row[k] for k in fields]]).fetchone()
                            if existing:break
                natural=table in ('lead_contact_preferences','template_drafts')
                if natural:existing=c.execute(sql.SQL('SELECT lead_id AS id FROM {} WHERE organization_id=%s AND lead_id=%s').format(sql.Identifier(table)),(organization,row['lead_id'])).fetchone()
                if existing:new=existing['id'];report['tables'][table]['ignored']+=1
                else:
                    query=sql.SQL('INSERT INTO {} ({}) VALUES ({}) RETURNING {}').format(sql.Identifier(table),sql.SQL(',').join(map(sql.Identifier,row)),sql.SQL(',').join(sql.Placeholder() for _ in row),sql.Identifier('lead_id' if natural else 'id'))
                    report['phase']=table+'.insert'
                    new=c.execute(query,list(row.values())).fetchone()['lead_id' if natural else 'id'];report['tables'][table]['migrated']+=1
                mapping[(table,old)]=new
                report['phase']=table+'.mapping_insert'
                c.execute('INSERT INTO migration_map(organization_id,source,table_name,legacy_id,new_id) VALUES(%s,%s,%s,%s,%s)',(organization,source_id,table,old,new))
        report['phase']='commit'
    report['phase']='committed'
    report['applied']=True
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sqlite',required=True);parser.add_argument('--organization',required=True);parser.add_argument('--source-id',required=True)
    parser.add_argument('--backup-dir',default='data/backups');parser.add_argument('--report',default='backend/migration-report.json');parser.add_argument('--dry-run',action='store_true');parser.add_argument('--apply',action='store_true');parser.add_argument('--confirm')
    parser.add_argument('--env-file',help='Arquivo explicito; le somente LOUNG_MIGRATION_DSN, sem alterar o ambiente')
    args=parser.parse_args();org=str(UUID(args.organization))
    if Path(args.report).suffix.lower()!='.json' or Path(args.report).resolve()==Path(args.sqlite).resolve():
        parser.error('--report deve ser um JSON separado da origem SQLite')
    if args.apply and (args.dry_run or args.confirm!=org):parser.error('--apply exige --confirm UUID igual à organização e sem --dry-run')
    data,report=inspect_source(args.sqlite,args.backup_dir)
    try:
        if args.apply:
            report['phase']='configuration'
            apply(data,report,migration_dsn(args.env_file),org,args.source_id)
    except Exception as error:
        report.setdefault('failureDiagnostic',safe_failure(error,report.get('phase','configuration')))
        report['failure']='Transação não confirmada. Revise configuração/constraints sem divulgar credenciais.'
        Path(args.report).write_text(json.dumps(report,indent=2),encoding='utf8')
        raise SystemExit(report['failure']+' '+json.dumps(report['failureDiagnostic'])) from None
    Path(args.report).write_text(json.dumps(report,indent=2),encoding='utf8')
    print(json.dumps(report,indent=2))
    if report['rejectedCount']:raise SystemExit(2)
if __name__=='__main__':main()
