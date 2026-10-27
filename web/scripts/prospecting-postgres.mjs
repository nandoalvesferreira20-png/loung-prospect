// Disposable PostgreSQL engine for deduplication/RLS tests. No env or migrations.
import { PGlite } from '@electric-sql/pglite';
import { PGLiteSocketServer } from '@electric-sql/pglite-socket';
const db = await PGlite.create();
await db.exec(`
CREATE TABLE prospecting_test_marker(value text);
INSERT INTO prospecting_test_marker VALUES ('prospecting-isolated-memory');
CREATE ROLE loung_api NOLOGIN NOBYPASSRLS;
CREATE TABLE organization_members(organization_id text, user_id text, role text);
CREATE TABLE leads(id serial PRIMARY KEY, organization_id text, provider text,
 provider_place_id text, google_maps text, empresa text, endereco text, telefone text);
INSERT INTO organization_members VALUES ('org-a','user-a','owner'),('org-b','user-b','owner');
ALTER TABLE leads ENABLE ROW LEVEL SECURITY;
ALTER TABLE leads FORCE ROW LEVEL SECURITY;
CREATE POLICY scoped ON leads USING (
 organization_id=current_setting('app.organization_id',true)
 AND EXISTS(SELECT 1 FROM organization_members m WHERE m.organization_id=leads.organization_id
 AND m.user_id=(current_setting('request.jwt.claims',true)::jsonb->>'sub')));
GRANT SELECT ON leads,organization_members TO loung_api;
INSERT INTO leads(organization_id,provider,provider_place_id,google_maps,empresa,endereco,telefone)
VALUES ('org-a','google_places','a','map-a','Synthetic A','address-a','phone-a'),
 ('org-b','google_places','b','map-b','Synthetic B','address-b','phone-b');
`);
const server = new PGLiteSocketServer({db, port:55432, host:'127.0.0.1', maxConnections:8});
await server.start();
console.log('SYNTHETIC prospecting PostgreSQL ready on 127.0.0.1:55432; no migrations');
process.on('SIGINT',async()=>{await server.stop();await db.close();process.exit(0);});
