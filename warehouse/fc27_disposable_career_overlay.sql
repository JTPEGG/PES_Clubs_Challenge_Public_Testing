-- Disposable FC27 career overlay demonstration; NEVER installed into production.
-- The actual world_career_* persistence adapter remains separately gated.
PRAGMA foreign_keys=ON;
CREATE TABLE fc27_demo_career_metadata(
 career_id TEXT PRIMARY KEY,
 edition INTEGER NOT NULL CHECK(edition=2027),
 source_sha256 TEXT NOT NULL CHECK(length(source_sha256)=64),
 simulation_status TEXT NOT NULL CHECK(simulation_status='isolated_test_only'),
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE fc27_demo_career_clubs(
 career_id TEXT NOT NULL,
 club_key TEXT NOT NULL,
 starting_competition TEXT NOT NULL,
 intended_manager_selectable INTEGER NOT NULL CHECK(intended_manager_selectable IN (0,1)),
 PRIMARY KEY(career_id,club_key),
 FOREIGN KEY(career_id) REFERENCES fc27_demo_career_metadata(career_id));
CREATE TABLE fc27_demo_career_registrations(
 career_id TEXT NOT NULL,
 player_key TEXT NOT NULL,
 original_club_key TEXT NOT NULL,
 current_club_key TEXT NOT NULL,
 revision INTEGER NOT NULL CHECK(revision>=0),
 PRIMARY KEY(career_id,player_key),
 FOREIGN KEY(career_id,original_club_key) REFERENCES fc27_demo_career_clubs(career_id,club_key),
 FOREIGN KEY(career_id,current_club_key) REFERENCES fc27_demo_career_clubs(career_id,club_key));
CREATE INDEX fc27_demo_current_squad ON fc27_demo_career_registrations(career_id,current_club_key);
CREATE TABLE fc27_demo_career_starting_contracts(
 career_id TEXT NOT NULL,
 player_key TEXT NOT NULL,
 starting_weekly_wage_gbp INTEGER NOT NULL,
 wage_provenance TEXT NOT NULL,
 starting_contract_expires_on TEXT,
 expiry_provenance TEXT NOT NULL,
 PRIMARY KEY(career_id,player_key),
 FOREIGN KEY(career_id,player_key) REFERENCES fc27_demo_career_registrations(career_id,player_key));
CREATE TABLE fc27_demo_career_starting_finances(
 career_id TEXT NOT NULL,
 club_key TEXT NOT NULL,
 starting_payroll_weekly_gbp INTEGER NOT NULL,
 model_wage_budget_weekly_gbp INTEGER NOT NULL,
 model_transfer_budget_gbp INTEGER NOT NULL,
 model_provenance TEXT NOT NULL CHECK(model_provenance='game_model_estimate'),
 PRIMARY KEY(career_id,club_key),
 FOREIGN KEY(career_id,club_key) REFERENCES fc27_demo_career_clubs(career_id,club_key));
CREATE TABLE fc27_demo_registration_events(
 career_id TEXT NOT NULL,
 transaction_key TEXT NOT NULL,
 player_key TEXT NOT NULL,
 selling_club_key TEXT NOT NULL,
 buying_club_key TEXT NOT NULL,
 before_revision INTEGER NOT NULL,
 after_revision INTEGER NOT NULL,
 entry_origin TEXT NOT NULL CHECK(entry_origin='verified_test_simulation_not_a_real_transfer'),
 PRIMARY KEY(career_id,transaction_key),
 FOREIGN KEY(career_id,player_key) REFERENCES fc27_demo_career_registrations(career_id,player_key));
