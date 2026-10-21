-- FC27 gameplay decision reference dimensions v1.
-- All values either dated evidence or visibly marked deterministic SIMULATION MODEL.
-- No unverified claims about real personalities/owners/managers.
-- Additive to already validated wh_fc27_* immutable source warehouse.
PRAGMA foreign_keys=ON;
CREATE TABLE wh_fc27_decision_model_versions (
  model_key TEXT PRIMARY KEY,
  model_version TEXT NOT NULL,
  assumption_policy TEXT NOT NULL,
  source_sha256 TEXT,
  verified_real_world_claim INTEGER NOT NULL CHECK(verified_real_world_claim=0));
CREATE TABLE wh_fc27_club_decision_profile (
  edition INTEGER NOT NULL CHECK(edition=2027),
  club_key TEXT NOT NULL,
  sporting_appeal INTEGER NOT NULL CHECK(sporting_appeal BETWEEN 0 AND 100),
  institutional_prestige INTEGER,
  squad_top16_source_overall_avg REAL,
  sampled_overall_players INTEGER NOT NULL CHECK(sampled_overall_players>=0),
  league_squad_strength_rank INTEGER,
  league_club_count INTEGER NOT NULL CHECK(league_club_count>0),
  expected_competitive_band TEXT NOT NULL CHECK(expected_competitive_band IN
      ('upper_end','mid_table','lower_end','unassessed')),
  ambition_level INTEGER NOT NULL CHECK(ambition_level BETWEEN 0 AND 100),
  pressure_to_improve INTEGER NOT NULL CHECK(pressure_to_improve BETWEEN 0 AND 100),
  operating_approach TEXT NOT NULL CHECK(operating_approach IN
      ('high_ambition','balanced','consolidate','survival','unassessed')),
  game_reputation_origin TEXT NOT NULL CHECK(game_reputation_origin='derived_source_squad_game_proxy'),
  ambition_origin TEXT NOT NULL CHECK(ambition_origin='explicit_gameplay_simulation_not_verified_board_intent'),
  identity_evidence_status TEXT NOT NULL CHECK(identity_evidence_status='institutional_prestige_not_verified'),
  confidence TEXT NOT NULL CHECK(confidence IN ('sufficient_squad_evidence','limited_squad_evidence','tier_proxy_only')),
  model_version TEXT NOT NULL,
  PRIMARY KEY(edition,club_key),
  FOREIGN KEY(edition,club_key) REFERENCES wh_fc27_clubs(edition,club_key),
  CHECK(institutional_prestige IS NULL));
CREATE TABLE wh_fc27_club_financial_circumstances (
  edition INTEGER NOT NULL CHECK(edition=2027),
  club_key TEXT NOT NULL,
  preseason_as_of TEXT NOT NULL,
  model_weekly_wage_ceiling_gbp INTEGER NOT NULL CHECK(model_weekly_wage_ceiling_gbp>=0),
  committed_payroll_weekly_gbp INTEGER NOT NULL CHECK(committed_payroll_weekly_gbp>=0),
  signed_wage_headroom_weekly_gbp INTEGER NOT NULL,
  model_transfer_allowance_gbp INTEGER NOT NULL CHECK(model_transfer_allowance_gbp>=0),
  financial_health TEXT NOT NULL,
  pressure_band TEXT NOT NULL CHECK(pressure_band IN ('distress','over_committed','tight','normal')),
  pressure_index INTEGER NOT NULL CHECK(pressure_index BETWEEN 0 AND 100),
  ownership_status TEXT NOT NULL,
  active_evidence_event_ids_json TEXT NOT NULL,
  verified_revenue_gbp INTEGER,
  verified_cash_balance_gbp INTEGER,
  verified_net_debt_gbp INTEGER,
  verified_owner_capital_injection_gbp INTEGER,
  model_source TEXT NOT NULL CHECK(model_source='historical-club-financial-circumstances-v2'),
  reliable_actual_accounts INTEGER NOT NULL CHECK(reliable_actual_accounts=0),
  PRIMARY KEY(edition,club_key),
  FOREIGN KEY(edition,club_key) REFERENCES wh_fc27_clubs(edition,club_key),
  CHECK(signed_wage_headroom_weekly_gbp =
      model_weekly_wage_ceiling_gbp-committed_payroll_weekly_gbp),
  CHECK(verified_revenue_gbp IS NULL AND verified_cash_balance_gbp IS NULL AND
    verified_net_debt_gbp IS NULL AND verified_owner_capital_injection_gbp IS NULL));
CREATE TABLE wh_fc27_financial_evidence_events (
  edition INTEGER NOT NULL CHECK(edition=2027),
  event_id TEXT NOT NULL,
  club_key TEXT NOT NULL,
  event_date TEXT NOT NULL,
  event_category TEXT NOT NULL,
  source_authority TEXT NOT NULL,
  source_url TEXT NOT NULL,
  observed_fact TEXT NOT NULL,
  active_at_preseason INTEGER NOT NULL CHECK(active_at_preseason=1),
  is_observed_source_fact INTEGER NOT NULL CHECK(is_observed_source_fact=1),
  financial_amount_claimed INTEGER NOT NULL CHECK(financial_amount_claimed=0),
  PRIMARY KEY(edition,event_id),
  FOREIGN KEY(edition,club_key) REFERENCES wh_fc27_clubs(edition,club_key));
CREATE TABLE wh_fc27_player_game_personality (
  edition INTEGER NOT NULL CHECK(edition=2027),
  player_key TEXT NOT NULL,
  ambition_prior INTEGER NOT NULL CHECK(ambition_prior BETWEEN 25 AND 75),
  loyalty_prior INTEGER NOT NULL CHECK(loyalty_prior BETWEEN 25 AND 75),
  professionalism_prior INTEGER NOT NULL CHECK(professionalism_prior BETWEEN 25 AND 75),
  temperament_prior INTEGER NOT NULL CHECK(temperament_prior BETWEEN 25 AND 75),
  adaptability_prior INTEGER NOT NULL CHECK(adaptability_prior BETWEEN 25 AND 75),
  wage_motivation_prior INTEGER NOT NULL CHECK(wage_motivation_prior BETWEEN 25 AND 75),
  observed_real_personality_json TEXT,
  origin TEXT NOT NULL CHECK(origin='fictional_stable_game_seed_not_real_player_claim'),
  identity_personality_source_status TEXT NOT NULL CHECK(identity_personality_source_status='unverified'),
  model_version TEXT NOT NULL,
  PRIMARY KEY(edition,player_key),
  FOREIGN KEY(edition,player_key) REFERENCES wh_fc27_players(edition,player_key),
  CHECK(observed_real_personality_json IS NULL));
CREATE TABLE wh_fc27_manager_profiles (
  edition INTEGER NOT NULL CHECK(edition=2027),
  manager_source_key TEXT NOT NULL,
  full_name TEXT NOT NULL,
  confirmed_club_key TEXT,
  source_url TEXT NOT NULL,
  source_effective_date TEXT NOT NULL,
  preferred_style TEXT,
  style_source_url TEXT,
  PRIMARY KEY(edition,manager_source_key),
  FOREIGN KEY(edition,confirmed_club_key) REFERENCES wh_fc27_clubs(edition,club_key),
  CHECK(length(source_url)>12));
CREATE TABLE wh_fc27_manager_recruitment_policy (
  edition INTEGER NOT NULL CHECK(edition=2027),
  club_key TEXT NOT NULL,
  named_manager_source_key TEXT,
  identity_status TEXT NOT NULL CHECK(identity_status='real_manager_unverified'),
  required_manager_reputation INTEGER NOT NULL CHECK(required_manager_reputation BETWEEN 0 AND 100),
  preferred_game_management_style TEXT NOT NULL CHECK(preferred_game_management_style IN
     ('development','balanced','results_first','financial_rebuild')),
  tolerance_for_risk INTEGER NOT NULL CHECK(tolerance_for_risk BETWEEN 0 AND 100),
  tolerance_for_rebuild INTEGER NOT NULL CHECK(tolerance_for_rebuild BETWEEN 0 AND 100),
  source_origin TEXT NOT NULL CHECK(source_origin='fictional_club_hiring_archetype_not_real_person'),
  model_version TEXT NOT NULL,
  PRIMARY KEY(edition,club_key),
  FOREIGN KEY(edition,club_key) REFERENCES wh_fc27_clubs(edition,club_key),
  FOREIGN KEY(edition,named_manager_source_key)
       REFERENCES wh_fc27_manager_profiles(edition,manager_source_key),
  CHECK(named_manager_source_key IS NULL));
-- Anonymised game-AI coaching behaviour; this is NOT a verified human manager
-- identity, appointment, real tactical formation or observed personality.
CREATE TABLE wh_fc27_simulated_manager_agents (
  edition INTEGER NOT NULL CHECK(edition=2027),
  game_manager_key TEXT NOT NULL,
  starting_club_key TEXT NOT NULL,
  real_manager_source_key TEXT,
  real_manager_name TEXT,
  display_role TEXT NOT NULL CHECK(display_role='Anonymous simulated coaching agent'),
  game_coaching_ability INTEGER NOT NULL CHECK(game_coaching_ability BETWEEN 15 AND 95),
  youth_development_bias INTEGER NOT NULL CHECK(youth_development_bias BETWEEN 15 AND 95),
  tactical_flexibility INTEGER NOT NULL CHECK(tactical_flexibility BETWEEN 15 AND 95),
  recruitment_risk_appetite INTEGER NOT NULL CHECK(recruitment_risk_appetite BETWEEN 15 AND 95),
  financial_discipline INTEGER NOT NULL CHECK(financial_discipline BETWEEN 15 AND 95),
  playing_style TEXT NOT NULL CHECK(playing_style IN
    ('development','balanced','results_first','financial_rebuild')),
  provenance TEXT NOT NULL CHECK(provenance='fictional_game_ai_agent_not_a_real_person_or_appointment'),
  model_version TEXT NOT NULL,
  PRIMARY KEY(edition,game_manager_key),
  UNIQUE(edition,starting_club_key),
  FOREIGN KEY(edition,starting_club_key) REFERENCES wh_fc27_clubs(edition,club_key),
  CHECK(real_manager_source_key IS NULL AND real_manager_name IS NULL)
);
CREATE VIEW wh_fc27_ai_club_decision_context AS
 SELECT c.edition,c.club_key,c.name,c.competition_code,c.career_scope,
        d.sporting_appeal,d.institutional_prestige,d.ambition_level,
        d.pressure_to_improve,d.operating_approach,d.confidence,
        f.pressure_band,f.pressure_index,f.financial_health,f.ownership_status,
        f.model_weekly_wage_ceiling_gbp,f.signed_wage_headroom_weekly_gbp,
        f.model_transfer_allowance_gbp,f.verified_cash_balance_gbp,
        p.required_manager_reputation,p.preferred_game_management_style,
        p.named_manager_source_key
 FROM wh_fc27_clubs c
 JOIN wh_fc27_club_decision_profile d ON d.edition=c.edition AND d.club_key=c.club_key
 JOIN wh_fc27_club_financial_circumstances f ON f.edition=c.edition AND f.club_key=c.club_key
 JOIN wh_fc27_manager_recruitment_policy p ON p.edition=c.edition AND p.club_key=c.club_key;
