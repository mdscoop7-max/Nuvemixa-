# Eindcontrole opslag (PR #80)

- Concepten (`research_notes`, prefix `[Concept]`), kandidaten (`suppliers`, status `onderzoek`) en statussen gaan via `nuvemixa_admin_store.connect()`.
  Met `NUVEMIXA_DASHBOARD_BACKEND=postgres` is dat schema `nuvemixa_dashboard` (tabellen met identity-id's in `nv_dashboard_postgres.sql`); anders SQLite.
- Bewezen op een lokale wegwerp-PostgreSQL 16 (niet Neon, niet het 2FA-schema): schrijven in proces A, server herstart, lezen in proces B → concept, status `geselecteerd` en kandidaat aanwezig.
- Test: `tests/test_opslag_eindcontrole.py` (PostgreSQL-deel draait alleen met `NUVEMIXA_TEST_PG_URL` naar een eigen wegwerpdatabase).
- Het dashboard toont nu "Opslag: permanent" (PostgreSQL actief) of "Opslag: tijdelijk" (SQLite op Render Free).
- Er wordt niets verwijderd; geen wijziging in 2FA, wachtwoorden of Neon-productiedata.

## Neon-installatie (nuvemixa-dashboard, Frankfurt)
- `scripts/neon_dashboard_installeren.sql`: weigert te draaien in een database met schema `nuvemixa_auth` (2FA), maakt rol `nuvemixa_dashboard_app` met alleen SELECT/INSERT/UPDATE op `nuvemixa_dashboard` (geen DELETE, TRUNCATE, DDL).
- Wachtwoord alleen in Render (`NUVEMIXA_DASHBOARD_DATABASE_URL`), nooit in Git.
- Herstel: Neon-snapshot (UI/MCP) of `pg_dump`/`pg_restore` van schema `nuvemixa_dashboard` naar een wegwerpdatabase; lokaal getest.
