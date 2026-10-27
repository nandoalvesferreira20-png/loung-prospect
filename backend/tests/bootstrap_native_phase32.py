"""Bootstrap an EMPTY native PostgreSQL on the fixed test port, never an env DSN.

Use only with a disposable initdb cluster bound to 127.0.0.1:55431.
The existing integration suite uses the same synthetic marker and fixed DSN.
"""
from pathlib import Path
import psycopg

DSN='postgresql://postgres@127.0.0.1:55431/postgres?sslmode=disable&max_protocol_version=3.0'


def main():
    with psycopg.connect(DSN,connect_timeout=2,prepare_threshold=None) as c:
        assert c.execute('SELECT host(inet_server_addr()),inet_server_port()').fetchone()==('127.0.0.1',55431)
        assert c.execute("SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname IN ('public','auth')").fetchone()[0]==0,'Refusing a nonempty database'
        c.execute("""CREATE SCHEMA auth;CREATE SCHEMA extensions;
        CREATE ROLE anon NOLOGIN;CREATE ROLE authenticated NOLOGIN;
        CREATE ROLE service_role NOLOGIN BYPASSRLS;
        CREATE TABLE auth.users(id uuid PRIMARY KEY);
        CREATE FUNCTION auth.uid() RETURNS uuid LANGUAGE sql STABLE AS $$
        SELECT (nullif(current_setting('request.jwt.claims',true),'')::jsonb->>'sub')::uuid $$;
        CREATE TABLE public.phase31_test_marker(value text PRIMARY KEY);
        INSERT INTO public.phase31_test_marker VALUES('synthetic-memory-only');
        CREATE TABLE public.phase32_native_marker(value text PRIMARY KEY);
        INSERT INTO public.phase32_native_marker VALUES('native-disposable-cluster');""")
        for name in ('202610190001_phase31.sql','202610200001_repair_auth_schema_usage.sql'):
            c.execute((Path('supabase/migrations')/name).read_text(encoding='utf-8-sig'))
    print('Native synthetic PostgreSQL initialized; previous migrations applied locally only.')


if __name__=='__main__':main()
