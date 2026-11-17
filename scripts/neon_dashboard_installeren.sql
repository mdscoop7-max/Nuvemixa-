-- NUVEMIXA dashboard: installatie in een AFZONDERLIJKE database (nooit in nuvemixa-2fa).
-- Uitvoeren als eigenaar van het nieuwe project (bv. neondb_owner), na jouw akkoord:
--   psql "<EIGENAAR-URL>" -v ON_ERROR_STOP=1 -v app_password="'<NIEUW-WACHTWOORD>'" \
--        -f nv_dashboard_postgres.sql -f scripts/neon_dashboard_installeren.sql
-- Het wachtwoord komt alleen op de commandoregel/in Render, nooit in Git of in dit bestand.
BEGIN;
DO $$ BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.schemata WHERE schema_name = 'nuvemixa_auth') THEN
    RAISE EXCEPTION 'Stop: schema nuvemixa_auth bestaat hier; dit is de 2FA-database. Gebruik een afzonderlijke database.';
  END IF;
END $$;
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'nuvemixa_dashboard_app') THEN
    CREATE ROLE nuvemixa_dashboard_app LOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE;
  END IF;
END $$;
ALTER ROLE nuvemixa_dashboard_app PASSWORD :app_password;
REVOKE ALL ON SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA nuvemixa_dashboard TO nuvemixa_dashboard_app;
-- Alleen SELECT/INSERT/UPDATE (de app verwijdert nergens rijen): geen DDL, TRUNCATE, DROP of DELETE.
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA nuvemixa_dashboard TO nuvemixa_dashboard_app;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA nuvemixa_dashboard TO nuvemixa_dashboard_app;
ALTER ROLE nuvemixa_dashboard_app SET search_path = nuvemixa_dashboard, pg_catalog;
COMMIT;
