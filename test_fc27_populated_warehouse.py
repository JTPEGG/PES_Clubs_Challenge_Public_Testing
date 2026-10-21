"""Warehouse schema integrity and truthful missing/estimated field semantics."""
import sqlite3
import tempfile
import unittest
from pathlib import Path
from scripts.build_fc27_populated_warehouse import _stats,CORE,AUX,GAPS

SQL=(Path(__file__).resolve().parent/"warehouse/fc27_populated_reference_v1.sql").read_text()

class FC27WarehouseModelTests(unittest.TestCase):
    def setUp(self):
        self.db=sqlite3.connect(":memory:")
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.executescript(SQL)
        self.db.execute("""
          INSERT INTO wh_fc27_snapshot(edition,season,state,immutable_source_clubs,
            source_mens_players,source_active_players)
          VALUES(2027,'2026/27','frozen_reference_not_live_career',659,17849,17593)
        """)
        self.db.execute("""
          INSERT INTO wh_fc27_competitions VALUES(
          2027,'2027:en.1','England','Premier League',1,'open_pyramid',1,20,'source_membership')
        """)
        self.db.execute("""
          INSERT INTO wh_fc27_clubs VALUES(
          2027,'eng-club-1','Example United','2027:en.1','open_league_season_candidate')
        """)
    def tearDown(self):self.db.close()
    def test_contract_budget_provenance_and_no_invented_managers(self):
        self.db.execute("""
          INSERT INTO wh_fc27_club_financials VALUES(
          2027,'eng-club-1',100000,130000,500000,30000,.4,
          'modest_financial_proxy','game_model_estimate',
          'simulation_not_audited','game-model-v1')
        """)
        self.assertEqual(self.db.execute("""
          SELECT remaining_wage_headroom_weekly_gbp
          FROM wh_fc27_club_financials
        """).fetchone()[0],30000)
        self.db.executemany("INSERT INTO wh_fc27_coverage_gaps VALUES(2027,?,?,?)",GAPS)
        self.assertEqual(self.db.execute("""
          SELECT coverage_status FROM wh_fc27_coverage_gaps WHERE domain='managers'
        """).fetchone()[0],"not_populated")
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute("""
              INSERT INTO wh_fc27_club_financials VALUES(
                2027,'not-a-source-club',1,3,4,2,.1,'x','game_model_estimate','x','v1')
            """)
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute("""
              INSERT INTO wh_fc27_movement_routes VALUES(
                 2027,'2027:en.1','2027:en.2','dated_core_pyramid',2,0,2,0,
                 'test',1)
            """)
    def test_squad_is_frozen_reference_not_mutable_career(self):
        self.db.execute("""
          INSERT INTO wh_fc27_players VALUES(
          2027,'P-1','external-1','namespaced-1','Example Striker',
          NULL,NULL,NULL,NULL,NULL,65,'CF','[]','{}','provider')
        """)
        self.db.execute("""
          INSERT INTO wh_fc27_starting_rosters
          VALUES(2027,'P-1','eng-club-1','at_club')
        """)
        self.assertEqual(self.db.execute("""
          SELECT COUNT(*) FROM wh_fc27_playable_starting_squads
        """).fetchone()[0],1)
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute("""
              INSERT INTO wh_fc27_starting_rosters
              VALUES(2027,'unknown','eng-club-1','at_club')
            """)
        self.assertFalse(any(r[0].startswith("world_career") for r in
                             self.db.execute("SELECT name FROM sqlite_master")))
    def test_pes_attribute_conversion_cannot_silently_fill_unknowns(self):
        import json
        a={key:65 for key in CORE}
        b=dict(weak_foot_usage=2,weak_foot_accuracy=2,form=4,injury_resistance=2)
        x,y=_stats(json.dumps(a),json.dumps(b))
        self.assertEqual(len(x),25)
        self.assertEqual(len(y),4)
        del a["dribbling"]
        with self.assertRaisesRegex(ValueError,"25 core"):
            _stats(json.dumps(a),json.dumps(b))
        a["dribbling"]=65
        b["form"]=10
        with self.assertRaisesRegex(ValueError,"outside valid"):
            _stats(json.dumps(a),json.dumps(b))
if __name__=="__main__":
    unittest.main()
