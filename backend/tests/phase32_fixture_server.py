"""Browser QA only: four synthetic accounts in the fixed memory-only database."""
import psycopg
from uuid import uuid4
from pathlib import Path
from backend.tests.phase31_fixture_server import create_app as base_app
from backend.tests.test_phase31_postgres import DSN

def create_app():
    with psycopg.connect(DSN,prepare_threshold=None) as c:
        assert c.execute('SELECT value FROM phase31_test_marker').fetchone()[0]=='synthetic-memory-only'
        c.execute('ALTER TABLE auth.users ADD COLUMN IF NOT EXISTS email text')
        if not c.execute("SELECT 1 FROM pg_proc WHERE proname='team_roster'").fetchone():
            c.execute(Path('supabase/migrations/202610200002_team_operations.sql').read_text(encoding='utf8'))
    app=base_app()
    with psycopg.connect(DSN,prepare_threshold=None) as c:
        org=c.execute("SELECT id FROM organizations WHERE name='Synthetic browser workspace' ORDER BY created_at DESC LIMIT 1").fetchone()[0]
        owner=c.execute('SELECT user_id FROM organization_members WHERE organization_id=%s',(org,)).fetchone()[0]
        c.execute("UPDATE organization_members SET role='owner' WHERE organization_id=%s AND user_id=%s",(org,owner))
        c.execute("UPDATE auth.users SET email='qa@example.invalid' WHERE id=%s",(owner,))
        for index,role in enumerate(('admin','member','member'),1):
            uid=str(uuid4())
            c.execute('INSERT INTO auth.users(id,email) VALUES(%s,%s)',(uid,f'qa{index}@example.invalid'))
            c.execute('INSERT INTO profiles(id,display_name) VALUES(%s,%s)',(uid,f'Synthetic QA {index}'))
            c.execute('INSERT INTO organization_members(organization_id,user_id,role) VALUES(%s,%s,%s)',(org,uid,role))
    return app
