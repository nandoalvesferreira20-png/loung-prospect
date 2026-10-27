-- Incremental application-function repair. Review and apply manually.
-- No managed schema changes, grants, RLS changes or business-data writes.
BEGIN;

DO $preflight$
BEGIN
 IF current_user <> 'postgres' THEN
  RAISE EXCEPTION 'Apply as the trusted application function owner' USING ERRCODE='42501';
 END IF;
 IF NOT EXISTS (
  SELECT 1 FROM pg_catalog.pg_proc p
  JOIN pg_catalog.pg_roles r ON r.oid=p.proowner
  WHERE p.oid='public.stamp_actor()'::pg_catalog.regprocedure
    AND r.rolname='postgres' AND NOT p.prosecdef
    AND p.prorettype='pg_catalog.trigger'::pg_catalog.regtype
 ) THEN
  RAISE EXCEPTION 'Unexpected stamp_actor owner or execution mode; review before deployment'
   USING ERRCODE='42501';
 END IF;
END
$preflight$;

-- SECURITY INVOKER is intentional. FastAPI verifies the JWT before setting
-- request.jwt.claims with SET LOCAL semantics in the same transaction.
-- This function stamps authorship; it does not authenticate or grant access.
-- Existing membership checks and RLS remain responsible for authorization.
CREATE OR REPLACE FUNCTION public.stamp_actor() RETURNS trigger
LANGUAGE plpgsql VOLATILE SECURITY INVOKER SET search_path=''
AS $stamp_actor$
DECLARE actor pg_catalog.uuid;
BEGIN
 actor := nullif(
  nullif(pg_catalog.current_setting('request.jwt.claims',true),'')::pg_catalog.jsonb ->> 'sub',
  ''
 )::pg_catalog.uuid;
 -- Runtime writes must never silently lose authorship. Trusted operator work
 -- without JWT claims retains the existing NULL/migration-origin behavior.
 IF current_user='loung_api' AND actor IS NULL THEN
  RAISE EXCEPTION 'Authenticated transaction identity required' USING ERRCODE='42501';
 END IF;
 IF TG_OP='INSERT' THEN
  NEW.created_by := actor;
 ELSE
  NEW.created_by := OLD.created_by;
 END IF;
 NEW.updated_by := actor;
 RETURN NEW;
END
$stamp_actor$;

-- CREATE OR REPLACE retains ownership, ACLs, OID and dependent triggers.
-- Do not add EXECUTE grants: existing triggers do not require a new grant.
DO $postflight$
BEGIN
 IF pg_catalog.has_function_privilege('loung_api','public.stamp_actor()','EXECUTE')
    OR pg_catalog.has_function_privilege('anon','public.stamp_actor()','EXECUTE')
    OR pg_catalog.has_function_privilege('authenticated','public.stamp_actor()','EXECUTE') THEN
  RAISE EXCEPTION 'Unexpected direct stamp_actor execution grant; review ACLs'
   USING ERRCODE='42501';
 END IF;
END
$postflight$;

COMMIT;
