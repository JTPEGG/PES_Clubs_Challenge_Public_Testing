-- Isolated FC27 development-career snapshots.
-- Apply ONLY to Supabase project bjahvrmzcpqrynmoxokb
-- (Clubs_Challenge_Development), never to the original challenge save.
CREATE SCHEMA IF NOT EXISTS fc27_storage;
REVOKE ALL ON SCHEMA fc27_storage FROM PUBLIC, anon, authenticated;
CREATE TABLE IF NOT EXISTS fc27_storage.pes_save_store (
    save_key text PRIMARY KEY,
    db_bytes bytea NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT now()
);
REVOKE ALL ON fc27_storage.pes_save_store FROM PUBLIC, anon, authenticated;
-- The login role and password are provisioned out of band, never stored
-- in a migration or repository. It receives only schema USAGE and
-- SELECT, INSERT, UPDATE on this table.
