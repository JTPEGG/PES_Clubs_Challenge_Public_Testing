"""Read-only FC27 unified reference warehouse adapter for future career integration.

A career must copy starting facts from a frozen warehouse dataset on creation;
never point mutable transfer logic directly at immutable source tables.
"""
from __future__ import annotations
import sqlite3
from pathlib import Path

class FC27WarehouseReader:
    def __init__(self, db_path):
        self.path=Path(db_path).resolve()
        if not self.path.is_file():
            raise FileNotFoundError(self.path)
        self.conn=sqlite3.connect(f"file:{self.path.as_posix()}?mode=ro",uri=True)
        self.conn.row_factory=sqlite3.Row
        self.conn.execute("PRAGMA query_only=ON")
        edition=self.conn.execute("""
          SELECT edition,season,state FROM wh_fc27_snapshot
        """).fetchone()
        if edition is None or tuple(edition)!=(
             2027,"2026/27","frozen_reference_not_live_career"):
            self.conn.close()
            raise ValueError("Invalid or mutable FC27 warehouse snapshot")
    def __enter__(self):return self
    def __exit__(self,*args):self.conn.close()
    def _rows(self,sql,params=()):
        return [dict(r) for r in self.conn.execute(sql,params)]
    def get_playable_competitions(self):
        return self._rows("""
          SELECT competition_code,country,name,tier,game_movement,
                 starting_original_clubs
          FROM wh_fc27_competitions
          WHERE edition=2027 AND intended_playable=1
          ORDER BY country,tier,competition_code
        """)
    def get_club(self,club_key):
        rows=self._rows("""
          SELECT c.club_key,c.name,c.competition_code,c.career_scope,
            l.country,l.tier,l.game_movement,
            f.starting_payroll_weekly_gbp,f.game_wage_budget_weekly_gbp,
            f.game_transfer_budget_gbp,f.remaining_wage_headroom_weekly_gbp,
            f.financial_capacity_band,f.finance_provenance,
            f.reliability_flag,f.finance_model_version
          FROM wh_fc27_clubs c
          JOIN wh_fc27_competitions l
            ON l.edition=c.edition AND l.competition_code=c.competition_code
          JOIN wh_fc27_club_financials f
            ON f.edition=c.edition AND f.club_key=c.club_key
          WHERE c.edition=2027 AND c.club_key=?
        """,(club_key,))
        return rows[0] if rows else None
    def get_starting_roster(self,club_key):
        return self._rows("""
          SELECT p.player_key,p.name,p.primary_position,
             p.source_player_id,con.weekly_game_wage_gbp,
             con.wage_provenance,con.contract_expires_on,con.expiry_provenance
          FROM wh_fc27_starting_rosters r
          JOIN wh_fc27_players p
            ON p.edition=r.edition AND p.player_key=r.player_key
          JOIN wh_fc27_starting_contracts con
            ON con.edition=p.edition AND con.player_key=p.player_key
          WHERE r.edition=2027 AND r.club_key=?
          ORDER BY p.name,p.player_key
        """,(club_key,))
    def get_player(self,player_key):
        base=self._rows("""
          SELECT p.player_key,p.name,p.date_of_birth,p.nationality,
                 p.primary_position,p.alternative_positions_json,
                 p.source_provider,p.namespaced_source_player_key,
                 r.club_key AS starting_club_key,
                 c.weekly_game_wage_gbp,c.source_observed_wage_weekly_gbp,
                 c.wage_provenance,c.contract_expires_on,
                 c.expiry_provenance
          FROM wh_fc27_players p
          JOIN wh_fc27_starting_rosters r
            ON r.edition=p.edition AND r.player_key=p.player_key
          JOIN wh_fc27_starting_contracts c
            ON c.edition=p.edition AND c.player_key=p.player_key
          WHERE p.edition=2027 AND p.player_key=?
        """,(player_key,))
        if not base:return None
        base[0]["pes2020_estimated_attributes"]={
          a["attribute_key"]:a["value"] for a in self._rows("""
            SELECT attribute_key,value FROM wh_fc27_player_attributes
            WHERE edition=2027 AND player_key=?
          """,(player_key,))
        }
        return base[0]
    def get_season_end_route(self,competition_code):
        routes=self._rows("""
          SELECT upper_code,lower_code,rule_type,direct_up,playoff_up,
              direct_down,conditional_places,rule_notes,enabled_for_career
          FROM wh_fc27_movement_routes WHERE edition=2027 AND upper_code=?
        """,(competition_code,))
        return routes[0] if routes else None
    def get_known_gaps(self):
        return self._rows("""
          SELECT domain,coverage_status,outstanding_reason
          FROM wh_fc27_coverage_gaps ORDER BY domain
        """)
    def get_club_ai_context(self,club_key):
        """Game-model reputation, board policy and dated finance circumstances.

        All simulated values carry explicit fields; observed prestige, cash,
        debt and owner injections remain NULL. No actual manager is implied.
        """
        rows=self._rows("""
           SELECT c.*,
              f.preseason_as_of,f.active_evidence_event_ids_json,
              f.verified_revenue_gbp,f.verified_net_debt_gbp,
              f.verified_owner_capital_injection_gbp,
              a.game_manager_key,a.display_role,
              a.game_coaching_ability,a.youth_development_bias,
              a.tactical_flexibility,a.recruitment_risk_appetite,
              a.financial_discipline,a.provenance AS simulated_manager_origin
           FROM wh_fc27_ai_club_decision_context c
           JOIN wh_fc27_club_financial_circumstances f
             ON f.edition=c.edition AND f.club_key=c.club_key
           JOIN wh_fc27_simulated_manager_agents a
             ON a.edition=c.edition AND a.starting_club_key=c.club_key
           WHERE c.edition=2027 AND c.club_key=?
        """,(club_key,))
        return rows[0] if rows else None

    def get_player_ai_context(self,player_key):
        """Existing sourced abilities/contracts and labelled fictional priors."""
        result=self.get_player(player_key)
        if result is None:return None
        traits=self._rows("""
           SELECT ambition_prior,loyalty_prior,professionalism_prior,
             temperament_prior,adaptability_prior,wage_motivation_prior,
             observed_real_personality_json,origin,
             identity_personality_source_status,model_version
           FROM wh_fc27_player_game_personality
           WHERE edition=2027 AND player_key=?
        """,(player_key,))
        if not traits:
            raise ValueError("FC27 decision reference lacks player gameplay priors")
        result["gameplay_personality"]=traits[0]
        return result

    def get_club_financial_events(self,club_key):
        return self._rows("""
          SELECT event_id,event_date,event_category,source_authority,
                 source_url,observed_fact,active_at_preseason
          FROM wh_fc27_financial_evidence_events
          WHERE edition=2027 AND club_key=? ORDER BY event_date,event_id
        """,(club_key,))

    def decision_dimension_coverage(self):
        domains=[
          ("clubs","wh_fc27_club_decision_profile"),
          ("finances","wh_fc27_club_financial_circumstances"),
          ("personalities","wh_fc27_player_game_personality"),
          ("anonymous_manager_simulation","wh_fc27_simulated_manager_agents"),
          ("actual_verified_managers","wh_fc27_manager_profiles"),
          ("source_financial_events","wh_fc27_financial_evidence_events")]
        return {name:self.conn.execute(
          f"SELECT COUNT(*) FROM {table} WHERE edition=2027"
        ).fetchone()[0] for name,table in domains}

    def snapshot_health(self):
        counts={}
        for name,table in [
          ("clubs","wh_fc27_clubs"),("competitions","wh_fc27_competitions"),
          ("players","wh_fc27_players"),("ratings","wh_fc27_player_attributes"),
          ("contracts","wh_fc27_starting_contracts"),
          ("club_finances","wh_fc27_club_financials"),
          ("season_end_routes","wh_fc27_movement_routes")]:
            counts[name]=self.conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        counts["immutable_reference"]=True
        counts["career_state_present"]=False
        return counts
