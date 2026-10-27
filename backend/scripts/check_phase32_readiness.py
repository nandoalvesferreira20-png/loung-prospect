"""Catalog-only, read-only write-readiness review. Never changes grants or data."""
import argparse
import json
import os
from pathlib import Path
from dotenv import dotenv_values
import psycopg
from psycopg.conninfo import conninfo_to_dict

BUSINESS = ('leads', 'lead_interactions', 'outreach', 'outreach_revisions',
            'lead_contact_preferences', 'template_drafts', 'prospecting_searches',
            'organization_settings', 'commercial_stages')
PROTECTED = ('organizations', 'profiles', 'organization_members', 'audit_events')
APPEND_ONLY = {'lead_interactions', 'outreach_revisions'}
FUNCTIONS = ('team_roster', 'manage_member', 'guard_membership', 'audit_membership',
             'stamp_actor', 'audit_change')


def claims_stamp_installed(connection):
    """Only the exact reviewed invoker implementation removes the USAGE need."""
    migration = Path(__file__).resolve().parents[2] / 'supabase/migrations/202610220001_stamp_actor_from_verified_claims.sql'
    if not migration.is_file():
        return False
    expected = migration.read_text(encoding='utf-8-sig').split('$stamp_actor$')[1].strip()
    row = connection.execute("SELECT p.prosrc,p.prosecdef,p.proconfig,r.rolname FROM pg_proc p JOIN pg_roles r ON r.oid=p.proowner WHERE p.oid='public.stamp_actor()'::regprocedure").fetchone()
    return bool(row and row[0].replace('\r\n', '\n').strip() == expected.replace('\r\n', '\n')
                and not row[1] and 'search_path=""' in (row[2] or []) and row[3] == 'postgres')


def inspect(dsn):
    # Refuse an administrative login before opening any connection.
    if conninfo_to_dict(dsn).get('user', '').split('.')[0] != 'loung_web':
        raise ValueError('RESTRICTED_LOGIN_REQUIRED')
    findings = []

    def check(name, passed, **metadata):
        findings.append({'check': name, 'passed': bool(passed), **metadata})

    with psycopg.connect(dsn, connect_timeout=5, prepare_threshold=None) as c:
        c.read_only = True
        c.execute("SET LOCAL statement_timeout='8s'")
        login = c.execute("SELECT current_user LIKE 'loung_web%%', NOT (rolsuper OR rolbypassrls OR rolcreaterole OR rolcreatedb OR rolreplication), pg_has_role(current_user,'loung_api','MEMBER') FROM pg_roles WHERE rolname=current_user").fetchone()
        check('restricted_login', login and all(login))
        check('login_has_no_privileged_role_memberships', not c.execute("SELECT EXISTS(SELECT 1 FROM pg_roles r WHERE (rolsuper OR rolbypassrls OR rolcreaterole OR rolcreatedb OR rolreplication) AND pg_has_role(current_user,r.oid,'MEMBER'))").fetchone()[0])
        c.execute('SET LOCAL ROLE loung_api')
        check('effective_runtime_role', c.execute("SELECT current_user='loung_api'").fetchone()[0])
        check('no_privileged_role_memberships', not c.execute("SELECT EXISTS(SELECT 1 FROM pg_roles r WHERE (rolsuper OR rolbypassrls OR rolcreaterole OR rolcreatedb OR rolreplication) AND pg_has_role('loung_api',r.oid,'MEMBER'))").fetchone()[0])
        claims_stamp = claims_stamp_installed(c)
        check('stamp_identity_source', claims_stamp or c.execute("SELECT has_schema_privilege(current_user,'auth','USAGE')").fetchone()[0], claimsStampInstalled=claims_stamp)
        for schema in ('public', 'auth', 'extensions'):
            actual = c.execute('SELECT has_schema_privilege(current_user,%s,\'USAGE\')', (schema,)).fetchone()[0]
            check('schema_usage', actual or (schema == 'auth' and claims_stamp), schema=schema,
                  actual=actual, required=not (schema == 'auth' and claims_stamp))
        for table in BUSINESS + PROTECTED:
            oid = c.execute('SELECT to_regclass(%s)', ('public.' + table,)).fetchone()[0]
            check('table_present', oid is not None, table=table)
            if oid is None:
                continue
            flags = c.execute('SELECT relrowsecurity,relforcerowsecurity FROM pg_class WHERE oid=%s::regclass', (oid,)).fetchone()
            check('rls_enabled', flags[0], table=table)
            if table in BUSINESS or table == 'audit_events':
                check('rls_forced', flags[1], table=table)
            for privilege in ('SELECT', 'INSERT', 'UPDATE', 'DELETE', 'TRUNCATE'):
                actual = c.execute('SELECT has_table_privilege(current_user,%s,%s)', (oid, privilege)).fetchone()[0]
                expected = privilege == 'SELECT' or (table in BUSINESS and (privilege == 'INSERT' or (privilege == 'UPDATE' and table not in APPEND_ONLY)))
                check('table_privilege', actual == expected, table=table, privilege=privilege, expected=expected, actual=actual)
            if table in PROTECTED or table in APPEND_ONLY:
                for privilege in (('INSERT', 'UPDATE') if table in PROTECTED else ('UPDATE',)):
                    check('column_write_denied', not c.execute('SELECT has_any_column_privilege(current_user,%s,%s)', (oid, privilege)).fetchone()[0], table=table, privilege=privilege)
            if table in BUSINESS:
                policies = c.execute("SELECT polcmd FROM pg_policy WHERE polrelid=%s::regclass AND (0=ANY(polroles) OR (SELECT oid FROM pg_roles WHERE rolname='loung_api')=ANY(polroles))", (oid,)).fetchall()
                expected_policies = {'r', 'a'} if table in APPEND_ONLY else {'r', 'a', 'w'}
                check('write_policies_present', expected_policies <= {r[0] for r in policies}, table=table)
                triggers = c.execute("SELECT tgname,tgenabled FROM pg_trigger WHERE tgrelid=%s::regclass AND NOT tgisinternal", (oid,)).fetchall()
                enabled = {name for name, state in triggers if state in ('O', 'A')}
                check('authorship_and_audit_triggers', {'stamp', 'audit'} <= enabled, table=table)
        for sequence in ('leads_id_seq', 'lead_interactions_id_seq', 'outreach_id_seq', 'outreach_revisions_id_seq'):
            oid = c.execute('SELECT to_regclass(%s)', ('public.' + sequence,)).fetchone()[0]
            check('sequence_usage', oid is not None and c.execute('SELECT has_sequence_privilege(current_user,%s,\'USAGE\')', (oid,)).fetchone()[0], sequence=sequence)
        functions = c.execute("SELECT p.oid,p.proname,p.prosecdef,p.proconfig,r.rolname FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace JOIN pg_roles r ON r.oid=p.proowner WHERE n.nspname='public' AND p.proname=ANY(%s)", (list(FUNCTIONS),)).fetchall()
        for name in FUNCTIONS:
            matches = [row for row in functions if row[1] == name]
            check('function_present_once', len(matches) == 1, function=name)
            for oid, _, definer, config, owner in matches:
                check('function_search_path', 'search_path=""' in (config or []), function=name)
                check('function_owner', owner == 'postgres', function=name)
                check('function_execution_mode', definer == (name != 'stamp_actor'), function=name)
                expected = name in ('team_roster', 'manage_member')
                check('runtime_function_execute', c.execute('SELECT has_function_privilege(current_user,%s,\'EXECUTE\')', (oid,)).fetchone()[0] == expected, function=name)
                if name in ('team_roster', 'manage_member', 'guard_membership', 'audit_membership'):
                    for role in ('anon', 'authenticated', 'service_role'):
                        check('public_api_function_denied', not c.execute('SELECT has_function_privilege(%s,%s,\'EXECUTE\')', (role, oid)).fetchone()[0], function=name, role=role)
        guards = c.execute("SELECT tgname,tgenabled FROM pg_trigger WHERE tgrelid='public.organization_members'::regclass AND NOT tgisinternal").fetchall()
        check('membership_guard_and_audit', {'membership_guard', 'membership_audit'} <= {name for name, state in guards if state in ('O', 'A')})
        check('transaction_read_only', c.execute('SHOW transaction_read_only').fetchone()[0] == 'on')
        c.rollback()
    return {'readOnly': True, 'readyByCatalog': all(f['passed'] for f in findings), 'checks': findings}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--env-file', required=True, type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if not args.env_file.is_file():
        parser.error('Arquivo de ambiente não encontrado.')
    values = {**dotenv_values(args.env_file), **os.environ}
    try:
        result = inspect(values.get('LOUNG_POSTGRES_DSN', ''))
        result['writesDisabledInConfiguration'] = values.get('LOUNG_ENABLE_WRITES', '0') != '1'
        result['sdrConfigurationPresent'] = {name: bool(values.get(name)) for name in ('GROQ_API_KEY', 'GROQ_MODEL')}
    except Exception as error:
        # Do not print driver messages, addresses or connection strings.
        result = {'readOnly': True, 'readyByCatalog': False, 'errorType': type(error).__name__}
    encoded = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(encoded + '\n', encoding='utf8')
    print(json.dumps({'readOnly': True, 'readyByCatalog': result['readyByCatalog'],
                      'failedChecks': [item for item in result.get('checks', []) if not item['passed']],
                      **{key: result[key] for key in ('writesDisabledInConfiguration', 'sdrConfigurationPresent', 'errorType') if key in result}}, ensure_ascii=False))
    if not result['readyByCatalog']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
