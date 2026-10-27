-- psql only. Run using the existing loung_web login, never an administrative one.
-- Supply -v user_id=EXISTING_AUTH_UUID -v organization_id=AUTHORIZED_ORG_UUID.
\set ON_ERROR_STOP on
BEGIN READ ONLY;
SET LOCAL ROLE loung_api;
SELECT current_user = 'loung_api' AS runtime_role_ok;
SELECT set_config('request.jwt.claims',json_build_object('sub', :'user_id', 'role','authenticated')::text,true) AS setup_claims,
       set_config('app.organization_id', :'organization_id',true) AS setup_org
\gset
SELECT auth.uid() = :'user_id'::uuid AS auth_uid_ok,
       has_schema_privilege(current_user,'auth','USAGE') AS auth_usage,
       has_function_privilege(current_user,'auth.uid()','EXECUTE') AS uid_execute,
       NOT has_schema_privilege(current_user,'auth','CREATE') AS no_auth_create,
       NOT has_table_privilege(current_user,'auth.users','SELECT') AS no_auth_users_read;
SELECT count(*) AS matching_memberships
FROM public.organization_members m JOIN public.organizations o ON o.id=m.organization_id
WHERE m.user_id=:'user_id'::uuid AND m.organization_id=:'organization_id'::uuid;
SELECT count(*) AS visible_own_profile FROM public.profiles WHERE id=:'user_id'::uuid;
SELECT NOT EXISTS(SELECT 1 FROM public.leads WHERE organization_id<>:'organization_id'::uuid) AS no_cross_org_rows;
SELECT NOT rolsuper AND NOT rolbypassrls AS restricted_runtime FROM pg_roles WHERE rolname=current_user;
ROLLBACK;
