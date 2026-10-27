"""AI decision model coverage: no false real personality, prestige, manager or cash claims."""
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from warehouse.fc27_enrich_decision_dimensions import (
    seed_personality,model_sporting_appeal,model_finance_pressure,
    model_club_game_plan,model_manager_hiring,build
)

ROOT=Path(__file__).resolve().parent

class FC27DecisionDimensionsTests(unittest.TestCase):
    def test_personality_is_stable_game_seed_not_inferred_identity(self):
        first=seed_personality("unambiguous-source-player-ID")
        self.assertEqual(first,seed_personality("unambiguous-source-player-ID"))
        self.assertNotEqual(first,seed_personality("different-source-player-ID"))
        self.assertEqual(len(first),6)
        self.assertTrue(all(35<=i<=65 for i in first))
        with self.assertRaisesRegex(ValueError,"Stable"):seed_personality("")
    def test_sporting_game_reputation_separate_from_real_prestige(self):
        premier,origin=model_sporting_appeal(83,1)
        lower,_=model_sporting_appeal(62,1)
        self.assertGreater(premier,lower+20)
        self.assertEqual(origin,"derived_squad")
        guessed,origin=model_sporting_appeal(None,3)
        self.assertEqual(origin,"league_tier_fallback")
        self.assertTrue(0<=guessed<=100)
        top=model_club_game_plan(appeal=82,standing_rank=1,
            standing_count=20,pressure_index=25,tier=1)
        bottom=model_club_game_plan(appeal=45,standing_rank=20,
            standing_count=20,pressure_index=25,tier=1)
        self.assertEqual(top[0],"upper_end")
        self.assertEqual(bottom[0],"lower_end")
        self.assertGreater(top[1],bottom[1])
    def test_distress_and_relegation_budget_constraints_are_preserved(self):
        self.assertEqual(model_finance_pressure(
            headroom=40000,payroll=100000,distress="documented_distress")[0],"distress")
        self.assertEqual(model_finance_pressure(
            headroom=-23000,payroll=120000,distress="model_wages_over_budget")[0],"over_committed")
        self.assertEqual(model_finance_pressure(
            headroom=3000,payroll=120000,distress="unverified")[0],"tight")
        self.assertEqual(model_finance_pressure(
            headroom=80000,payroll=120000,distress="unverified")[0],"normal")
        self.assertEqual(model_manager_hiring(sporting_appeal=54,ambition=60,
            financial_pressure=95,competitive_band="lower_end")[1],"financial_rebuild")
    def test_full_synthetic_reference_enrichment_leaves_master_untouched(self):
        with tempfile.TemporaryDirectory() as directory:
            tmp=Path(directory)
            reference=tmp/"reference.sqlite"
            circumstances=tmp/"financial.sqlite"
            enriched=tmp/"enriched.sqlite"
            with sqlite3.connect(reference) as db:
                db.execute("PRAGMA foreign_keys=ON")
                db.executescript((ROOT/"warehouse/fc27_populated_reference_v1.sql").read_text())
                db.execute("""
                   INSERT INTO wh_fc27_snapshot VALUES(
                   2027,'2026/27','frozen_reference_not_live_career',659,17849,17593,CURRENT_TIMESTAMP)
                """)
                db.execute("""
                   INSERT INTO wh_fc27_competitions VALUES(
                   2027,'2027:en.1','England','Premier League',1,
                   'open_pyramid',1,2,'known_source')
                """)
                for club in ("A","B"):
                    db.execute("""
                       INSERT INTO wh_fc27_clubs VALUES(
                       2027,? ,?,'2027:en.1','open_league_season_candidate')
                    """,(club,club))
                    db.execute("""
                       INSERT INTO wh_fc27_club_financials VALUES(
                       2027,?,100000,130000,400000,30000,.8,'strong_proxy',
                       'game_model_estimate','estimated','v1')
                    """,(club,))
                for i in range(20):
                    club="A" if i<10 else "B"
                    key=f"P{i}"
                    db.execute("""
                     INSERT INTO wh_fc27_players VALUES(
                      2027,?,?,? ,?,NULL,NULL,NULL,NULL,NULL,?, 'CMF','[]','{}','provider')
                    """,(key,f"src-{i}",f"namespace-{i}",f"Player {i}",83 if i<10 else 61))
                    db.execute("INSERT INTO wh_fc27_starting_rosters VALUES(2027,?,?,'at_club')",(key,club))
                db.commit()
            with sqlite3.connect(circumstances) as db:
                db.executescript("""
                CREATE TABLE historical_club_circumstances (
                club_key TEXT,edition INT,preseason_as_of TEXT,source_annual_payroll_gbp INT,
                revised_total_wage_budget_weekly_gbp INT,signed_wage_headroom_weekly_gbp INT,
                revised_transfer_budget_gbp INT,financial_health TEXT,owner_status TEXT,
                active_event_ids_json TEXT,revenue_reported_gbp INT,
                verified_cash_balance_gbp INT,verified_net_debt_gbp INT,
                verified_owner_capital_injection_gbp INT);
                CREATE TABLE observed_historical_events (
                  event_id TEXT,club_key TEXT,event_date TEXT,category TEXT,
                  source_authority TEXT,source_url TEXT,fact_text TEXT,
                  edition INT,active_at_preseason INT,source_match_status TEXT);
                """)
                for club in ("A","B"):
                    db.execute("""
                     INSERT INTO historical_club_circumstances VALUES(
                     ?,2027,'2026-08-01',100000,?, ?,?,
                     ?,'ownership_not_verified','[]',NULL,NULL,NULL,NULL)
                    """,(club,80000 if club=="B" else 130000,
                        -20000 if club=="B" else 30000,
                        1000 if club=="B" else 400000,
                        "model_wages_over_budget" if club=="B" else "unverified"))
                db.execute("""
                  INSERT INTO observed_historical_events VALUES(
                  'verified-example','B','2026-07-01','relegation','Official source',
                  'https://example.com/real-test','Confirmed for synthetic test only',
                  2027,1,'unique')
                """)
                db.commit()
            result=build(reference,circumstances,enriched,strict=False)
            self.assertEqual(result["club_profiles"],2)
            self.assertEqual(result["personality_priors"],20)
            self.assertEqual(result["real_verified_manager_profiles"],0)
            self.assertEqual(result["fictional_manager_recruitment_policies"],2)
            self.assertEqual(result["anonymous_simulated_manager_agent_profiles"],2)
            self.assertEqual(result["financial_source_events_as_of_preseason"],1)
            with sqlite3.connect(reference) as orig:
                self.assertEqual(orig.execute("""
                  SELECT COUNT(*) FROM sqlite_master
                  WHERE name='wh_fc27_club_decision_profile'
                """).fetchone()[0],0)
            with sqlite3.connect(enriched) as db:
                db.execute("PRAGMA foreign_keys=ON")
                self.assertEqual(db.execute("PRAGMA integrity_check").fetchone()[0],"ok")
                self.assertFalse(db.execute("PRAGMA foreign_key_check").fetchall())
                self.assertEqual(db.execute("""
                  SELECT pressure_band,signed_wage_headroom_weekly_gbp,
                    verified_owner_capital_injection_gbp FROM wh_fc27_club_financial_circumstances
                  WHERE club_key='B'
                """).fetchone(),("over_committed",-20000,None))
                self.assertEqual(db.execute("""
                  SELECT identity_status,named_manager_source_key
                  FROM wh_fc27_manager_recruitment_policy WHERE club_key='A'
                """).fetchone(),("real_manager_unverified",None))
                self.assertEqual(db.execute("""
                  SELECT real_manager_name,real_manager_source_key,display_role
                  FROM wh_fc27_simulated_manager_agents WHERE starting_club_key='A'
                """).fetchone(),(None,None,"Anonymous simulated coaching agent"))
                self.assertEqual(db.execute("""
                  SELECT COUNT(*) FROM wh_fc27_player_game_personality
                  WHERE observed_real_personality_json IS NULL
                """).fetchone()[0],20)
if __name__=="__main__":unittest.main()
