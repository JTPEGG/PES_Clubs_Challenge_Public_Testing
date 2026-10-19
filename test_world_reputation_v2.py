"""Continuous 2026/27 English pyramid model checks, independent of v1."""
import sqlite3
import tempfile
import unittest
from pathlib import Path
from flask import Flask
from world_v2 import initialize_world
from world_explorer import initialize_catalog
from world_reputation import initialize_reputations, assess_manager_application_v2
from world_reputation_v2 import (
    MODEL_VERSION,initialize_pyramid,get_pyramid_appeal,calculate_appeal,
    assess_player_interest,common_strength
)
from world_reputation_v2_ui import create_pyramid_blueprint


class PyramidReputationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory()
        cls.path=Path(cls.temp.name)/"pyramid.sqlite"
        cls.db=sqlite3.connect(cls.path)
        cls.db.row_factory=sqlite3.Row
        cls.db.execute("PRAGMA foreign_keys=ON")
        initialize_world(cls.db)
        initialize_catalog(cls.db)
        initialize_reputations(cls.db)
        initialize_pyramid(cls.db)
        cls.dataset="england-2026-27-fc27"

    @classmethod
    def tearDownClass(cls):
        cls.db.close()
        cls.temp.cleanup()

    @classmethod
    def _scores(cls):
        return {row["name"]:dict(row) for row in cls.db.execute("""
            SELECT c.name,r.sporting_appeal,r.squad_average,
                   r.prospects_label,r.institutional_prestige,r.competition_id
            FROM world_pyramid_club_appeal r
            JOIN world_clubs c ON c.club_id=r.club_id
            WHERE r.dataset_id=? AND r.model_version=?""",
            (cls.dataset,MODEL_VERSION))}

    def test_01_92_clubs_four_leagues_and_version_isolation(self):
        data=self._scores()
        self.assertEqual(len(data),92)
        self.assertEqual(
            self.db.execute("""SELECT COUNT(*) FROM world_pyramid_league_strength
               WHERE model_version=? AND dataset_id=?""",(MODEL_VERSION,self.dataset)).fetchone()[0],4)
        self.assertEqual(
            self.db.execute("SELECT COUNT(*) FROM world_club_reputation_snapshots WHERE dataset_id=?",
                           (self.dataset,)).fetchone()[0],92)
        self.assertTrue(all(v["institutional_prestige"] is None for v in data.values()))
        self.assertTrue(all(v["sporting_appeal"] is not None for v in data.values()))

    def test_02_arsenal_and_hull_diverge_without_league_cliff(self):
        d=self._scores()
        self.assertGreaterEqual(d["Arsenal"]["sporting_appeal"]-d["Hull City"]["sporting_appeal"],20)
        self.assertLessEqual(abs(d["West Ham United"]["sporting_appeal"]-d["Hull City"]["sporting_appeal"]),8)
        self.assertGreater(d["West Ham United"]["squad_average"],d["Hull City"]["squad_average"])

    def test_03_sporting_ability_overlaps_every_division_boundary(self):
        clubs=list(self._scores().values())
        for higher,lower in (("ENG1","ENG2"),("ENG2","ENG3"),("ENG3","ENG4")):
            weakest_above=min(x["sporting_appeal"] for x in clubs if x["competition_id"]==higher)
            strongest_below=max(x["sporting_appeal"] for x in clubs if x["competition_id"]==lower)
            self.assertLessEqual(abs(strongest_below-weakest_above),8,
                                 f"Unexpected division cliff between {higher}/{lower}")

    def test_04_reproducible_immutable_v2(self):
        previous=dict((k,v["sporting_appeal"]) for k,v in self._scores().items())
        initialize_pyramid(self.db)
        self.assertEqual(previous,dict((k,v["sporting_appeal"]) for k,v in self._scores().items()))
        self.assertEqual(common_strength(60),35)
        self.assertEqual(calculate_appeal(70,"ENG2",rank=1,competition_size=24)["prospects_adjustment"],1)
        self.assertIsNone(calculate_appeal(None,"ENG1")["sporting_appeal"])

    def test_05_overlap_changes_player_interest(self):
        d=self._scores()
        hull=d["Hull City"]["sporting_appeal"]
        west_ham=d["West Ham United"]["sporting_appeal"]
        to_hull=assess_player_interest(buyer_tier=1,seller_tier=2,
            buyer_score=hull,seller_score=west_ham)
        to_west_ham=assess_player_interest(buyer_tier=2,seller_tier=1,
            buyer_score=west_ham,seller_score=hull)
        self.assertEqual(to_hull["decision"],"open_to_talks")
        self.assertEqual(to_west_ham["decision"],"open_to_talks")
        arsenal=d["Arsenal"]["sporting_appeal"]
        refusal=assess_player_interest(buyer_tier=1,seller_tier=1,
            buyer_score=hull,seller_score=arsenal)
        self.assertEqual(refusal["decision"],"uninterested")
        self.assertFalse(refusal["can_negotiate"])

    def test_055_hiring_thresholds_reflect_within_league_differences(self):
        d=self._scores()
        arsenal=assess_manager_application_v2(manager_reputation=70,
            sporting_appeal=d["Arsenal"]["sporting_appeal"],league_tier=1)
        hull=assess_manager_application_v2(manager_reputation=70,
            sporting_appeal=d["Hull City"]["sporting_appeal"],league_tier=1)
        west_ham=assess_manager_application_v2(manager_reputation=70,
            sporting_appeal=d["West Ham United"]["sporting_appeal"],league_tier=2)
        self.assertGreater(arsenal["threshold"],hull["threshold"])
        self.assertEqual(arsenal["status"],"unlikely")
        self.assertEqual(hull["status"],"eligible_for_review")
        self.assertLessEqual(abs(hull["threshold"]-west_ham["threshold"]),8)

    def test_06_uncertain_historical_data_not_filled_with_2026_ratings(self):
        self.db.execute("INSERT OR IGNORE INTO world_seasons(season_id,label) VALUES('2004/05','2004/05')")
        self.db.execute("""INSERT OR IGNORE INTO world_datasets
           (dataset_id,season_id,title,source_label,source_date,status)
           VALUES ('pyramid-2004','2004/05','Empty 2004 test','No verified rating sources','2004-08-01','review')""")
        arsenal=self.db.execute("SELECT club_id FROM world_clubs WHERE name='Arsenal'").fetchone()[0]
        self.db.execute("""INSERT OR IGNORE INTO world_dataset_entries
            (dataset_id,competition_id,club_id) VALUES ('pyramid-2004','ENG1',?)""",(arsenal,))
        self.db.commit()
        initialize_pyramid(self.db)
        historic=get_pyramid_appeal(self.db,"pyramid-2004",arsenal)
        self.assertIsNone(historic["score"])
        self.assertEqual(historic["confidence"],"unassessed")
        self.assertIsNotNone(get_pyramid_appeal(self.db,self.dataset,arsenal)["score"])

    def test_07_audit_and_comparison_routes(self):
        app=Flask(__name__)
        app.register_blueprint(create_pyramid_blueprint(self.path))
        client=app.test_client()
        response=client.get("/world/reputations")
        self.assertEqual(response.status_code,200)
        self.assertIn(b"Club &amp; League Reputation Audit",response.data)
        self.assertIn(b"West Ham United",response.data)
        self.assertIn(b"Hull City",response.data)
        response=client.get("/world/reputations/compare?a=Hull+City&b=West+Ham+United")
        self.assertEqual(response.status_code,200)
        self.assertIn(b"Cross-Division Club Comparison",response.data)
        self.assertIn(b"Hull City",response.data)
        club_id=self.db.execute("SELECT club_id FROM world_clubs WHERE name='Hull City'").fetchone()[0]
        response=client.get(f"/world/reputations/v2/club/{club_id}")
        self.assertEqual(response.status_code,200)
        self.assertIn(b"Institutional prestige",response.data)
        self.assertEqual(client.get("/world/reputations?dataset=unknown").status_code,404)


if __name__=="__main__":
    unittest.main()
