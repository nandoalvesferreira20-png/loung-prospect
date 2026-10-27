-- Repair only the effective schema lookup privilege required by explicit auth.uid().
-- Run manually as the auth schema owner or a role with USAGE WITH GRANT OPTION.
-- No membership in loung_api and no SET ROLE loung_api are required to grant an ACL.
BEGIN;
GRANT USAGE ON SCHEMA auth TO loung_api;
DO $verify_auth_usage$
BEGIN
    IF NOT has_schema_privilege('loung_api', 'auth', 'USAGE') THEN
        RAISE EXCEPTION USING
            ERRCODE = '42501',
            MESSAGE = 'USAGE on schema auth was not granted to loung_api; use an authorized schema owner or grantor';
    END IF;
END
$verify_auth_usage$;
COMMIT;
