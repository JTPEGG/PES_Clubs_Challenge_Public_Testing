-- PES Clubs Challenge warehouse blueprint v1: ADDITIVE / NOT APPLIED TO PRODUCTION.
-- SQLite-compatible development specification. PostgreSQL migration must preserve
-- semantics, FK constraints and origin provenance.
-- Parent tables already defined by world_v2.py/world_explorer.py:
--   world_datasets(dataset_id), world_players(player_id),
--   world_clubs(club_id), world_competitions(competition_id).
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS wh_sources (
 source_id TEXT PRIMARY KEY,
 name TEXT NOT NULL,
 source_url TEXT,
 rights_basis TEXT NOT NULL CHECK(rights_basis IN
   ('licensed','open_data','original_research','internal_simulation','permission','unresolved')),
 source_version TEXT NOT NULL,
 retrieved_on TEXT,
 description TEXT,
 CHECK(source_url IS NULL OR LENGTH(source_url)>5)
);

CREATE TABLE IF NOT EXISTS wh_field_evidence (
 evidence_id INTEGER PRIMARY KEY,
 dataset_id TEXT NOT NULL REFERENCES world_datasets(dataset_id),
 entity_type TEXT NOT NULL CHECK(entity_type IN
   ('player','club','manager','competition','stadium','contract')),
 entity_id TEXT NOT NULL,
 field_path TEXT NOT NULL,
 source_id TEXT NOT NULL REFERENCES wh_sources(source_id),
 origin TEXT NOT NULL CHECK(origin IN ('source','model','operator','derived')),
 valid_as_of TEXT,
 value_description TEXT,
 recorded_on TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 UNIQUE(dataset_id,entity_type,entity_id,field_path,source_id,valid_as_of)
);

-- Primary and ALTERNATIVE positions are multi-row, not one secondary column.
-- Upstream world_players.primary_position remains legacy until read adapters ship.
-- A suitability OVR is optional: no arbitrary primary=100/alternative=80 rule.
CREATE TABLE IF NOT EXISTS wh_player_positions (
 dataset_id TEXT NOT NULL REFERENCES world_datasets(dataset_id),
 player_id INTEGER NOT NULL REFERENCES world_players(player_id),
 position_code TEXT NOT NULL,
 position_kind TEXT NOT NULL CHECK(position_kind IN ('primary','alternative')),
 suitability_ovr INTEGER CHECK(suitability_ovr BETWEEN 1 AND 99),
 origin TEXT NOT NULL CHECK(origin IN ('source','model','operator','derived')),
 source_id TEXT NOT NULL REFERENCES wh_sources(source_id),
 source_note TEXT NOT NULL DEFAULT '',
 PRIMARY KEY(dataset_id,player_id,position_code),
 CHECK(LENGTH(position_code) BETWEEN 2 AND 12)
);
CREATE UNIQUE INDEX IF NOT EXISTS wh_one_primary_position
 ON wh_player_positions(dataset_id,player_id) WHERE position_kind='primary';

-- A player with zero listed alternatives might truly play one position,
-- or might simply have no scouting evidence. Record review completeness.
CREATE TABLE IF NOT EXISTS wh_player_position_reviews (
 dataset_id TEXT NOT NULL REFERENCES world_datasets(dataset_id),
 player_id INTEGER NOT NULL REFERENCES world_players(player_id),
 review_status TEXT NOT NULL CHECK(review_status IN
  ('unreviewed','partial','verified_complete')),
 reviewed_on TEXT,
 source_id TEXT NOT NULL REFERENCES wh_sources(source_id),
 review_note TEXT,
 PRIMARY KEY(dataset_id,player_id)
);

-- Attribute key examples: sprint_speed, acceleration, passing, stamina,
-- finishing, heading; existing six FC categories map to separate keys.
CREATE TABLE IF NOT EXISTS wh_player_attributes (
 dataset_id TEXT NOT NULL REFERENCES world_datasets(dataset_id),
 player_id INTEGER NOT NULL REFERENCES world_players(player_id),
 attribute_key TEXT NOT NULL,
 value INTEGER NOT NULL CHECK(value BETWEEN 1 AND 99),
 scale TEXT NOT NULL DEFAULT '1-99' CHECK(scale='1-99'),
 origin TEXT NOT NULL CHECK(origin IN ('source','model','operator','derived')),
 source_id TEXT NOT NULL REFERENCES wh_sources(source_id),
 PRIMARY KEY(dataset_id,player_id,attribute_key)
);

-- Personality is a stable fictional behavioural profile; current morale,
-- unhappiness and transfer requests are CAREER state, not immutable traits.
CREATE TABLE IF NOT EXISTS wh_player_traits (
 dataset_id TEXT NOT NULL REFERENCES world_datasets(dataset_id),
 player_id INTEGER NOT NULL REFERENCES world_players(player_id),
 trait_key TEXT NOT NULL,
 score INTEGER NOT NULL CHECK(score BETWEEN 0 AND 100),
 origin TEXT NOT NULL CHECK(origin IN ('source','model','operator','derived')),
 source_id TEXT NOT NULL REFERENCES wh_sources(source_id),
 model_version TEXT,
 PRIMARY KEY(dataset_id,player_id,trait_key),
 CHECK(origin!='model' OR model_version IS NOT NULL)
);

-- Club institution separate from squad-form reputation and career cash ledger.
CREATE TABLE IF NOT EXISTS wh_club_profiles (
 dataset_id TEXT NOT NULL REFERENCES world_datasets(dataset_id),
 club_id INTEGER NOT NULL REFERENCES world_clubs(club_id),
 institutional_stature INTEGER CHECK(institutional_stature BETWEEN 0 AND 100),
 domestic_reputation INTEGER CHECK(domestic_reputation BETWEEN 0 AND 100),
 continental_reputation INTEGER CHECK(continental_reputation BETWEEN 0 AND 100),
 fanbase_score INTEGER CHECK(fanbase_score BETWEEN 0 AND 100),
 board_ambition TEXT CHECK(board_ambition IN
  ('survival','stability','growth','promotion','continental','title')),
 ownership_strategy TEXT CHECK(ownership_strategy IN
  ('conservative','balanced','investment','sell_to_sustain')),
 recruitment_strategy TEXT CHECK(recruitment_strategy IN
  ('development','value','balanced','established_stars')),
 origin TEXT NOT NULL CHECK(origin IN ('source','model','operator','derived')),
 source_id TEXT NOT NULL REFERENCES wh_sources(source_id),
 PRIMARY KEY(dataset_id,club_id)
);

CREATE TABLE IF NOT EXISTS wh_stadiums (
 stadium_id TEXT PRIMARY KEY,
 name TEXT NOT NULL,
 city TEXT,
 country TEXT,
 opened_year INTEGER CHECK(opened_year BETWEEN 1800 AND 2200),
 capacity INTEGER CHECK(capacity>0),
 pitch_surface TEXT,
 source_id TEXT NOT NULL REFERENCES wh_sources(source_id)
);
CREATE TABLE IF NOT EXISTS wh_club_stadiums (
 dataset_id TEXT NOT NULL REFERENCES world_datasets(dataset_id),
 club_id INTEGER NOT NULL REFERENCES world_clubs(club_id),
 stadium_id TEXT NOT NULL REFERENCES wh_stadiums(stadium_id),
 is_home INTEGER NOT NULL DEFAULT 1 CHECK(is_home IN (0,1)),
 usage_note TEXT,
 PRIMARY KEY(dataset_id,club_id,stadium_id)
);
CREATE UNIQUE INDEX IF NOT EXISTS wh_one_main_home_stadium
 ON wh_club_stadiums(dataset_id,club_id) WHERE is_home=1;

CREATE TABLE IF NOT EXISTS wh_club_facilities (
 dataset_id TEXT NOT NULL REFERENCES world_datasets(dataset_id),
 club_id INTEGER NOT NULL REFERENCES world_clubs(club_id),
 training_quality INTEGER CHECK(training_quality BETWEEN 0 AND 100),
 academy_quality INTEGER CHECK(academy_quality BETWEEN 0 AND 100),
 youth_recruitment INTEGER CHECK(youth_recruitment BETWEEN 0 AND 100),
 medical_quality INTEGER CHECK(medical_quality BETWEEN 0 AND 100),
 origin TEXT NOT NULL CHECK(origin IN ('source','model','operator','derived')),
 source_id TEXT NOT NULL REFERENCES wh_sources(source_id),
 PRIMARY KEY(dataset_id,club_id)
);

CREATE TABLE IF NOT EXISTS wh_managers (
 manager_id TEXT PRIMARY KEY,
 full_name TEXT NOT NULL,
 birth_date TEXT,
 nationality TEXT,
 created_on TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS wh_manager_external_ids (
 source_id TEXT NOT NULL REFERENCES wh_sources(source_id),
 external_id TEXT NOT NULL,
 manager_id TEXT NOT NULL REFERENCES wh_managers(manager_id),
 PRIMARY KEY(source_id,external_id),
 UNIQUE(source_id,manager_id)
);
CREATE TABLE IF NOT EXISTS wh_manager_profiles (
 dataset_id TEXT NOT NULL REFERENCES world_datasets(dataset_id),
 manager_id TEXT NOT NULL REFERENCES wh_managers(manager_id),
 reputation INTEGER CHECK(reputation BETWEEN 0 AND 100),
 tactical_style TEXT,
 preferred_formation TEXT,
 preferred_pressing TEXT,
 youth_priority INTEGER CHECK(youth_priority BETWEEN 0 AND 100),
 negotiation_aggression INTEGER CHECK(negotiation_aggression BETWEEN 0 AND 100),
 loyalty INTEGER CHECK(loyalty BETWEEN 0 AND 100),
 ambition INTEGER CHECK(ambition BETWEEN 0 AND 100),
 risk_tolerance INTEGER CHECK(risk_tolerance BETWEEN 0 AND 100),
 transfer_philosophy TEXT CHECK(transfer_philosophy IN
  ('protect_squad','sell_to_reinvest','development','win_now','balanced')),
 origin TEXT NOT NULL CHECK(origin IN ('source','model','operator','derived')),
 source_id TEXT NOT NULL REFERENCES wh_sources(source_id),
 PRIMARY KEY(dataset_id,manager_id)
);
CREATE TABLE IF NOT EXISTS wh_manager_appointments (
 appointment_id TEXT PRIMARY KEY,
 dataset_id TEXT NOT NULL REFERENCES world_datasets(dataset_id),
 manager_id TEXT NOT NULL REFERENCES wh_managers(manager_id),
 club_id INTEGER NOT NULL REFERENCES world_clubs(club_id),
 started_on TEXT NOT NULL,
 ended_on TEXT,
 appointment_type TEXT NOT NULL CHECK(appointment_type IN ('permanent','interim','caretaker')),
 origin TEXT NOT NULL CHECK(origin IN ('source','model','operator','derived')),
 source_id TEXT NOT NULL REFERENCES wh_sources(source_id),
 CHECK(ended_on IS NULL OR ended_on>=started_on)
);
CREATE INDEX IF NOT EXISTS wh_manager_appointments_club
 ON wh_manager_appointments(dataset_id,club_id,started_on);

-- Rules belong to a competition in a specific source season; they must not
-- rewrite historic league membership or alter an active PES season.
CREATE TABLE IF NOT EXISTS wh_competition_rules (
 dataset_id TEXT NOT NULL REFERENCES world_datasets(dataset_id),
 competition_id TEXT NOT NULL REFERENCES world_competitions(competition_id),
 format TEXT NOT NULL CHECK(format IN ('league','knockout','groups_knockout','mixed')),
 participating_clubs INTEGER CHECK(participating_clubs>1),
 points_for_win INTEGER CHECK(points_for_win BETWEEN 0 AND 5),
 points_for_draw INTEGER CHECK(points_for_draw BETWEEN 0 AND 3),
 promoted_places INTEGER CHECK(promoted_places>=0),
 relegated_places INTEGER CHECK(relegated_places>=0),
 registration_policy TEXT,
 foreign_player_rule TEXT,
 domestic_cup_qualification TEXT,
 continental_qualification TEXT,
 prestige INTEGER CHECK(prestige BETWEEN 0 AND 100),
 origin TEXT NOT NULL CHECK(origin IN ('source','model','operator','derived')),
 source_id TEXT NOT NULL REFERENCES wh_sources(source_id),
 PRIMARY KEY(dataset_id,competition_id),
 CHECK(promoted_places IS NULL OR participating_clubs IS NULL OR promoted_places<participating_clubs),
 CHECK(relegated_places IS NULL OR participating_clubs IS NULL OR relegated_places<participating_clubs)
);

CREATE TABLE IF NOT EXISTS wh_competition_prizes (
 dataset_id TEXT NOT NULL REFERENCES world_datasets(dataset_id),
 competition_id TEXT NOT NULL REFERENCES world_competitions(competition_id),
 finish_position INTEGER NOT NULL CHECK(finish_position>0),
 prize_gbp INTEGER CHECK(prize_gbp>=0),
 source_id TEXT NOT NULL REFERENCES wh_sources(source_id),
 origin TEXT NOT NULL CHECK(origin IN ('source','model','operator','derived')),
 PRIMARY KEY(dataset_id,competition_id,finish_position)
);

-- Existing live truth remains in world_dataset_player_contracts,
-- world_dataset_club_finances, world_dataset_transfer_history and
-- world_career_* tables. This schema does not duplicate or mutate them.
