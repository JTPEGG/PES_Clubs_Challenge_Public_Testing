"""Immutable 2027 warehouse app read adapter regression tests."""
import sqlite3,tempfile,unittest
from pathlib import Path
from warehouse.fc27_reference_reader import FC27WarehouseReader

SCHEMA=(Path(__file__).parent/"warehouse/fc27_populated_reference_v1.sql").read_text()

class FC27WarehouseReadOnlyTests(unittest.TestCase):
    def setUp(self):
        self.folder=tempfile.TemporaryDirectory()
        self.path=Path(self.folder.name)/"reference.sqlite"
        with sqlite3.connect(self.path) as db:
            db.executescript(SCHEMA)
            db.execute("""
              INSERT INTO wh_fc27_snapshot
              (edition,season,state,immutable_source_clubs,source_mens_players,source_active_players)
              VALUES(2027,'2026/27','frozen_reference_not_live_career',659,17849,17593)
            """)
            db.execute("""
              INSERT INTO wh_fc27_competitions VALUES(
                2027,'2027:en.1','England','Premier League',1,
                'open_pyramid',1,20,'source_verified')
            """)
            db.execute("""
              INSERT INTO wh_fc27_clubs VALUES(
                2027,'club-01','Example Town','2027:en.1','open_league_season_candidate')
            """)
            db.execute("""
              INSERT INTO wh_fc27_players VALUES(
                2027,'p-01','id-1','provider:1','Test Midfielder',NULL,
                'England','R','177','74',69,'CMF','[]','{}','source')
            """)
            db.execute("""
              INSERT INTO wh_fc27_starting_rosters VALUES(
                2027,'p-01','club-01','at_club')
            """)
            db.execute("""
              INSERT INTO wh_fc27_starting_contracts VALUES(
                2027,'p-01',5000,NULL,'modelled',NULL,'modelled',
                'regular','source_unknown','money-v1')
            """)
            db.execute("""
              INSERT INTO wh_fc27_club_financials VALUES(
                2027,'club-01',100000,130000,400000,30000,.5,
                'established_financial_proxy','game_model_estimate',
                'simulated','finance-v1')
            """)
            db.execute("""
              INSERT INTO wh_fc27_player_attributes VALUES(
                2027,'p-01','speed','pes2020_core_estimate',74,
                'fifa_pes_v2_converted_model')
            """)
            db.execute("""
              INSERT INTO wh_fc27_movement_routes VALUES(
                2027,'2027:en.1','2027:en.2','dated_core_pyramid',
                2,1,3,0,'game-mapped test',0)
            """)
            db.execute("""
              INSERT INTO wh_fc27_coverage_gaps VALUES(
                2027,'managers','not_populated','No manager source roster yet')
            """)
    def tearDown(self):self.folder.cleanup()
    def test_read_only_app_world_profiles(self):
        with FC27WarehouseReader(self.path) as wh:
            self.assertEqual(len(wh.get_playable_competitions()),1)
            self.assertEqual(wh.get_club("club-01")["game_transfer_budget_gbp"],400000)
            self.assertEqual(wh.get_club("missing"),None)
            self.assertEqual(wh.get_starting_roster("club-01")[0]["player_key"],"p-01")
            self.assertEqual(wh.get_player("p-01")["pes2020_estimated_attributes"]["speed"],74)
            self.assertEqual(wh.get_player("nonexistent"),None)
            self.assertEqual(wh.get_season_end_route("2027:en.1")["direct_down"],3)
            self.assertIsNone(wh.get_season_end_route("2027:us.mls"))
            self.assertEqual(wh.get_known_gaps()[0]["coverage_status"],"not_populated")
            with self.assertRaises(sqlite3.OperationalError):
                wh.conn.execute("UPDATE wh_fc27_clubs SET name='Changed'")
    def test_snapshot_validation_and_missing_file(self):
        with self.assertRaises(FileNotFoundError):FC27WarehouseReader(
          Path(self.folder.name)/"not-here.sqlite")
        with sqlite3.connect(self.path) as db:
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute("""
                  UPDATE wh_fc27_snapshot SET state='tampered' WHERE edition=2027
                """)
        with FC27WarehouseReader(self.path) as warehouse:
            self.assertTrue(warehouse.snapshot_health()["immutable_reference"])
if __name__=="__main__":unittest.main()
