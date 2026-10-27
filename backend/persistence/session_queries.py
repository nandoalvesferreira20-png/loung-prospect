"""Fixed statements in the authenticated session path; never log bound values."""
MEMBERSHIPS_SQL = 'SELECT m.organization_id::text,m.role,o.name FROM public.organization_members m JOIN public.organizations o ON o.id=m.organization_id WHERE m.user_id=%s ORDER BY o.slug'
PROFILE_SQL = 'SELECT display_name FROM profiles WHERE id=?'
STATEMENTS = {
    'session_memberships': MEMBERSHIPS_SQL,
    'session_profile': PROFILE_SQL,
    'set_runtime_role': 'SET LOCAL ROLE loung_api',
    'set_transaction_identity': "SELECT set_config('request.jwt.claims',%s,true),set_config('app.organization_id',%s,true)",
    'session_membership_recheck': 'SELECT role FROM public.organization_members WHERE organization_id=%s AND user_id=%s',
    'schema_metadata': "SELECT table_name,column_name FROM information_schema.columns WHERE table_schema='public' AND table_name=ANY(%s) ORDER BY table_name,ordinal_position",
}
