"""Reproduce the original advisory-only guard in a disposable native database.

Run AFTER bootstrap_native_phase32.py and BEFORE test_phase32_team.py.
Never reads environment DSNs; requires the native synthetic marker.
"""
from uuid import uuid4
import psycopg
from backend.tests.bootstrap_native_phase32 import DSN


def main():
    org,a,b=[str(uuid4()) for _ in range(3)]
    with psycopg.connect(DSN) as c:
        assert c.execute('SELECT value FROM public.phase32_native_marker').fetchone()[0]=='native-disposable-cluster'
        assert c.execute("SELECT to_regprocedure('public.guard_membership()')").fetchone()[0] is None
        c.execute("INSERT INTO organizations(id,name,slug) VALUES(%s,'Synthetic MVCC proof',%s)",(org,'proof-'+org))
        for uid in (a,b):
            c.execute('INSERT INTO auth.users(id) VALUES(%s)',(uid,))
            c.execute("INSERT INTO profiles(id,display_name) VALUES(%s,'Synthetic proof')",(uid,))
            c.execute("INSERT INTO organization_members(organization_id,user_id,role) VALUES(%s,%s,'owner')",(org,uid))
        c.execute("""CREATE FUNCTION public.synthetic_unsafe_guard() RETURNS trigger
        LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$ BEGIN
        PERFORM pg_advisory_xact_lock(hashtextextended(OLD.organization_id::text,0));
        IF OLD.role='owner' AND NOT EXISTS(SELECT 1 FROM public.organization_members
        WHERE organization_id=OLD.organization_id AND role='owner' AND user_id<>OLD.user_id) THEN
        RAISE EXCEPTION 'Last owner required' USING ERRCODE='23514'; END IF;
        RETURN NEW; END $$;
        CREATE TRIGGER synthetic_unsafe_guard BEFORE UPDATE ON public.organization_members
        FOR EACH ROW EXECUTE FUNCTION public.synthetic_unsafe_guard();""")
    try:
        with psycopg.connect(DSN) as x,psycopg.connect(DSN) as y:
            for c in (x,y):
                c.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ')
                assert c.execute("SELECT count(*) FROM organization_members WHERE organization_id=%s AND role='owner'",(org,)).fetchone()[0]==2
            x.execute("UPDATE organization_members SET role='admin' WHERE organization_id=%s AND user_id=%s",(org,a));x.commit()
            y.execute("UPDATE organization_members SET role='admin' WHERE organization_id=%s AND user_id=%s",(org,b));y.commit()
        with psycopg.connect(DSN) as c:
            assert c.execute("SELECT count(*) FROM organization_members WHERE organization_id=%s AND role='owner'",(org,)).fetchone()[0]==0
        print('REPRODUCED: original advisory-only logic permits zero owners with two old RR snapshots.')
    finally:
        with psycopg.connect(DSN) as c:
            c.execute('DROP TRIGGER synthetic_unsafe_guard ON public.organization_members; DROP FUNCTION public.synthetic_unsafe_guard()')
            c.execute('DELETE FROM organization_members WHERE organization_id=%s',(org,))
            c.execute('DELETE FROM organizations WHERE id=%s',(org,))
            c.execute('DELETE FROM profiles WHERE id IN (%s,%s)',(a,b))
            c.execute('DELETE FROM auth.users WHERE id IN (%s,%s)',(a,b))


if __name__=='__main__':main()
