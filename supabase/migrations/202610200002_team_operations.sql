-- Incremental; review and apply manually. No runtime table-write grants.
BEGIN;
-- Deploy as the trusted schema owner, never as a runtime login. Fail closed on
-- unexpected effective grants; this migration does not repair runtime roles.
DO $$
BEGIN
 IF current_user <> 'postgres' OR NOT EXISTS (
  SELECT 1 FROM pg_catalog.pg_roles WHERE rolname='postgres' AND rolbypassrls
 ) THEN
  RAISE EXCEPTION 'Apply as the trusted postgres deployment role' USING ERRCODE='42501';
 END IF;
 IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles r
  WHERE (r.rolsuper OR r.rolbypassrls OR r.rolcreaterole OR r.rolcreatedb OR r.rolreplication)
   AND pg_catalog.pg_has_role('loung_api',r.oid,'MEMBER'))
  OR pg_catalog.has_table_privilege('loung_api','public.organization_members','INSERT,UPDATE,DELETE,TRUNCATE')
  OR pg_catalog.has_any_column_privilege('loung_api','public.organization_members','INSERT,UPDATE')
  OR pg_catalog.has_table_privilege('loung_api','public.organizations','UPDATE')
  OR pg_catalog.has_any_column_privilege('loung_api','public.organizations','UPDATE')
  OR pg_catalog.has_table_privilege('loung_api','public.audit_events','INSERT,UPDATE,DELETE,TRUNCATE')
  OR pg_catalog.has_any_column_privilege('loung_api','public.audit_events','INSERT,UPDATE') THEN
  RAISE EXCEPTION 'Unexpected runtime privileges; review grants before deployment' USING ERRCODE='42501';
 END IF;
END $$;
CREATE FUNCTION public.team_roster() RETURNS TABLE("userId" uuid,"displayName" text,email text,role text,status text)
LANGUAGE sql STABLE SECURITY DEFINER SET search_path='' AS $$
 SELECT m.user_id,p.display_name,u.email::text,m.role,'active'::text
 FROM public.organization_members m JOIN public.profiles p ON p.id=m.user_id
 JOIN auth.users u ON u.id=m.user_id
 WHERE m.organization_id=public.active_org() AND public.is_member(m.organization_id)
 ORDER BY p.display_name,m.user_id
$$;

CREATE FUNCTION public.guard_membership() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
BEGIN
 PERFORM pg_advisory_xact_lock(hashtextextended(OLD.organization_id::text,0));
 -- A real MVCC write serializes owner changes even with a pre-existing
 -- REPEATABLE READ snapshot (the loser must retry SQLSTATE 40001).
 -- Keep the stored timestamp unchanged; no business rows are modified.
 UPDATE public.organizations AS o SET updated_at=o.updated_at WHERE o.id=OLD.organization_id;
 IF TG_OP='UPDATE' THEN
  IF NEW.organization_id<>OLD.organization_id OR NEW.user_id<>OLD.user_id THEN
   RAISE EXCEPTION 'Membership identity is immutable' USING ERRCODE='23514';
  END IF;
  IF NEW.role=OLD.role THEN RETURN NEW; END IF;
 END IF;
 IF OLD.role='owner' AND NOT EXISTS(SELECT 1 FROM public.organization_members
   WHERE organization_id=OLD.organization_id AND role='owner' AND user_id<>OLD.user_id) THEN
  RAISE EXCEPTION 'Last owner required' USING ERRCODE='23514',CONSTRAINT='organization_last_owner';
 END IF;
 IF TG_OP='DELETE' THEN RETURN OLD; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER membership_guard BEFORE UPDATE OR DELETE ON public.organization_members
 FOR EACH ROW EXECUTE FUNCTION public.guard_membership();

CREATE FUNCTION public.audit_membership() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
DECLARE o uuid; subject uuid; before_role text; after_role text;
BEGIN
 IF TG_OP<>'INSERT' THEN o:=OLD.organization_id;subject:=OLD.user_id;before_role:=OLD.role; END IF;
 IF TG_OP<>'DELETE' THEN o:=NEW.organization_id;subject:=NEW.user_id;after_role:=NEW.role; END IF;
 INSERT INTO public.audit_events(organization_id,actor_id,action,old_value,new_value,origin)
 VALUES(o,auth.uid(),'organization_members.'||lower(TG_OP),
 jsonb_build_object('user_id',subject,'role',before_role),jsonb_build_object('user_id',subject,'role',after_role),
 CASE WHEN auth.uid() IS NULL THEN 'operator' ELSE 'web' END);
 RETURN NULL;
END $$;
CREATE TRIGGER membership_audit AFTER INSERT OR UPDATE OR DELETE ON public.organization_members
 FOR EACH ROW EXECUTE FUNCTION public.audit_membership();

CREATE FUNCTION public.manage_member(target uuid,new_role text,remove_access boolean DEFAULT false) RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
DECLARE org uuid:=public.active_org();
BEGIN
 PERFORM pg_advisory_xact_lock(hashtextextended(org::text,0));
 -- Serialize BEFORE checking authority: a concurrently revoked owner must not
 -- authorize a change from an old snapshot. The trigger also covers direct DML.
 UPDATE public.organizations AS o SET updated_at=o.updated_at WHERE o.id=org;
 IF org IS NULL OR auth.uid() IS NULL OR NOT EXISTS(SELECT 1 FROM public.organization_members
  WHERE organization_id=org AND user_id=auth.uid() AND role='owner') OR target=auth.uid() THEN
  RAISE EXCEPTION 'Not authorized' USING ERRCODE='42501';
 END IF;
 IF target IS NULL OR remove_access IS NULL OR new_role IS NULL OR new_role NOT IN ('owner','admin','member') THEN
  RAISE EXCEPTION 'Invalid role' USING ERRCODE='22023';
 END IF;
 IF NOT EXISTS(SELECT 1 FROM public.organization_members WHERE organization_id=org AND user_id=target) THEN
  RAISE EXCEPTION 'Member unavailable' USING ERRCODE='P0002';
 END IF;
 IF remove_access THEN
  DELETE FROM public.organization_members WHERE organization_id=org AND user_id=target;
 ELSE
  UPDATE public.organization_members SET role=new_role WHERE organization_id=org AND user_id=target;
 END IF;
END $$;
ALTER FUNCTION public.team_roster() OWNER TO postgres;
ALTER FUNCTION public.manage_member(uuid,text,boolean) OWNER TO postgres;
ALTER FUNCTION public.guard_membership() OWNER TO postgres;
ALTER FUNCTION public.audit_membership() OWNER TO postgres;
-- Supabase/custom ALTER DEFAULT PRIVILEGES can add explicit grants in addition
-- to PUBLIC. Remove every inherited default ACL on these four new functions.
DO $$
DECLARE f regprocedure; grantee_oid oid;
BEGIN
 FOREACH f IN ARRAY ARRAY['public.team_roster()'::regprocedure,
  'public.manage_member(uuid,text,boolean)'::regprocedure,
  'public.guard_membership()'::regprocedure,'public.audit_membership()'::regprocedure]
 LOOP
  FOR grantee_oid IN SELECT DISTINCT a.grantee FROM pg_catalog.pg_proc p,
   LATERAL pg_catalog.aclexplode(COALESCE(p.proacl,pg_catalog.acldefault('f',p.proowner))) a
   WHERE p.oid=f AND a.grantee<>p.proowner
  LOOP
   EXECUTE format('REVOKE ALL ON FUNCTION %s FROM %s',f,
    CASE WHEN grantee_oid=0 THEN 'PUBLIC' ELSE quote_ident(pg_catalog.pg_get_userbyid(grantee_oid)) END);
  END LOOP;
 END LOOP;
END $$;
GRANT EXECUTE ON FUNCTION public.team_roster(),public.manage_member(uuid,text,boolean) TO loung_api;
DO $$
BEGIN
 -- Revoking direct ACLs cannot remove EXECUTE inherited through role membership.
 IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles r
  WHERE r.rolname IN ('anon','authenticated','service_role') AND (
   pg_catalog.has_function_privilege(r.oid,'public.team_roster()','EXECUTE') OR
   pg_catalog.has_function_privilege(r.oid,'public.manage_member(uuid,text,boolean)','EXECUTE') OR
   pg_catalog.has_function_privilege(r.oid,'public.guard_membership()','EXECUTE') OR
   pg_catalog.has_function_privilege(r.oid,'public.audit_membership()','EXECUTE'))) THEN
  RAISE EXCEPTION 'Unexpected inherited function access; review role membership' USING ERRCODE='42501';
 END IF;
END $$;
COMMIT;
