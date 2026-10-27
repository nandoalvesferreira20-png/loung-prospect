// Synthetic PostgreSQL only: all state is in WASM memory and disappears on exit.
import {PGlite} from '@electric-sql/pglite';
import {unaccent} from '@electric-sql/pglite/contrib/unaccent';
import {PGLiteSocketServer} from '@electric-sql/pglite-socket';
import {readFile} from 'node:fs/promises';
const db=await PGlite.create({extensions:{unaccent}});
await db.exec(`CREATE SCHEMA auth;CREATE SCHEMA extensions;
CREATE ROLE anon NOLOGIN;CREATE ROLE authenticated NOLOGIN;CREATE ROLE service_role NOLOGIN BYPASSRLS;
CREATE TABLE auth.users(id uuid PRIMARY KEY);
CREATE FUNCTION auth.uid() RETURNS uuid LANGUAGE sql STABLE AS $$ SELECT (nullif(current_setting('request.jwt.claims',true),'')::jsonb->>'sub')::uuid $$;
CREATE TABLE public.phase31_test_marker(value text PRIMARY KEY);INSERT INTO public.phase31_test_marker VALUES('synthetic-memory-only');`);
const migration=await readFile(new URL('../../supabase/migrations/202610190001_phase31.sql',import.meta.url),'utf8');
await db.exec(migration);
const server=new PGLiteSocketServer({db,port:55431,host:'127.0.0.1',maxConnections:16});
await server.start();console.log('SYNTHETIC PostgreSQL ready on 127.0.0.1:55431');
process.on('SIGINT',async()=>{await server.stop();await db.close();process.exit(0);});

