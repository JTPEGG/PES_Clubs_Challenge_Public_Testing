-- FC27 populated stand-alone canonical reference snapshot v1.
-- A READ MODEL, not a new world_career_* authority or Render migration.
-- All source ID / value provenance retained. PES native export deferred.
PRAGMA foreign_keys=ON;
CREATE TABLE wh_fc27_snapshot(
 edition INTEGER PRIMARY KEY CHECK(edition=2027),
 season TEXT NOT NULL CHECK(season='2026/27'),
 state TEXT NOT NULL CHECK(state='frozen_reference_not_live_career'),
 immutable_source_clubs INTEGER NOT NULL CHECK(immutable_source_clubs=659),
 source_mens_players INTEGER NOT NULL CHECK(source_mens_players=17849),
 source_active_players INTEGER NOT NULL CHECK(source_active_players=17593),
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE wh_fc27_source_manifest(
 source_key TEXT PRIMARY KEY,
 original_filename TEXT NOT NULL,
 sha256 TEXT NOT NULL CHECK(length(sha256)=64),
 source_role TEXT NOT NULL CHECK(source_role IN
  ('competition_source_and_game_scope','male_player_contracts_and_loans',
   'source_backed_game_finance_model')),
 source_or_model TEXT NOT NULL CHECK(source_or_model IN ('mixed','game_model','source_archive')),
 edition INTEGER NOT NULL DEFAULT 2027 REFERENCES wh_fc27_snapshot(edition));
CREATE TABLE wh_fc27_competitions(
 edition INTEGER NOT NULL REFERENCES wh_fc27_snapshot(edition),
 competition_code TEXT NOT NULL,
 country TEXT NOT NULL,
 name TEXT NOT NULL,
 tier INTEGER NOT NULL,
 game_movement TEXT NOT NULL CHECK(game_movement IN ('open_pyramid','closed')),
 intended_playable INTEGER NOT NULL CHECK(intended_playable IN(0,1)),
 starting_original_clubs INTEGER NOT NULL CHECK(starting_original_clubs>=1),
 original_membership_basis TEXT NOT NULL,
 PRIMARY KEY(edition,competition_code));
CREATE TABLE wh_fc27_clubs(
 edition INTEGER NOT NULL REFERENCES wh_fc27_snapshot(edition),
 club_key TEXT NOT NULL,
 name TEXT NOT NULL,
 competition_code TEXT NOT NULL,
 career_scope TEXT NOT NULL CHECK(career_scope IN
  ('open_league_season_candidate','playable_closed_league_candidate','closed_background_world')),
 PRIMARY KEY(edition,club_key),
 FOREIGN KEY(edition,competition_code) REFERENCES wh_fc27_competitions(edition,competition_code));
CREATE INDEX wh_fc27_clubs_league ON wh_fc27_clubs(edition,competition_code);
CREATE TABLE wh_fc27_players(
 edition INTEGER NOT NULL REFERENCES wh_fc27_snapshot(edition),
 player_key TEXT NOT NULL,
 source_player_id TEXT NOT NULL,
 namespaced_source_player_key TEXT NOT NULL,
 name TEXT NOT NULL,
 date_of_birth TEXT,
 nationality TEXT,
 preferred_foot TEXT,
 height_cm TEXT,
 weight_kg TEXT,
 source_overall INTEGER,
 primary_position TEXT NOT NULL,
 alternative_positions_json TEXT NOT NULL,
 position_fit_indices_json TEXT NOT NULL,
 source_provider TEXT NOT NULL,
 PRIMARY KEY(edition,player_key));
CREATE TABLE wh_fc27_starting_rosters(
 edition INTEGER NOT NULL,
 player_key TEXT NOT NULL,
 club_key TEXT NOT NULL,
 assignment TEXT NOT NULL CHECK(assignment='at_club'),
 PRIMARY KEY(edition,player_key),
 FOREIGN KEY(edition,player_key) REFERENCES wh_fc27_players(edition,player_key),
 FOREIGN KEY(edition,club_key) REFERENCES wh_fc27_clubs(edition,club_key));
CREATE INDEX wh_fc27_rosters_club ON wh_fc27_starting_rosters(edition,club_key);
CREATE TABLE wh_fc27_player_positions(
 edition INTEGER NOT NULL,
 player_key TEXT NOT NULL,
 position_code TEXT NOT NULL,
 position_kind TEXT NOT NULL CHECK(position_kind IN ('primary','alternative')),
 suitability_value REAL,
 suitability_origin TEXT NOT NULL CHECK(suitability_origin IN ('source','source_unknown')),
 PRIMARY KEY(edition,player_key,position_code),
 FOREIGN KEY(edition,player_key) REFERENCES wh_fc27_players(edition,player_key));
CREATE UNIQUE INDEX wh_fc27_one_primary ON wh_fc27_player_positions(edition,player_key) WHERE position_kind='primary';
CREATE TABLE wh_fc27_player_attributes(
 edition INTEGER NOT NULL,
 player_key TEXT NOT NULL,
 attribute_key TEXT NOT NULL,
 rating_layer TEXT NOT NULL CHECK(rating_layer IN ('pes2020_core_estimate','pes2020_auxiliary_estimate')),
 value INTEGER NOT NULL,
 source_role TEXT NOT NULL CHECK(source_role='fifa_pes_v2_converted_model'),
 PRIMARY KEY(edition,player_key,attribute_key),
 FOREIGN KEY(edition,player_key) REFERENCES wh_fc27_players(edition,player_key));
CREATE INDEX wh_fc27_player_attributes_key ON wh_fc27_player_attributes(edition,attribute_key);
CREATE TABLE wh_fc27_starting_contracts(
 edition INTEGER NOT NULL,
 player_key TEXT NOT NULL,
 weekly_game_wage_gbp INTEGER NOT NULL CHECK(weekly_game_wage_gbp>=0),
 source_observed_wage_weekly_gbp INTEGER CHECK(source_observed_wage_weekly_gbp>=0),
 wage_provenance TEXT NOT NULL,
 contract_expires_on TEXT,
 expiry_provenance TEXT NOT NULL,
 initial_squad_tier TEXT NOT NULL,
 wage_quality_warning TEXT NOT NULL,
 wage_model_version TEXT NOT NULL,
 PRIMARY KEY(edition,player_key),
 FOREIGN KEY(edition,player_key) REFERENCES wh_fc27_players(edition,player_key));
CREATE TABLE wh_fc27_starting_loans(
 edition INTEGER NOT NULL,
 player_key TEXT NOT NULL,
 borrower_club_key TEXT NOT NULL,
 parent_club_key TEXT,
 parent_match_status TEXT NOT NULL,
 game_return_date TEXT,
 simulated_borrower_wage_share_pct INTEGER,
 PRIMARY KEY(edition,player_key),
 FOREIGN KEY(edition,player_key) REFERENCES wh_fc27_players(edition,player_key),
 FOREIGN KEY(edition,borrower_club_key) REFERENCES wh_fc27_clubs(edition,club_key),
 FOREIGN KEY(edition,parent_club_key) REFERENCES wh_fc27_clubs(edition,club_key));
CREATE TABLE wh_fc27_club_financials(
 edition INTEGER NOT NULL,
 club_key TEXT NOT NULL,
 starting_payroll_weekly_gbp INTEGER NOT NULL CHECK(starting_payroll_weekly_gbp>=0),
 game_wage_budget_weekly_gbp INTEGER NOT NULL CHECK(game_wage_budget_weekly_gbp>=0),
 game_transfer_budget_gbp INTEGER NOT NULL CHECK(game_transfer_budget_gbp>=0),
 remaining_wage_headroom_weekly_gbp INTEGER NOT NULL,
 financial_capacity_percentile REAL NOT NULL CHECK(financial_capacity_percentile BETWEEN 0 AND 1),
 financial_capacity_band TEXT NOT NULL,
 finance_provenance TEXT NOT NULL CHECK(finance_provenance='game_model_estimate'),
 reliability_flag TEXT NOT NULL,
 finance_model_version TEXT NOT NULL,
 PRIMARY KEY(edition,club_key),
 FOREIGN KEY(edition,club_key) REFERENCES wh_fc27_clubs(edition,club_key),
 CHECK(remaining_wage_headroom_weekly_gbp=game_wage_budget_weekly_gbp-starting_payroll_weekly_gbp));
CREATE TABLE wh_fc27_movement_routes(
 edition INTEGER NOT NULL,
 upper_code TEXT NOT NULL,
 lower_code TEXT NOT NULL,
 rule_type TEXT NOT NULL,
 direct_up INTEGER,
 playoff_up INTEGER,
 direct_down INTEGER,
 conditional_places INTEGER,
 rule_notes TEXT NOT NULL,
 enabled_for_career INTEGER NOT NULL CHECK(enabled_for_career=0),
 PRIMARY KEY(edition,upper_code),
 FOREIGN KEY(edition,upper_code) REFERENCES wh_fc27_competitions(edition,competition_code));
CREATE TABLE wh_fc27_coverage_gaps(
 edition INTEGER NOT NULL REFERENCES wh_fc27_snapshot(edition),
 domain TEXT NOT NULL,
 coverage_status TEXT NOT NULL,
 outstanding_reason TEXT NOT NULL,
 PRIMARY KEY(edition,domain));
CREATE VIEW wh_fc27_playable_starting_squads AS
 SELECT r.edition,r.club_key,c.name AS club_name,c.competition_code,
        p.player_key,p.name AS player_name,p.primary_position,
        f.weekly_game_wage_gbp
 FROM wh_fc27_starting_rosters r
 JOIN wh_fc27_players p ON p.edition=r.edition AND p.player_key=r.player_key
 JOIN wh_fc27_clubs c ON c.edition=r.edition AND c.club_key=r.club_key
 LEFT JOIN wh_fc27_starting_contracts f ON f.edition=r.edition AND f.player_key=r.player_key
 WHERE c.career_scope IN ('open_league_season_candidate','playable_closed_league_candidate');
